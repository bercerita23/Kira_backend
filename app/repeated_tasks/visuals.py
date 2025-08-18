import asyncio
import io
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.database.db import get_async_db
from app.router.aws_s3 import S3Service
from app.model.topics import Topic
from app.model.questions import Question
from app.model.users import User
from google import genai
from google.genai import types
from app.config import settings

async def visual_generation():
    """
    Process one Topic in PROMPTS_GENERATED state:
      - find Questions with image_prompt set and image_url empty
      - generate 1 image per question via Gemini
      - upload PNG bytes to S3
      - write image_url back, flip Topic to VISUALS_GENERATED if any were created
    """
    s3_service = S3Service()

    # Initialize Gemini client
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    model_name = "gemini-2.0-flash-preview-image-generation"

    # Load Gemini role prompt
    try:
        with open("app/gen_ai_prompts/gemini_role_prompt.txt", encoding="utf-8") as f:
            gemini_role_prompt = f.read()
    except FileNotFoundError:
        gemini_role_prompt = "Create an educational image based on the following prompt:"
        print("gemini_role_prompt.txt not found, using default prompt")

    try:
        async with get_async_db() as db:
            # Process ONE topic at a time
            result = await db.execute(
                select(Topic)
                .options(joinedload(Topic.questions))
                .filter(Topic.state == "PROMPTS_GENERATED")
                .order_by(Topic.updated_at.asc())
            )
            topic = result.scalars().first()

            if not topic:
                return  # No work to do, let the outer loop handle scheduling

            print(f"Processing topic {topic.topic_id}: '{topic.topic_name}' (School: {topic.school_id})")

            # Questions that need visuals
            q_need = [
                q for q in topic.questions
                if q.image_prompt and q.image_prompt.strip() and (not q.image_url or not q.image_url.strip())
            ]

            if not q_need:
                return
                

            made_any = False
            school_id = getattr(topic, "school_id", "unknown")
            week_number = getattr(topic, "week_number", 0)

            for i, q in enumerate(q_need, 1):
                try:
                    prompt_text = q.image_prompt.strip()
                    full_prompt = f"{gemini_role_prompt}\n\n{prompt_text}"

                    # Gemini API call (blocking) — can wrap in executor if needed
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(response_modalities=['TEXT','IMAGE'])
                    )

                    # Extract image
                    image_obj = None
                    for part in response.candidates[0].content.parts:
                        if part.inline_data is not None:
                            image_obj = Image.open(io.BytesIO(part.inline_data.data))
                            break

                    if not image_obj:
                        print(f"No image generated for question {q.question_id}")
                        continue

                    # Convert to PNG bytes
                    buf = io.BytesIO()
                    image_obj.save(buf, format="PNG")
                    buf.seek(0)
                    png_bytes = buf.getvalue()

                    # Upload to S3
                    filename = f"t{topic.topic_id}/q{q.question_id}.png"
                    s3_url = s3_service.upload_file_to_s3(
                        file_content=png_bytes,
                        school_id=str(school_id),
                        filename=filename,
                        week_number=week_number,
                        content_type='image/png',
                        folder_prefix='visuals'
                    )

                    if not s3_url:
                        print(f"S3 upload failed for question {q.question_id}")
                        continue

                    q.image_url = s3_url
                    db.add(q)
                    await db.commit()
                    made_any = True

                except Exception as q_err:
                    print(f"Error processing question {q.question_id}: {q_err}")
                    try:
                        await db.rollback()
                    except:
                        pass

            if made_any:
                topic.state = "VISUALS_GENERATED"
                db.add(topic)
                await db.commit()
                print(f"Topic {topic.topic_id} completed - marked as VISUALS_GENERATED")
            else:
                print(f"No images were successfully generated for topic {topic.topic_id}")

    except Exception as e:
        print(f"Error in visual_generation task: {e}")
        await db.rollback()
        raise  # Let the outer loop handle the error
