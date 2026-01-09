
from app.celery_app import celery_app
from app.repeated_tasks.question_and_prompt import prompt_generation
from app.repeated_tasks.visuals import visual_generation
from app.repeated_tasks.ready import ready_for_review
import os
import redis
import time


def get_redis_client():
    redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    # Remove scheme for redis-py if needed
    if redis_url.startswith("redis://"):
        redis_url = redis_url.replace("redis://", "", 1)
    # redis.from_url expects the full URL
    return redis.from_url(os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))

def acquire_lock(r, lock_name, expire=600):
    # Try to acquire lock, expire in 10 min (safety)
    return r.set(lock_name, "1", nx=True, ex=expire)

def release_lock(r, lock_name):
    r.delete(lock_name)

@celery_app.task
def run_prompt_generation():
    import asyncio
    r = get_redis_client()
    lock_name = "lock:run_prompt_generation"
    if not acquire_lock(r, lock_name, expire=600):
        # Lock is held, skip this run
        return
    try:
        asyncio.run(prompt_generation())
    finally:
        release_lock(r, lock_name)


@celery_app.task
def run_visual_generation():
    import asyncio
    r = get_redis_client()
    lock_name = "lock:run_visual_generation"
    if not acquire_lock(r, lock_name, expire=600):
        return
    try:
        asyncio.run(visual_generation())
    finally:
        release_lock(r, lock_name)


@celery_app.task
def run_ready_for_review():
    import asyncio
    r = get_redis_client()
    lock_name = "lock:run_ready_for_review"
    if not acquire_lock(r, lock_name, expire=600):
        return
    try:
        asyncio.run(ready_for_review())
    finally:
        release_lock(r, lock_name)
