"""Unit tests for app.services.auth — pure logic, no HTTP layer."""

from __future__ import annotations

from datetime import timedelta, timezone

import pytest
from app.services.auth import (
    _hash_token,
    create_access_token,
    create_refresh_token,
    create_user,
    decode_access_token,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_password_is_not_plaintext():
    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert len(hashed) > 20


def test_verify_password_correct():
    hashed = hash_password("correct-horse")
    assert verify_password("correct-horse", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correct-horse")
    assert verify_password("wrong-horse", hashed) is False


def test_two_hashes_of_same_password_differ():
    """bcrypt uses a random salt — same input must produce different hashes."""
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


# ---------------------------------------------------------------------------
# Access token
# ---------------------------------------------------------------------------


def test_create_and_decode_access_token():
    user_id = "user-123"
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_decode_access_token_rejects_garbage():
    with pytest.raises(JWTError):
        decode_access_token("not.a.token")


def test_decode_access_token_rejects_wrong_type(monkeypatch):
    """A token with type != 'access' must be rejected."""
    from datetime import datetime as dt

    from app.config import settings
    from jose import jwt

    payload = {
        "sub": "user-123",
        "exp": dt.now(timezone.utc) + timedelta(minutes=15),
        "type": "refresh",  # wrong type
    }
    bad_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(JWTError):
        decode_access_token(bad_token)


def test_decode_access_token_rejects_expired(monkeypatch):
    from datetime import datetime as dt

    from app.config import settings
    from jose import jwt

    payload = {
        "sub": "user-123",
        "exp": dt.now(timezone.utc) - timedelta(seconds=1),  # already expired
        "type": "access",
    }
    expired_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(JWTError):
        decode_access_token(expired_token)


# ---------------------------------------------------------------------------
# Refresh token hashing
# ---------------------------------------------------------------------------


def test_hash_token_is_deterministic():
    assert _hash_token("abc") == _hash_token("abc")


def test_hash_token_different_inputs_differ():
    assert _hash_token("abc") != _hash_token("xyz")


# ---------------------------------------------------------------------------
# User creation and lookup (require DB session)
# ---------------------------------------------------------------------------


async def test_create_user_stores_hashed_password(db_session: AsyncSession):
    user = await create_user("alice@example.com", "password123", db_session)
    assert user.email == "alice@example.com"
    assert user.password_hash != "password123"
    assert verify_password("password123", user.password_hash)


async def test_create_user_lowercases_email(db_session: AsyncSession):
    user = await create_user("BOB@EXAMPLE.COM", "password123", db_session)
    assert user.email == "bob@example.com"


async def test_create_user_duplicate_email_raises(db_session: AsyncSession):
    await create_user("carol@example.com", "password123", db_session)
    with pytest.raises(ValueError, match="already registered"):
        await create_user("carol@example.com", "other-password", db_session)


async def test_get_user_by_email_found(db_session: AsyncSession):
    await create_user("dave@example.com", "password123", db_session)
    user = await get_user_by_email("dave@example.com", db_session)
    assert user is not None
    assert user.email == "dave@example.com"


async def test_get_user_by_email_not_found(db_session: AsyncSession):
    user = await get_user_by_email("nobody@example.com", db_session)
    assert user is None


async def test_get_user_by_id(db_session: AsyncSession):
    created = await create_user("eve@example.com", "password123", db_session)
    fetched = await get_user_by_id(created.id, db_session)
    assert fetched is not None
    assert fetched.id == created.id


async def test_get_user_by_id_not_found(db_session: AsyncSession):
    user = await get_user_by_id("00000000-0000-0000-0000-000000000000", db_session)
    assert user is None


# ---------------------------------------------------------------------------
# Refresh token lifecycle
# ---------------------------------------------------------------------------


async def test_create_and_rotate_refresh_token(db_session: AsyncSession):
    user = await create_user("frank@example.com", "password123", db_session)
    raw = await create_refresh_token(user.id, db_session)
    assert len(raw) > 10

    user_id, new_raw = await rotate_refresh_token(raw, db_session)
    assert user_id == user.id
    assert new_raw != raw


async def test_rotate_refresh_token_old_token_invalid_after_rotation(db_session: AsyncSession):
    user = await create_user("grace@example.com", "password123", db_session)
    raw = await create_refresh_token(user.id, db_session)
    await rotate_refresh_token(raw, db_session)

    # Using the old token again must fail
    with pytest.raises(ValueError, match="not found"):
        await rotate_refresh_token(raw, db_session)


async def test_rotate_refresh_token_unknown_raises(db_session: AsyncSession):
    with pytest.raises(ValueError, match="not found"):
        await rotate_refresh_token("completely-fake-token", db_session)


async def test_revoke_refresh_token(db_session: AsyncSession):
    user = await create_user("heidi@example.com", "password123", db_session)
    raw = await create_refresh_token(user.id, db_session)
    await revoke_refresh_token(raw, db_session)

    # After revocation, rotation must fail
    with pytest.raises(ValueError, match="not found"):
        await rotate_refresh_token(raw, db_session)


async def test_revoke_refresh_token_silent_on_unknown(db_session: AsyncSession):
    """Revoking a non-existent token must not raise."""
    await revoke_refresh_token("ghost-token", db_session)  # no exception
