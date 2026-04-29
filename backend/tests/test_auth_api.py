"""Integration tests for the /auth HTTP endpoints."""

from __future__ import annotations

from httpx import AsyncClient, Response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def register(client: AsyncClient, email: str = "test@example.com", password: str = "password123") -> Response:
    return await client.post("/auth/register", json={"email": email, "password": password})


async def login(client: AsyncClient, email: str = "test@example.com", password: str = "password123") -> Response:
    return await client.post("/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


async def test_register_returns_tokens(client: AsyncClient):
    resp = await register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    await register(client, "dup@example.com")
    resp = await register(client, "dup@example.com")
    assert resp.status_code == 409


async def test_register_weak_password_returns_422(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "weak@example.com", "password": "short"})
    assert resp.status_code == 422


async def test_register_invalid_email_returns_422(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


async def test_login_correct_credentials(client: AsyncClient):
    await register(client, "login@example.com")
    resp = await login(client, "login@example.com")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password_returns_401(client: AsyncClient):
    await register(client, "wrongpw@example.com")
    resp = await client.post("/auth/login", json={"email": "wrongpw@example.com", "password": "bad-password"})
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client: AsyncClient):
    resp = await client.post("/auth/login", json={"email": "ghost@example.com", "password": "password123"})
    assert resp.status_code == 401


async def test_login_each_call_issues_new_refresh_token(client: AsyncClient):
    await register(client, "multilogin@example.com")
    r1 = await login(client, "multilogin@example.com")
    r2 = await login(client, "multilogin@example.com")
    assert r1.json()["refresh_token"] != r2.json()["refresh_token"]


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


async def test_refresh_returns_new_token_pair(client: AsyncClient):
    resp = await register(client, "refresh@example.com")
    old_refresh = resp.json()["refresh_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    body = r.json()
    # Refresh token must be rotated (new value issued)
    assert body["refresh_token"] != old_refresh
    # Access token must be present and well-formed
    assert body["access_token"]
    assert body["token_type"] == "bearer"


async def test_refresh_old_token_cannot_be_reused(client: AsyncClient):
    resp = await register(client, "rotate@example.com")
    old_refresh = resp.json()["refresh_token"]

    await client.post("/auth/refresh", json={"refresh_token": old_refresh})

    # Reuse the old token — must fail
    r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 401


async def test_refresh_fake_token_returns_401(client: AsyncClient):
    r = await client.post("/auth/refresh", json={"refresh_token": "fake-token"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


async def test_logout_returns_204(client: AsyncClient):
    resp = await register(client, "logout@example.com")
    refresh_token = resp.json()["refresh_token"]
    r = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert r.status_code == 204


async def test_logout_invalidates_refresh_token(client: AsyncClient):
    resp = await register(client, "logoutinv@example.com")
    refresh_token = resp.json()["refresh_token"]

    await client.post("/auth/logout", json={"refresh_token": refresh_token})

    r = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401


async def test_logout_unknown_token_is_silent(client: AsyncClient):
    r = await client.post("/auth/logout", json={"refresh_token": "ghost-token"})
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


async def test_me_returns_user_profile(client: AsyncClient):
    resp = await register(client, "me@example.com")
    access_token = resp.json()["access_token"]

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@example.com"
    assert body["is_active"] is True
    assert "id" in body


async def test_me_without_token_returns_401(client: AsyncClient):
    r = await client.get("/auth/me")
    assert r.status_code in (401, 403)  # missing credentials: framework returns either


async def test_me_with_bad_token_returns_401(client: AsyncClient):
    r = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_register_duplicate_email_mixed_case_returns_409(client: AsyncClient):
    """Registering the same email with different casing must be rejected."""
    await register(client, "MixedCase@example.com")
    resp = await register(client, "mixedcase@example.com")
    assert resp.status_code == 409


async def test_login_with_mixed_case_email(client: AsyncClient):
    """Login must work regardless of the case used at registration."""
    await register(client, "CaseLogin@example.com")
    resp = await client.post(
        "/auth/login",
        json={"email": "caselogin@EXAMPLE.COM", "password": "password123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
