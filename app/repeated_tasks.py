import asyncio
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.router.aws_ses import *
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
#---n---
async def prompt_generation(): 
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)

    while True: 
        try:
            with SessionLocal() as db:
                # find entries that are READY_FOR_GENERATION
                ready_entries = db.query(Topic).filter(Topic.state == "READY_FOR_GENERATION").all()
                
                # get the pdf from S3 

                # quiz and prompt generation 
                
                # change the state to PROMPTS_GENERATED
             
        except Exception as e: 
            print(f"Error in repeated task: {e}")
        finally: 
            db.close()
            await asyncio.sleep(10)

async def visual_generation():
    """
    For each Topic in PROMPTS_GENERATED:
      - find Questions with image_prompt set and image_url empty
      - generate 1 image per question via Gemini
      - upload PNG bytes to S3 using the SAME method/signature as /content-upload
      - write image_url back, and flip Topic to VISUALS_GENERATED if any were created
    """
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    s3_service = S3Service()

    client = genai.Client()
    model_name = "gemini-2.0-flash-preview-image-generation"

    while True:
        try:
            with SessionLocal() as db:  # note the () — this instantiates the session
                topics = (
                    db.query(Topic)
                      .filter(Topic.state == "PROMPTS_GENERATED")
                      .all()
                )

                for topic in topics:
                    # Gather questions that still need visuals
                    q_need = (
                        db.query(Question)
                          .filter(
                              Question.topic_id == topic.topic_id,
                              Question.image_prompt.isnot(None),
                              (Question.image_url.is_(None)) | (Question.image_url == "")
                          )
                          .all()
                    )

                    if not q_need:
                        # Nothing to do for this topic; mark as done
                        topic.state = "VISUALS_GENERATED"
                        db.add(topic)
                        db.commit()
                        continue

                    made_any = False
                    school_id = getattr(topic, "school_id", "unknown")
                    week_number = getattr(topic, "week_number", 0)

                    for q in q_need:
                        try:
                            prompt_text = (q.image_prompt or "").strip()
                            if not prompt_text:
                                continue

                            # 1) Generate image via Gemini
                            response = client.models.generate_content(
                                model=model_name,
                                contents=prompt_text,
                                config=types.GenerateContentConfig(
                                    response_modalities=["TEXT", "IMAGE"]
                                ),
                            )

                            # 2) Extract image bytes → PIL
                            image_obj = None
                            for part in response.candidates[0].content.parts:
                                if getattr(part, "inline_data", None) is not None:
                                    raw = part.inline_data.data
                                    try:
                                        image_obj = Image.open(io.BytesIO(raw))
                                    except Exception:
                                        if isinstance(raw, str):
                                            raw = raw.encode("utf-8")
                                        decoded = base64.b64decode(raw)
                                        image_obj = Image.open(io.BytesIO(decoded))
                                    break

                            if image_obj is None:
                                print(f"[visual_generation] No image for q={q.question_id}")
                                continue

                            # 3) Convert to PNG bytes
                            buf = io.BytesIO()
                            image_obj.save(buf, format="PNG")
                            buf.seek(0)
                            png_bytes = buf.getvalue()

                            # 4) Upload to S3 the SAME way as /content-upload
                            #    key becomes: {school_id}/{week_number}/visuals/t{topic}/q{q}.png
                            filename = f"visuals/t{topic.topic_id}/q{q.question_id}.png"
                            s3_url = s3_service.upload_file_to_s3(
                                file_content=png_bytes,
                                school_id=school_id,
                                filename=filename,
                                week_number=week_number
                            )

                            if not s3_url:
                                print(f"[visual_generation] S3 upload failed q={q.question_id}")
                                continue

                            # 5) Save URL & commit each question
                            q.image_url = s3_url
                            db.add(q)
                            db.commit()
                            made_any = True

                        except Exception as q_err:
                            db.rollback()
                            print(f"[visual_generation] question {q.question_id} error: {q_err}")

                    if made_any:
                        topic.state = "VISUALS_GENERATED"
                        db.add(topic)
                        db.commit()

            await asyncio.sleep(10)

        except Exception as e:
            print(f"Error in repeated task (visual_generation): {e}")
            await asyncio.sleep(10)


async def ready_for_review():
    """Scan for visuals generated entries, change their state to ready for review and send them email 
    """
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    while True:
        try:
            with SessionLocal() as db:
                # find entries that are VISUALS_GENERATED
                ready_entries = db.query(Topic).filter(Topic.state == "VISUALS_GENERATED").all()

                # change the state to READY_FOR_REVIEW
                for ready_entry in ready_entries:
                    ready_entry.state = "READY_FOR_REVIEW"

                # send admin notification to review
                school_ids = {re.school_id for re in ready_entries}
                if school_ids:
                    admin_emails = (
                        db.query(User.email)
                        .filter(User.is_admin == True, User.school_id.in_(school_ids))
                        .all()
                    )
                    for email in admin_emails:
                        send_ready_notification(email[0])

                db.commit()

            await asyncio.sleep(10)

        except Exception as e:
            print(f"Error in repeated task: {e}")
            # rollback just in case
            try:
                db.rollback()
            except:
                pass
            await asyncio.sleep(10)


# async def hello_world():
#     """Run the repeated task every 10 seconds"""
#     while True:
#         try:
#             print("Hello World every 10 sec")
#             await asyncio.sleep(10)  # 10 seconds for testing
#         except Exception as e:
#             print(f"Error in repeated task: {e}")
#             await asyncio.sleep(10) 
# 
# async def hello_sky():
#     """Run the repeated task every 10 seconds"""
#     while True:
#         try:
#             print("Hello Sky every 5 sec")
#             await asyncio.sleep(5)  # 10 seconds for testing
#         except Exception as e:
#             print(f"Error in repeated task: {e}")
#             await asyncio.sleep(5) 