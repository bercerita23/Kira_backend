import asyncio
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.router.aws_ses import *
from openai import OpenAI
#---img generation---
import os
import io
import base64
from PIL import Image
from google import genai
from google.genai import types
from app.model.topics import Topic
from app.model.questions import Question
from app.model.users import User
from app.router.aws_s3 import S3Service
from app.config import settings

OPENAI_MODEL = "gpt-4o-mini"
NUM_OF_QUESTION = 5
s3_service = S3Service()

async def prompt_generation(): 
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)

    while True: 
        try:
            with SessionLocal() as db:
                # find entries that are READY_FOR_GENERATION
                ready_entries = db.query(Topic).filter(Topic.state == "READY_FOR_GENERATION").all()

                for rn in ready_entries: 
                    # get the pdf from S3 
                    pdf_bytes = s3_service.get_file_by_url(rn.s3_bucket_url)

                    pdf_buffer = io.BytesIO(pdf_bytes)
                    pdf_buffer.name = "document.pdf"
                    # quiz and prompt generation 
                    # 1st upload the pdf for openai model
                    client = OpenAI(api_key=settings.OPENAI_API_KEY)
                    
                    uploaded_file = client.files.create(
                        file=pdf_buffer,
                        purpose="assistants"
                    )

                    with open("app/gen_ai_prompts/open_ai_role_prompt.txt", encoding="utf-8") as f: 
                        role_prompt = f.read()

                    
                    # Create an assistant that can read files
                    assistant = client.beta.assistants.create(
                        name="KIRA",
                        instructions=role_prompt,
                        model=OPENAI_MODEL,
                        tools=[{"type": "file_search"}]
                    )

                    # Create a thread
                    thread = client.beta.threads.create()

                    # Add a message with the file
                    message = client.beta.threads.messages.create(
                        thread_id=thread.id,
                        role="user",
                        content=f"Return {NUM_OF_QUESTION} questions in total about that pdf",
                        attachments=[
                            {
                                "file_id": uploaded_file.id,
                                "tools": [{"type": "file_search"}]
                            }
                        ]
                    )

                    # Run the assistant
                    run = client.beta.threads.runs.create(
                        thread_id=thread.id,
                        assistant_id=assistant.id
                    )

                    # Wait for completion and get the response
                    while run.status in ["queued", "in_progress"]:
                        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)


                    # Get the messages
                    messages = client.beta.threads.messages.list(thread_id=thread.id)
                    response = messages.data[0].content[0].text.value
                    print(response)
                
                    # change the state to PROMPTS_GENERATED                             
            await asyncio.sleep(10)
        except Exception as e: 
            print(f"Error in repeated task: {e}")
            # rollback just in case
            try:
                db.rollback()
            except:
                pass
            await asyncio.sleep(10)