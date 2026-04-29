import asyncio
from typing import Callable, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.log import get_logger
from app.repeated_tasks.bigquery_upsert import bigquery_nightly_upsert
from app.repeated_tasks.question_and_prompt import prompt_generation
from app.repeated_tasks.ready import ready_for_review
from app.repeated_tasks.visuals import visual_generation

logger = get_logger("worker", "INFO")
# Locks to prevent concurrent processing of same task
task_locks: Dict[str, asyncio.Lock] = {
    "prompt_generation": asyncio.Lock(),
    "ready_for_review": asyncio.Lock(),
    "visual_generation": asyncio.Lock(),
}

async def run_task(name: str, func: Callable, interval: int = 30):
    """
    Run a background task periodically, ensuring only one instance
    of this task is running at a time.
    """
    consecutive_errors = 0
    max_backoff = 300  # 5 minutes

    while True:
        lock = task_locks[name]
        if lock.locked():
            await asyncio.sleep(interval)
            continue

        try:
            async with lock:
                try:
                    await func()
                    consecutive_errors = 0
                except Exception as e:
                    consecutive_errors += 1
                    error_msg = str(e)
                    print(f"Error in {name}: {error_msg}")

                    if "remaining connection slots are reserved" in error_msg:
                        backoff = min(interval * (2 ** consecutive_errors), max_backoff)
                        print(f"{name}: Connection pool exhausted, backing off for {backoff}s")
                        await asyncio.sleep(backoff)
                        continue

            await asyncio.sleep(interval)

        except Exception as outer_e:
            print(f"Critical error in task runner for {name}: {outer_e}")
            await asyncio.sleep(interval)


def build_scheduler() -> AsyncIOScheduler:
    """Build the in-process APScheduler that replaces Celery + Redis broker.

    `bigquery_nightly_upsert` is a sync function; APScheduler runs it in its
    default thread-pool executor, so the existing sync BigQuery + SQLAlchemy
    code works unchanged. The job is idempotent (INSERT ... ON CONFLICT
    DO UPDATE), so missed runs are auto-recovered the next day.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        bigquery_nightly_upsert,
        CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="bq_upsert",
        misfire_grace_time=3600,
        coalesce=True,
    )
    return scheduler


async def worker_main():
    """Run generation tasks concurrently with the same logic as before"""
    logger.info(f"Worker starting in {settings.ENV} mode...")
    logger.info("=" * 50)
    logger.info("Running tasks concurrently:")
    logger.info("  - PromptGen (every 10s)")
    logger.info("  - VisualGen (every 10s)")
    logger.info("  - ReadyCheck (every 10s)")
    logger.info("  - BQ nightly upsert (00:00 UTC)")
    logger.info("=" * 50)

    scheduler = build_scheduler()
    scheduler.start()

    await asyncio.gather(
        run_task("prompt_generation", prompt_generation, 10),
        run_task("ready_for_review", ready_for_review, 10),
        run_task("visual_generation", visual_generation, 10),
    )


if __name__ == "__main__":  # pragma: no cover
    try:
        logger.info("WORKER BOOTING")
        asyncio.run(worker_main())
    except Exception:
        import traceback
        logger.critical("WORKER CRASHED:")
        logger.critical(traceback.format_exc())
        traceback.print_exc()
        raise
