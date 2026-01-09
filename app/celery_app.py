from celery import Celery
from app.config import settings

celery_app = Celery(
    "kira_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "run-prompt-generation-every-10-seconds": {
            "task": "app.tasks.run_prompt_generation",
            "schedule": 10.0,
        },
        "run-visual-generation-every-10-seconds": {
            "task": "app.tasks.run_visual_generation",
            "schedule": 10.0,
        },
        "run-ready-for-review-every-10-seconds": {
            "task": "app.tasks.run_ready_for_review",
            "schedule": 10.0,
        },
    },
    worker_prefetch_multiplier=1,
)