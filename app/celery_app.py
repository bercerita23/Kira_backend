from celery import Celery
from app.config import settings
from celery.schedules import crontab


celery_app = Celery(
    "kira_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.autodiscover_tasks(["app"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    'bq_upsert': {
        'task': 'app.tasks.bigquery_nightly_upsert',
        'schedule': crontab(minute=0, hour=0)
    },
}

