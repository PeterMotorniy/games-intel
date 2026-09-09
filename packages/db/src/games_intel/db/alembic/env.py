"""Alembic environment. Database URL comes from settings or -x database_url."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from games_intel.db.engine import async_database_url
from games_intel.db.models import Base
from games_intel.settings import load_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configured_url() -> str:
    x_args: dict[str, Any] = context.get_x_argument(as_dictionary=True)
    explicit = x_args.get("database_url") or x_args.get("url")
    if explicit:
        return async_database_url(str(explicit))
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and not ini_url.startswith("driver://"):
        return async_database_url(ini_url)
    secret = load_settings().database.url.get_secret_value()
    if not secret:
        msg = "database.url is empty; pass -x database_url=... or set settings"
        raise RuntimeError(msg)
    return async_database_url(secret)


def run_migrations_offline() -> None:
    url = _configured_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_configured_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
