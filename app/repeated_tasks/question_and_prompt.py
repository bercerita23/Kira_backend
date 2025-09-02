import asyncio
import io
from openai import OpenAI
from sqlalchemy import select
from app.database.db import get_async_db
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.model.topics import Topic
from app.model.questions import *
from app.router.aws_s3 import S3Service
from app.config import settings
import re, json

OPENAI_MODEL = "gpt-4o-mini"
NUM_OF_QUESTION = 5
s3_service = S3Service()

async def prompt_generation():
    """Process a single topic that needs prompt generation"""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    async with get_async_db() as db:
        ###########################################################
        ### step 1: get the entry in READY_FOR_GENERATION state ###
        ###########################################################
        rn = (await db.execute(select(Topic)
                .filter(Topic.state == "READY_FOR_GENERATION")
                .order_by(Topic.updated_at.asc())
                )).scalars().first()
        
        if not rn:
            return  # No work to do, let the outer loop handle the sleep
        
                # Check if questions are already generated for this topic
        questions = (await db.execute(select(Question)
                .filter(Question.topic_id == rn.topic_id)
                )).scalars().all()
                
        if len(questions) == 5:
            # If questions exist, update the topic state and skip generation
            rn.state = "PROMPTS_GENERATED"
            await db.commit()
            return
        # else get the pdf from S3 as bytes
        pdf_bytes = s3_service.get_file_by_url(rn.s3_bucket_url)


        ###############################################
        ### step 2: questions and prompt generation ###
        ###############################################

        # upload the pdf to OpenAI
        pdf_buffer = io.BytesIO(pdf_bytes)
        pdf_buffer.name = "document.pdf"
        uploaded_file = client.files.create(
            file=pdf_buffer,
            purpose="assistants"
        )

        # read the openai system prompt
        with open("app/gen_ai_prompts/open_ai_role_prompt.txt", encoding="utf-8") as f:
            role_prompt = f.read()

        # chat completion with the PDF attached
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": role_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Return {NUM_OF_QUESTION} questions in total of the pdf file that was given to you."},
                        {"type": "file", "file": {"file_id": uploaded_file.id}}
                    ]
                }
            ]
        )

        # cleanup the uploaded file
        client.files.delete(uploaded_file.id)

        # extract the model's outputs
        response = completion.choices[0].message.content

        #####################################################
        ### step 3: extract information from the response ###
        #####################################################
        json_match = re.search(r"```json(.*?)```", response, re.DOTALL)

        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # fallback: return None or raise
            raise Exception("No json found in the response in either formats")

        #################################################
        ### step 4: update question entries in the DB ###
        #################################################
        for category, questions in data.items():
            for q in questions:
                new_question = Question(
                    school_id=rn.school_id,
                    topic_id=rn.topic_id,
                    content=q["question"],
                    options=q.get("options", []),
                    question_type=q["type"],
                    points=1,
                    answer=q["correct_answer"],
                    image_prompt=q['visual_prompt'],
                    image_url=None 
                )
                db.add(new_question) 
        
        # change to next state
        rn.state = "PROMPTS_GENERATED"
        await db.commit()
        return  # Task completed successfully
