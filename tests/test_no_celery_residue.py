"""Lock in the Redis/Celery removal so it cannot silently regress.

These tests read files directly instead of importing app modules, so they
run under bare `pytest` (no app dependencies installed). That keeps them
useful as a tripwire even in minimal CI setups.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (REPO / rel_path).read_text()


def test_celery_files_are_gone():
    for path in ["app/celery_app.py", "app/start_celery.py", "app/tasks.py"]:
        assert not (REPO / path).exists(), f"{path} should have been deleted"


def test_no_celery_or_redis_pinned_in_requirements():
    for req in ["requirements.web.txt", "requirements.worker.txt"]:
        for line in _read(req).splitlines():
            stripped = line.strip().lower()
            assert not stripped.startswith("celery"), f"{req} still pins celery"
            assert not stripped.startswith("redis"), f"{req} still pins redis"


def test_apscheduler_still_pinned_in_requirements():
    for req in ["requirements.web.txt", "requirements.worker.txt"]:
        assert "APScheduler==" in _read(req), f"{req} dropped APScheduler"


def test_no_celery_env_vars_in_compose_files():
    for compose in ["docker-compose.yml", "docker-compose.worker.yml"]:
        contents = _read(compose)
        assert "CELERY_BROKER_URL" not in contents, f"{compose} still references CELERY_BROKER_URL"
        assert "CELERY_RESULT_BACKEND" not in contents, f"{compose} still references CELERY_RESULT_BACKEND"


def test_no_celery_worker_service_in_compose():
    assert "celery_worker:" not in _read("docker-compose.worker.yml")


def test_worker_compose_propagates_google_application_credentials():
    """The BQ client in app.repeated_tasks.bigquery_upsert needs this env
    var passed through to the worker container; previously it was set only
    on the now-removed celery_worker service."""
    assert "GOOGLE_APPLICATION_CREDENTIALS=" in _read("docker-compose.worker.yml")


def test_pydantic_settings_drops_celery_fields():
    """If these stay in Settings, the app fails Pydantic validation at boot."""
    contents = _read("app/config.py")
    assert "CELERY_BROKER_URL" not in contents
    assert "CELERY_RESULT_BACKEND" not in contents
