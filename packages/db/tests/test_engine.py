from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from games_intel.db.engine import create_engine as make_engine
from games_intel.db.engine import is_database_ready, wait_until_database_ready
from games_intel.settings import Settings


async def test_wait_until_database_ready_succeeds(engine: AsyncEngine) -> None:
    assert await wait_until_database_ready(engine, attempts=1, interval_seconds=0) is True


async def test_wait_until_database_ready_retries_then_fails() -> None:
    broken = make_engine(
        Settings(),
        url="postgresql+asyncpg://games:bad@127.0.0.1:1/missing",
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    try:
        assert await is_database_ready(broken) is False
        ok = await wait_until_database_ready(
            broken,
            attempts=2,
            interval_seconds=0.01,
            sleep=fake_sleep,
        )
        assert ok is False
        assert sleeps == [0.01]
    finally:
        await broken.dispose()
