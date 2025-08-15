import asyncio
import io
from openai import OpenAI
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.model.topics import Topic
from app.router.aws_s3 import S3Service
from app.config import settings

OPENAI_MODEL = "gpt-4o-mini"
NUM_OF_QUESTION = 5
s3_service = S3Service()

async def prompt_generation():
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    while True:
        try:
            with SessionLocal() as db:
                ###########################################################
                ### step 1: get the entry in READY_FOR_GENERATION state ###
                ###########################################################
                rn = (
                    db.query(Topic)
                    .filter(Topic.state == "READY_FOR_GENERATION")
                    .order_by(Topic.updated_at.asc())  # FIFO
                    .first()
                )

                # if no entry at the state, return the control back to the loop after 20 secs
                if not rn:
                    await asyncio.sleep(20)
                    continue
                
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
                                {"type": "text", "text": f"Return {NUM_OF_QUESTION} questions in total about that pdf."},
                                {"type": "file", "file": {"file_id": uploaded_file.id}}
                            ]
                        }
                    ]
                )

                # cleanup the uploaded file
                client.files.delete(uploaded_file.id)

                # extract the model's output
                # TODO: comment out this line
                print(completion.choices[0].message.content)

                #####################################################
                ### step 3: extract information from the response ###
                #####################################################
                # TODO: use regular expression

                #################################################
                ### step 4: update question entries in the DB ###
                #################################################

                # TODO: update entries in the db
                
                # change to next state
                rn.state = "PROMPTS_GENERATED"
                db.commit()

            await asyncio.sleep(20)

        except Exception as e:
            print(f"Error in prompt generation: {e}")
            try:
                db.rollback()
            except:
                pass
            await asyncio.sleep(20)
