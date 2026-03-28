"""
Alembic environment – supports both async (online) and offline modes.

The DATABASE_URL is read from the app's Settings so it always matches
whatever the running application is using.
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make sure `app` is importable when alembic is run from the backend/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import all models so their tables are registered on Base.metadata.
import app.models  # noqa: E402, F401
from app.config import settings  # noqa: E402
from app.db.database import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the URL from app settings (picks up DATABASE_URL env var).
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migration (generates SQL without a live connection)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migration (uses a live async engine)
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
