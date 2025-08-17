import asyncio
from sqlalchemy.orm import joinedload
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
    print(" Visual generation task started!")
    
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    s3_service = S3Service()

    # Initialize Gemini client exactly like my_gemini.py but with explicit API key
    try:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        model_name = "gemini-2.0-flash-preview-image-generation"
        print(" Gemini client initialized successfully")
    except Exception as e:
        print(f" Failed to initialize Gemini client: {e}")
        return

    # Load Gemini role prompt
    try:
        with open("app/gen_ai_prompts/gemini_role_prompt.txt", encoding="utf-8") as f:
            gemini_role_prompt = f.read()
        print(" Loaded gemini_role_prompt.txt")
    except FileNotFoundError:
        gemini_role_prompt = "Create an educational image based on the following prompt:"
        print(" gemini_role_prompt.txt not found, using default prompt")

    iteration_count = 0
    while True:
        iteration_count += 1
        
        
        try:
            with SessionLocal() as db:
                # Process ONE topic at a time with joinedload
                topic = (
                    db.query(Topic)
                    .options(joinedload(Topic.questions))
                    .filter(Topic.state == "PROMPTS_GENERATED")
                    .order_by(Topic.updated_at.asc())  # FIFO like prompt generation
                    .first()
                )

                if not topic:
                    
                    await asyncio.sleep(10)
                    continue

                print(f" Processing topic {topic.topic_id}: '{topic.topic_name}' (School: {topic.school_id})")

                # Gather questions that still need visuals - fix the filtering logic
                q_need = []
                for q in topic.questions:
                    if (q.image_prompt and 
                        q.image_prompt.strip() and 
                        (q.image_url is None or q.image_url == "" or q.image_url.strip() == "")):
                        q_need.append(q)

                print(f" Topic has {len(topic.questions)} total questions, {len(q_need)} need visuals")

                if not q_need:
                    # Nothing to do for this topic; mark as done
                    topic.state = "VISUALS_GENERATED"
                    db.add(topic)
                    db.commit()
                    print(f" Topic {topic.topic_id} marked as VISUALS_GENERATED (no questions needed visuals)")
                    continue

                print(f" Found {len(q_need)} questions needing visuals in topic {topic.topic_id}")

                made_any = False
                school_id = getattr(topic, "school_id", "unknown")
                week_number = getattr(topic, "week_number", 0)

                for i, q in enumerate(q_need, 1):
                    try:
                        prompt_text = q.image_prompt.strip()
                        print(f" Generating image {i}/{len(q_need)} for question {q.question_id}")
                        print(f" Image prompt: {prompt_text[:100]}...")

                        # Combine role prompt with image prompt
                        full_prompt = f"{gemini_role_prompt}\n\n{prompt_text}"

                        # 1) Generate image via Gemini - exactly like my_gemini.py
                        print(f"🤖 Calling Gemini API for question {q.question_id}")
                        response = client.models.generate_content(
                            model=model_name,
                            contents=full_prompt,
                            config=types.GenerateContentConfig(
                                response_modalities=['TEXT', 'IMAGE']
                            )
                        )

                        # 2) Extract image data - exactly like my_gemini.py
                        image_obj = None
                        for part in response.candidates[0].content.parts:
                            if part.text is not None:
                                print(f" Gemini response text: {part.text}")
                            elif part.inline_data is not None:
                                image_obj = Image.open(io.BytesIO(part.inline_data.data))
                                break

                        if image_obj is None:
                            print(f" No image generated for question {q.question_id}")
                            continue

                        print(f"Image generated successfully for question {q.question_id} ({image_obj.size})")

                        # 3) Convert to PNG bytes
                        buf = io.BytesIO()
                        image_obj.save(buf, format="PNG")
                        buf.seek(0)
                        png_bytes = buf.getvalue()
                        print(f" PNG conversion complete: {len(png_bytes)} bytes")

                        # 4) Upload to S3 the SAME way as /content-upload
                        filename = f"t{topic.topic_id}/q{q.question_id}.png"
                        print(f" Uploading to S3: {filename}")
                        
                        s3_url = s3_service.upload_file_to_s3(
                            file_content=png_bytes,
                            school_id=str(school_id),
                            filename=filename,
                            week_number=week_number,
                            content_type='image/png',
                            folder_prefix='visuals'
                        )

                        if not s3_url:
                            print(f" S3 upload failed for question {q.question_id}")
                            continue

                        # 5) Save URL & commit each question
                        q.image_url = s3_url
                        db.add(q)
                        db.commit()
                        made_any = True
                        print(f" Successfully processed question {q.question_id}")
                        print(f" Image URL: {s3_url}")

                    except Exception as q_err:
                        print(f" Error processing question {q.question_id}: {str(q_err)}")
                        try:
                            db.rollback()
                        except:
                            pass

                # Mark topic as complete if any images were generated
                if made_any:
                    topic.state = "VISUALS_GENERATED"
                    db.add(topic)
                    db.commit()
                    print(f" Topic {topic.topic_id} completed - marked as VISUALS_GENERATED")
                else:
                    print(f" No images were successfully generated for topic {topic.topic_id}")

            await asyncio.sleep(5)  # Shorter sleep since we're processing one at a time

        except Exception as e:
            print(f" Error in visual_generation task (iteration {iteration_count}): {str(e)}")
            import traceback
            print(f" Traceback: {traceback.format_exc()}")
            await asyncio.sleep(10)