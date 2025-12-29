from app.celery_app import celery_app
from app.repeated_tasks.question_and_prompt import prompt_generation
from app.repeated_tasks.visuals import visual_generation
from app.repeated_tasks.ready import ready_for_review

@celery_app.task
def run_prompt_generation():
    import asyncio
    asyncio.run(prompt_generation())

@celery_app.task
def run_visual_generation():
    import asyncio
    asyncio.run(visual_generation())

@celery_app.task
def run_ready_for_review():
    import asyncio
    asyncio.run(ready_for_review())
