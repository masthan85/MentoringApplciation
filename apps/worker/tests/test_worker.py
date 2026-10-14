import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("AUTH_MODE", "dev")

from worker.main import WorkerSettings, heartbeat, ping


async def test_ping() -> None:
    assert await ping({}) == "pong"


async def test_heartbeat_runs() -> None:
    await heartbeat({})


def test_worker_settings_register_jobs() -> None:
    assert ping in WorkerSettings.functions
    assert WorkerSettings.cron_jobs
