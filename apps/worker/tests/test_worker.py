import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("AUTH_MODE", "dev")

from worker.main import WorkerSettings, heartbeat, ping, run_job_entry


async def test_ping() -> None:
    assert await ping({}) == "pong"


async def test_heartbeat_runs() -> None:
    await heartbeat({})


def test_worker_settings_register_jobs() -> None:
    assert ping in WorkerSettings.functions
    assert WorkerSettings.cron_jobs


async def test_worker_knows_every_job_the_api_can_enqueue() -> None:
    import pytest
    from app.core import jobs

    assert run_job_entry in WorkerSettings.functions
    assert {"extract_memories", "summarise_conversation"} <= set(jobs._HANDLERS)
    with pytest.raises(KeyError):
        await run_job_entry({}, "no_such_job", {})
