"""Basic smoke tests for the FastAPI app."""

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_openapi_docs(client: AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Language Flashcards API"
