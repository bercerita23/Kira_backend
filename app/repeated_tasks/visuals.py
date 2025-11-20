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
    model_name = "gemini-2.5-flash-preview-image"

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
                max_retries = 3  # Maximum number of retry attempts
                retry_count = 0
                image_generated = False
                
                while retry_count < max_retries and not image_generated:
                    try:
                        retry_count += 1
                        prompt_text = q.image_prompt.strip()
                        full_prompt = f"{gemini_role_prompt}\n\n{prompt_text}"

                        print(f"Generating image {i}/{len(q_need)} for question {q.question_id} (attempt {retry_count}/{max_retries})")

                        # Gemini API call (blocking) — can wrap in executor if needed
                        response = client.models.generate_content(
                            model=model_name,
                            contents=full_prompt,
                            config=types.GenerateContentConfig(response_modalities=['TEXT','IMAGE'])
                        )

                        # Extract image
                        image_obj = None
                        if response.candidates and len(response.candidates) > 0 and response.candidates[0].content:
                            for part in response.candidates[0].content.parts:
                                if part.inline_data is not None and part.inline_data.data:
                                    image_obj = Image.open(io.BytesIO(part.inline_data.data))
                                    break
                            
                        if not image_obj:
                            print(f"No image generated for question {q.question_id} (attempt {retry_count}/{max_retries})")
                            if retry_count < max_retries:
                                print(f"Retrying image generation...")
                                await asyncio.sleep(2)  # Wait before retry
                                continue  # Retry image generation
                            else:
                                print(f"Failed to generate image after {max_retries} attempts")
                                break  # Move to next question
                        
                        # Convert to PNG bytes
                        buf = io.BytesIO()
                        image_obj.save(buf, format="PNG")
                        buf.seek(0)
                        png_bytes = buf.getvalue()

                        # Validate image bytes
                        if not png_bytes or len(png_bytes) == 0:
                            print(f"Generated image is empty for question {q.question_id} (attempt {retry_count}/{max_retries})")
                            if retry_count < max_retries:
                                print(f"Retrying due to empty image...")
                                await asyncio.sleep(2)
                                continue
                            else:
                                print(f"Failed to generate valid image after {max_retries} attempts")
                                break

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
                            print(f"S3 upload failed for question {q.question_id} (attempt {retry_count}/{max_retries})")
                            if retry_count < max_retries:
                                print(f"Retrying S3 upload...")
                                await asyncio.sleep(2)
                                continue  # Retry the whole process
                            else:
                                print(f"Failed to upload after {max_retries} attempts")
                                break
                        
                        # Success!
                        q.image_url = s3_url
                        db.add(q)
                        await db.commit()
                        made_any = True
                        image_generated = True
                        print(f"Successfully processed question {q.question_id} on attempt {retry_count}")

                    except Exception as q_err:
                        print(f"Error processing question {q.question_id} (attempt {retry_count}/{max_retries}): {q_err}")
                        if retry_count < max_retries:
                            print(f"Retrying due to error...")
                            await asyncio.sleep(2)
                            try:
                                await db.rollback()
                            except:
                                pass
                        else:
                            print(f"Failed after {max_retries} attempts due to errors")
                            try:
                                await db.rollback()
                            except:
                                pass
                            break

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
        raise  
