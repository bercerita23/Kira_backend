"""Behavioural tests for the BigQuery → Postgres nightly upsert.

The function is now invoked by APScheduler (in app.worker) instead of
Celery Beat. These tests verify it still:
  - is a plain callable (no Celery-task wrapping, no `self` parameter),
  - upserts every row returned by BigQuery, then commits exactly once,
  - rolls back and re-raises on DB failure,
  - tolerates an empty BigQuery result,
  - tolerates rows where last_updated_date is NULL.

Mocks isolate us from real BigQuery + Postgres so these run hermetically.
"""
import inspect
from unittest.mock import MagicMock, patch

import pytest

# Skip the whole module gracefully when the worker dependency stack
# is not installed (bare CI). The test_no_celery_residue tests still
# guard the migration in that case.
pytest.importorskip("google.cloud.bigquery")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")


@pytest.fixture
def upsert_module():
    import app.repeated_tasks.bigquery_upsert as mod
    return mod


def _fake_row(user_id="u1", engagement_ms=42, last_updated_date="20260420"):
    row = MagicMock()
    row.user_id = user_id
    row.total_engagement_time_ms = engagement_ms
    row.last_updated_date = last_updated_date
    return row


def _patch_externals(upsert_module, rows, session):
    job = MagicMock()
    job.result.return_value = rows
    client = MagicMock()
    client.query.return_value = job
    return (
        patch.object(upsert_module.bigquery, "Client", return_value=client),
        patch.object(upsert_module, "SessionLocal", return_value=session),
        client,
    )


def test_function_is_a_plain_callable_not_a_celery_task(upsert_module):
    fn = upsert_module.bigquery_nightly_upsert
    assert callable(fn)
    assert not hasattr(fn, "delay"), "Celery decorator still wraps the function"
    assert not hasattr(fn, "apply_async"), "Celery decorator still wraps the function"
    assert list(inspect.signature(fn).parameters) == [], (
        "expected a 0-arg function — `self` should be gone after dropping @celery_app.task"
    )


def test_upserts_each_row_then_commits(upsert_module):
    rows = [
        _fake_row("u1", 100, "20260420"),
        _fake_row("u2", 250, "20260421"),
    ]
    session = MagicMock()
    client_patch, session_patch, client = _patch_externals(upsert_module, rows, session)

    with client_patch as ClientCls, session_patch:
        upsert_module.bigquery_nightly_upsert()

    ClientCls.assert_called_once_with(project="analytics-482304")
    assert client.query.call_count == 1
    assert session.execute.call_count == 2
    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    session.close.assert_called_once()


def test_empty_bigquery_result_still_commits_and_closes(upsert_module):
    session = MagicMock()
    client_patch, session_patch, _ = _patch_externals(upsert_module, [], session)

    with client_patch, session_patch:
        upsert_module.bigquery_nightly_upsert()

    session.execute.assert_not_called()
    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    session.close.assert_called_once()


def test_rollback_on_execute_failure_and_reraises(upsert_module):
    rows = [_fake_row()]
    session = MagicMock()
    session.execute.side_effect = RuntimeError("boom")
    client_patch, session_patch, _ = _patch_externals(upsert_module, rows, session)

    with client_patch, session_patch:
        with pytest.raises(RuntimeError, match="boom"):
            upsert_module.bigquery_nightly_upsert()

    session.commit.assert_not_called()
    session.rollback.assert_called_once()
    session.close.assert_called_once()


def test_null_last_updated_date_is_handled(upsert_module):
    rows = [_fake_row(last_updated_date=None)]
    session = MagicMock()
    client_patch, session_patch, _ = _patch_externals(upsert_module, rows, session)

    with client_patch, session_patch:
        upsert_module.bigquery_nightly_upsert()

    session.execute.assert_called_once()
    session.commit.assert_called_once()
