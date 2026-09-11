"""Points the whole test session at a separate Postgres database.

Must set DATABASE_URL before anything imports app.core.config (which builds
the Settings singleton from .env) or app.database (which builds the engine
from that singleton) — pytest loads conftest.py before collecting test
modules, so this runs first as long as nothing above does an `app.*` import.
"""

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/openbanking_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.database import Base, engine  # noqa: E402

# Import every model module so Base.metadata is complete before create_all —
# mirrors migrations/env.py's own import list.
from app.features.accounts import models as _accounts_models  # noqa: E402,F401
from app.features.auth import models as _auth_models  # noqa: E402,F401
from app.features.connections import models as _connections_models  # noqa: E402,F401


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_database() -> None:
    admin_url, _, dbname = TEST_DATABASE_URL.rpartition("/")
    admin_url = f"{admin_url}/postgres"

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": dbname}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    await admin_engine.dispose()

    # Schema is built straight from the ORM models rather than running
    # Alembic — simplest way to keep the test DB structurally in sync.
    # ponytail: if models and migrations ever drift, switch this to
    # `alembic upgrade head` against TEST_DATABASE_URL instead.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
