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
    
    # Load Gemini role prompt
    try:
        with open("app/gen_ai_prompts/gemini_role_prompt.txt", encoding="utf-8") as f:
            gemini_role_prompt = f.read()
    except FileNotFoundError:
        gemini_role_prompt = "Create an educational image based on the following prompt:"
        print("[visual_generation] Warning: gemini_role_prompt.txt not found, using default prompt")

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

                            # Combine role prompt with image prompt
                            full_prompt = f"{gemini_role_prompt}\n\n{prompt_text}"

                            # 1) Generate image via Gemini using enhanced prompt
                            response = client.models.generate_content(
                                model=model_name,
                                contents=full_prompt,
                                config=types.GenerateContentConfig(
                                    response_modalities=["TEXT", "IMAGE"]
                                ),
                            )

                            # 2) Extract image using same method as my_gemini.py
                            image_obj = None
                            for part in response.candidates[0].content.parts:
                                if part.inline_data is not None:
                                    # Use BytesIO directly like my_gemini.py
                                    image_obj = Image.open(io.BytesIO(part.inline_data.data))
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
                            filename = f"t{topic.topic_id}/q{q.question_id}.png"
                            s3_url = s3_service.upload_file_to_s3(
                                file_content=png_bytes,
                                school_id=school_id,
                                filename=filename,
                                week_number=week_number,
                                content_type='image/png',
                                folder_prefix='visuals'
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