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
        
        # Get school information for max_questions and question_prompt
        school = (await db.execute(select(School)
                .filter(School.school_id == rn.school_id)
                )).scalars().first()
        
        if not school:
            raise Exception(f"School not found for topic {rn.topic_id}")
        
        max_questions = school.max_questions
        
        # Check if questions are already generated for this topic
        questions = (await db.execute(select(Question)
                .filter(Question.topic_id == rn.topic_id)
                )).scalars().all()
                
        if len(questions) == max_questions:
            # If exact number of questions exist, update the topic state and skip generation
            rn.state = "PROMPTS_GENERATED"
            await db.commit()
            return
        elif len(questions) > 0:
            # If wrong number of questions exist, clear them first
            for question in questions:
                await db.delete(question)
        await db.commit()

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

        # Use school-specific prompt or fallback to default file
        if school.question_prompt:
            role_prompt = school.question_prompt
        else:
            # read the openai system prompt from file
            with open("app/gen_ai_prompts/open_ai_role_prompt.txt", encoding="utf-8") as f:
                role_prompt = f.read()

        # Always append the instruction content
        with open("app/gen_ai_prompts/open_ai_role_prompt_instruction.txt", encoding="utf-8") as f:
            instruction_content = f.read()
        
        # Combine role prompt with instructions
        combined_prompt = role_prompt + "\n\n" + instruction_content

        # Retry logic for exact question generation
        max_retries = 5
        all_generated_questions = []
        
        for attempt in range(max_retries):
            remaining_questions = max_questions - len(all_generated_questions)
            
            if remaining_questions <= 0:
                break
            
            print(f"Attempt {attempt + 1}/{max_retries}: Requesting {remaining_questions} questions")
            
            # chat completion with the PDF attached - STRONGER PROMPT
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
                
                # Extract questions from response
                questions_in_this_attempt = []
                for category, questions in data.items():
                    for q in questions:
                        questions_in_this_attempt.append(q)
                
                print(f"Attempt {attempt + 1}: Received {len(questions_in_this_attempt)} questions")
                
                # Add questions up to our limit
                for q in questions_in_this_attempt:
                    if len(all_generated_questions) >= max_questions:
                        break
                    all_generated_questions.append(q)
                
                print(f"Total accumulated: {len(all_generated_questions)}/{max_questions}")
                
                # If we have exactly the right number, break
                if len(all_generated_questions) == max_questions:
                    print(f"✓ Success! Generated exactly {max_questions} questions")
                    break
                    
            except json.JSONDecodeError as e:
                print(f"Attempt {attempt + 1}: JSON decode error - {str(e)}")
                continue

        # Generate summary (only once)
        summary = client.chat.completions.create(
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

        rn.summary = summary.choices[0].message.content or ""
        await db.commit()

        # cleanup the uploaded file
        client.files.delete(uploaded_file.id)

        # Verify we have EXACTLY the right number of questions
        if len(all_generated_questions) != max_questions:
            raise Exception(
                f"Failed to generate exactly {max_questions} questions after {max_retries} attempts. "
                f"Got {len(all_generated_questions)} questions instead."
            )

        #################################################
        ### step 4: update question entries in the DB ###
        #################################################
        # Take EXACTLY max_questions (in case we somehow got more)
        for q in all_generated_questions[:max_questions]:
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
        
        print(f"✓ Successfully saved {max_questions} questions to database")
        return  # Task completed successfully
