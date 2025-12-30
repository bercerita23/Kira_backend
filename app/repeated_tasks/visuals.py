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
from app.model.schools import School
from google import genai
from google.genai import types
from app.config import settings
from app.log import get_logger

logger = get_logger("visual_generation", "INFO")

async def visual_generation():
    """
    Process one Topic in PROMPTS_GENERATED state:
      - find Questions with image_prompt set and image_url empty
      - generate 1 image per question via Gemini
      - upload PNG bytes to S3
      - write image_url back, flip Topic to VISUALS_GENERATED if any were created
    """
    s3_service = S3Service()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    model_name = "gemini-2.5-flash-image"

    try:
        # Step 1: Get topic and questions data, release connection quickly
        async with get_async_db() as db:
            result = await db.execute(
                select(Topic)
                .filter(Topic.state == "PROMPTS_GENERATED")
                .order_by(Topic.updated_at.asc())
            )
            topic = result.scalars().first()
            
            if not topic:
                return
            
            # Store necessary data
            topic_id = topic.topic_id
            topic_name = topic.topic_name
            school_id = topic.school_id
            week_number = topic.week_number
            
            logger.info(f"Processing topic {topic_id}: '{topic_name}' (School: {school_id})")
            
            # Get school information
            school_result = await db.execute(
                select(School).filter(School.school_id == school_id)
            )
            school = school_result.scalars().first()
            
            if not school:
                raise Exception(f"School not found: {school_id}")
            
            image_prompt_template = school.image_prompt
            
            # Get questions needing images
            questions_result = await db.execute(
                select(Question)
                .filter(
                    Question.topic_id == topic_id,
                    Question.image_prompt.isnot(None),
                    Question.image_url.is_(None)
                )
            )
            questions = questions_result.scalars().all()
            
            if not questions:
                # No questions need images, update state
                topic_obj = await db.get(Topic, topic_id)
                topic_obj.state = "VISUALS_GENERATED"
                await db.commit()
                return
            
            # Store question data
            questions_data = [
                {
                    "question_id": q.question_id,
                    "image_prompt": q.image_prompt.strip()
                }
                for q in questions
                if q.image_prompt and q.image_prompt.strip()
            ]
        # CONNECTION RELEASED HERE - no longer holding DB connection
        
        # Load prompt template
        if image_prompt_template:
            gemini_role_prompt = image_prompt_template
        else:
            try:
                with open("app/gen_ai_prompts/imagen_prompt.txt", encoding="utf-8") as f:
                    gemini_role_prompt = f.read()
            except FileNotFoundError:
                gemini_role_prompt = "Create an educational image based on the following prompt:"
                logger.warning("imagen_prompt.txt not found, using default prompt")
        
        # Step 2: Generate images (expensive operation, no DB connection)
        generated_images = []
        
        for i, q_data in enumerate(questions_data, 1):
            max_retries = 3
            retry_count = 0
            image_generated = False
            
            while retry_count < max_retries and not image_generated:
                try:
                    retry_count += 1
                    
                    # Build final prompt
                    if "{image_prompt}" in gemini_role_prompt:
                        full_prompt = gemini_role_prompt.replace("{image_prompt}", q_data["image_prompt"])
                    else:
                        full_prompt = f"{gemini_role_prompt}\n\n{q_data['image_prompt']}"
                    
                    logger.info(f"Generating image {i}/{len(questions_data)} for question {q_data['question_id']} (attempt {retry_count}/{max_retries})")
                    
                    # Generate image with Gemini
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE'])
                    )
                    
                    # Extract image
                    image_obj = None
                    if response.candidates and len(response.candidates) > 0 and response.candidates[0].content:
                        for part in response.candidates[0].content.parts:
                            if part.inline_data is not None and part.inline_data.data:
                                image_obj = Image.open(io.BytesIO(part.inline_data.data))
                                break
                    
                    if not image_obj:
                        logger.warning(f"No image generated for question {q_data['question_id']} (attempt {retry_count}/{max_retries})")
                        if retry_count < max_retries:
                            await asyncio.sleep(2)
                            continue
                        else:
                            break
                    
                    # Convert to PNG bytes
                    buf = io.BytesIO()
                    image_obj.save(buf, format="PNG")
                    buf.seek(0)
                    png_bytes = buf.getvalue()
                    
                    # Validate image bytes
                    if not png_bytes or len(png_bytes) == 0:
                        logger.warning(f"Generated image is empty for question {q_data['question_id']} (attempt {retry_count}/{max_retries})")
                        if retry_count < max_retries:
                            await asyncio.sleep(2)
                            continue
                        else:
                            break
                    
                    # Upload to S3
                    filename = f"t{topic_id}/q{q_data['question_id']}.png"
                    s3_url = s3_service.upload_file_to_s3(
                        file_content=png_bytes,
                        school_id=str(school_id),
                        filename=filename,
                        week_number=week_number,
                        content_type='image/png',
                        folder_prefix='visuals'
                    )
                    
                    if not s3_url:
                        logger.error(f"S3 upload failed for question {q_data['question_id']} (attempt {retry_count}/{max_retries})")
                        if retry_count < max_retries:
                            await asyncio.sleep(2)
                            continue
                        else:
                            break
                    
                    # Success!
                    generated_images.append({
                        "question_id": q_data["question_id"],
                        "image_url": s3_url
                    })
                    image_generated = True
                    logger.info(f"Successfully processed question {q_data['question_id']} on attempt {retry_count}")
                    
                except Exception as q_err:
                    logger.error(f"Error processing question {q_data['question_id']} (attempt {retry_count}/{max_retries}): {q_err}")
                    if retry_count < max_retries:
                        await asyncio.sleep(2)
                    else:
                        break
        
        # Step 3: Write results back to DB with NEW connection
        if generated_images:
            async with get_async_db() as db:
                # Update questions with image URLs
                for img_data in generated_images:
                    question = await db.get(Question, img_data["question_id"])
                    if question:
                        question.image_url = img_data["image_url"]
                        db.add(question)
                
                # Update topic state
                topic = await db.get(Topic, topic_id)
                topic.state = "VISUALS_GENERATED"
                db.add(topic)
                
                await db.commit()
            # CONNECTION RELEASED HERE
            
            logger.info(f"Topic {topic_id} completed - marked as VISUALS_GENERATED with {len(generated_images)} images")
        else:
            logger.warning(f"No images were successfully generated for topic {topic_id}")
            
    except Exception as e:
        logger.error(f"Error in visual_generation task: {e}")
        raise
