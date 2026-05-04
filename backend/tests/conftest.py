"""
Shared pytest fixtures for the test suite.

Uses a single in-memory SQLite database shared across all connections via
StaticPool. Every test is wrapped in a transaction that is rolled back
afterwards, keeping tests isolated without recreating the schema.

The `db_session` fixture owns the connection, transaction, and FastAPI
`get_db` override. The `rollback_after_test` autouse fixture depends on
`db_session`, ensuring every test — even those that never mention
`db_session` explicitly — gets the override installed and the rollback
applied.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from app.db.database import Base, get_db
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

# StaticPool forces every engine.connect() to reuse the same underlying
# connection, so create_tables and all test sessions share one in-memory DB.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(autouse=True, scope="session")
async def create_tables() -> AsyncGenerator[None, None]:
    """Create all tables once for the entire test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Open a connection, begin a savepoint transaction, install the get_db
    override, and yield the session.  The transaction is rolled back on
    teardown, leaving the DB clean for the next test.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_db] = _override_get_db
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
            app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
async def rollback_after_test(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """
    Autouse fixture that simply depends on `db_session`, guaranteeing that
    every test — including those that never request `db_session` directly —
    gets the get_db override installed and the rollback applied.
    """
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
