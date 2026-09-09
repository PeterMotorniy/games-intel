from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from alembic import command
from alembic.config import Config

from games_intel.db.engine import async_database_url

_PACKAGE_DIR = Path(__file__).resolve().parent
ALEMBIC_INI = _PACKAGE_DIR / "alembic.ini"


def _alembic_config(*, database_url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_INI))
    if database_url:
        async_url = async_database_url(database_url)
        config.set_main_option("sqlalchemy.url", async_url.replace("%", "%%"))
        config.cmd_opts = Namespace(x=["database_url=" + database_url])
    return config


def upgrade_head(*, database_url: str | None = None) -> None:
    command.upgrade(_alembic_config(database_url=database_url), "head")


def downgrade_base(*, database_url: str | None = None) -> None:
    command.downgrade(_alembic_config(database_url=database_url), "base")
