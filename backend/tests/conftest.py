"""
Shared pytest fixtures for the test suite.

Uses an in-memory SQLite database per test session so tests are isolated
from the dev.db and from each other (each test gets a fresh session via
the overridden get_db dependency).
"""

from __future__ import annotations

import pytest
from app.db.database import Base, get_db
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# In-memory SQLite — recreated fresh for every test module load.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest.fixture(autouse=True, scope="session")
async def create_tables():
    """Create all tables once for the test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def rollback_after_test():
    """
    Wrap each test in a transaction that is rolled back afterwards,
    keeping tests isolated without recreating the schema every time.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        async def override_get_db():
            try:
                yield session
            finally:
                pass  # do not commit – rollback handled below

        app.dependency_overrides[get_db] = override_get_db
        yield
        await session.close()
        await conn.rollback()

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncSession:
    """Yield the same session used by the current test's request cycle."""
    async with TestSessionLocal() as session:
        yield session
