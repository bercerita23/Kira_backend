from app.celery_app import celery_app
import asyncio
import time
from app.repeated_tasks.question_and_prompt import prompt_generation
from app.repeated_tasks.visuals import visual_generation
from app.repeated_tasks.ready import ready_for_review

@celery_app.task(bind=True)
def worker_loop(self):
    print("[Celery] Worker loop started.", flush=True)
    while True:
        try:
            print("[Celery] Running prompt_generation...", flush=True)
            asyncio.run(prompt_generation())
        except Exception as e:
            print(f"[Celery] Error in prompt_generation: {e}", flush=True)
        try:
            print("[Celery] Running visual_generation...", flush=True)
            asyncio.run(visual_generation())
        except Exception as e:
            print(f"[Celery] Error in visual_generation: {e}", flush=True)
        try:
            print("[Celery] Running ready_for_review...", flush=True)
            asyncio.run(ready_for_review())
        except Exception as e:
            print(f"[Celery] Error in ready_for_review: {e}", flush=True)
        time.sleep(15)
