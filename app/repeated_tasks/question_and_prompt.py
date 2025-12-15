import asyncio
import io
from openai import OpenAI
from sqlalchemy import select
from app.database.db import get_async_db
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.model.topics import Topic
from app.model.questions import *
from app.model.schools import School
from app.router.aws_s3 import S3Service
from app.config import settings
import re, json
#20 question takes around 5co min to generate
OPENAI_MODEL = "gpt-4o-mini"
s3_service = S3Service()

async def prompt_generation():
    """Process a single topic that needs prompt generation"""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Step 1: Get topic data and release connection immediately
    async with get_async_db() as db:
        rn = (await db.execute(select(Topic)
                .filter(Topic.state == "READY_FOR_GENERATION")
                .order_by(Topic.updated_at.asc())
                )).scalars().first()
        
        if not rn:
            return
        
        # Store necessary data in variables
        topic_id = rn.topic_id
        school_id = rn.school_id
        s3_url = rn.s3_bucket_url
        
        # Get school information
        school = (await db.execute(select(School)
                .filter(School.school_id == school_id)
                )).scalars().first()
        
        if not school:
            raise Exception(f"School not found for topic {topic_id}")
        
        max_questions = school.max_questions
        question_prompt = school.question_prompt
        
        # Check existing questions
        questions = (await db.execute(select(Question)
                .filter(Question.topic_id == topic_id)
                )).scalars().all()
                
        if len(questions) == max_questions:
            rn.state = "PROMPTS_GENERATED"
            await db.commit()
            return
        elif len(questions) > 0:
            for question in questions:
                await db.delete(question)
            await db.commit()
    # CONNECTION RELEASED HERE - no longer holding DB connection
    
    # Step 2: Get PDF from S3 (no DB connection needed)
    pdf_bytes = s3_service.get_file_by_url(s3_url)

    # Step 3: Upload to OpenAI and generate (expensive, no DB connection)
    pdf_buffer = io.BytesIO(pdf_bytes)
    pdf_buffer.name = "document.pdf"
    uploaded_file = client.files.create(
        file=pdf_buffer,
        purpose="assistants"
    )

    # Prepare prompts
    if question_prompt:
        role_prompt = question_prompt
    else:
        with open("app/gen_ai_prompts/open_ai_role_prompt.txt", encoding="utf-8") as f:
            role_prompt = f.read()

    with open("app/gen_ai_prompts/open_ai_role_prompt_instruction.txt", encoding="utf-8") as f:
        instruction_content = f.read()
    
    combined_prompt = role_prompt + "\n\n" + instruction_content

    # Retry logic for question generation
    max_retries = 5
    all_generated_questions = []
    
    for attempt in range(max_retries):
        remaining_questions = max_questions - len(all_generated_questions)
        
        if remaining_questions <= 0:
            break
        
        print(f"Attempt {attempt + 1}/{max_retries}: Requesting {remaining_questions} questions")
        
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": combined_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": f"""CRITICAL INSTRUCTION: You MUST generate EXACTLY {remaining_questions} questions - no more, no less.
                            
Count carefully before responding. The total number of questions across ALL categories must equal EXACTLY {remaining_questions}.

This is attempt {attempt + 1} of {max_retries}. We need precisely {remaining_questions} questions.

Generate the questions from the PDF file provided."""
                        },
                        {"type": "file", "file": {"file_id": uploaded_file.id}}
                    ]
                }
            ]
        )

        response = completion.choices[0].message.content
        json_match = re.search(r"```json(.*?)```", response, re.DOTALL)

        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        try:
            data = json.loads(json_str)
            questions_in_this_attempt = []
            for category, questions in data.items():
                for q in questions:
                    questions_in_this_attempt.append(q)
            
            print(f"Attempt {attempt + 1}: Received {len(questions_in_this_attempt)} questions")
            
            for q in questions_in_this_attempt:
                if len(all_generated_questions) >= max_questions:
                    break
                all_generated_questions.append(q)
            
            print(f"Total accumulated: {len(all_generated_questions)}/{max_questions}")
            
            if len(all_generated_questions) == max_questions:
                print(f"✓ Success! Generated exactly {max_questions} questions")
                break
                
        except json.JSONDecodeError as e:
            print(f"Attempt {attempt + 1}: JSON decode error - {str(e)}")
            continue

    # Generate summary
    summary_response = client.chat.completions.create(
        model=OPENAI_MODEL, 
        messages=[
            {"role": "system", "content": ""}, 
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Return a summary no more than 5000 words on the pdf that was given to you"},
                    {"type": "file", "file": {"file_id": uploaded_file.id}}
                ]
            }
        ]
    )
    
    summary_text = summary_response.choices[0].message.content or ""

    # Cleanup OpenAI file
    client.files.delete(uploaded_file.id)

    # Verify question count
    if len(all_generated_questions) != max_questions:
        raise Exception(
            f"Failed to generate exactly {max_questions} questions after {max_retries} attempts. "
            f"Got {len(all_generated_questions)} questions instead."
        )

    # Step 4: Write results back to DB with NEW connection
    async with get_async_db() as db:
        # Add all questions
        for q in all_generated_questions[:max_questions]:
            new_question = Question(
                school_id=school_id,
                topic_id=topic_id,
                content=q["question"],
                options=q.get("options", []),
                question_type=q["type"],
                points=1,
                answer=q["correct_answer"],
                image_prompt=q['visual_prompt'],
                image_url=None 
            )
            db.add(new_question)
        
        # Update topic state and summary
        topic = await db.get(Topic, topic_id)
        topic.state = "PROMPTS_GENERATED"
        topic.summary = summary_text
        await db.commit()
    # CONNECTION RELEASED HERE
    
    print(f"✓ Successfully saved {max_questions} questions to database")
