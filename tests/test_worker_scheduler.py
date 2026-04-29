"""Verify the APScheduler job that replaces Celery Beat.

The scheduler must register exactly one job (`bq_upsert`) targeting
`bigquery_nightly_upsert`, on a daily 00:00 UTC cron, with the misfire/
coalesce settings spelled out in MIGRATION_PLAN.md (so a worker that's
down at midnight catches up within the hour rather than skipping the
day).
"""
import pytest

pytest.importorskip("apscheduler")
pytest.importorskip("google.cloud.bigquery")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")


def test_build_scheduler_registers_daily_midnight_utc_bq_job():
    from apscheduler.triggers.cron import CronTrigger

    from app.worker import build_scheduler

    scheduler = build_scheduler()
    try:
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1, "expected exactly one scheduled job"
        job = jobs[0]

        assert job.id == "bq_upsert"
        assert job.func.__module__ == "app.repeated_tasks.bigquery_upsert"
        assert job.func.__name__ == "bigquery_nightly_upsert"
        assert job.misfire_grace_time == 3600
        assert job.coalesce is True

        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)
        assert str(trigger.timezone) == "UTC"

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["hour"] == "0"
        assert fields["minute"] == "0"
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_worker_module_does_not_boot_on_import():
    """Worker boot is gated on `__name__ == '__main__'` so the module is
    safely importable from tests + tools without spawning the asyncio
    event loop or the scheduler."""
    import app.worker as worker_mod

    assert hasattr(worker_mod, "worker_main")
    assert hasattr(worker_mod, "build_scheduler")
