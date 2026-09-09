from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncEngine

from games_intel.db.engine import is_database_ready
from games_intel.kafka.client import admin_config
from games_intel.settings import Settings

SleepFn = Callable[[float], Awaitable[None]]


async def is_kafka_ready(settings: Settings) -> bool:
    """Best-effort bootstrap probe for API /readyz. Never raises."""
    servers = settings.kafka.bootstrap_servers.strip()
    if not servers:
        return False
    try:
        from aiokafka.admin import AIOKafkaAdminClient
    except ImportError:
        return False
    admin = AIOKafkaAdminClient(**admin_config(settings, client_id="games-intel-readyz"))
    started = False
    try:
        await admin.start()
        started = True
        await admin.list_topics()
    except Exception:
        return False
    finally:
        if started:
            try:
                await admin.close()
            except Exception:
                pass
    return True


async def wait_until_backend_ready(
    engine: AsyncEngine,
    settings: Settings,
    *,
    sleep: SleepFn,
    attempts: int = 30,
    interval_seconds: float = 2.0,
    require_kafka: bool = True,
) -> bool:
    """Wait until Postgres (and optionally Kafka) accept connections."""
    total = max(1, attempts)
    for attempt in range(total):
        db_ok = await is_database_ready(engine)
        kafka_ok = True if not require_kafka else await is_kafka_ready(settings)
        if db_ok and kafka_ok:
            return True
        if attempt + 1 < total:
            await sleep(interval_seconds)
    return False
