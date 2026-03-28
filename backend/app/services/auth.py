"""
Authentication service.

Responsibilities:
- Password hashing and verification (bcrypt via passlib)
- JWT access token creation and decoding
- Refresh token creation, storage (hashed), and revocation
- Fetching a user by email or id
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Access token (short-lived JWT)
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return str(jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm))


def decode_access_token(token: str) -> str:
    """
    Return the user_id encoded in the token.

    Raises ``JWTError`` if the token is invalid or expired.
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise JWTError("Token missing sub claim")
    return user_id


# ---------------------------------------------------------------------------
# Refresh token (opaque random token stored hashed in the DB)
# ---------------------------------------------------------------------------


def _hash_token(raw: str) -> str:
    """SHA-256 hash of the raw token string (for safe DB storage)."""
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(user_id: str, db: AsyncSession) -> str:
    """Generate a new refresh token, persist its hash, and return the raw value."""
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()  # write within the current transaction without committing
    return raw


async def rotate_refresh_token(raw: str, db: AsyncSession) -> tuple[str, str]:
    """
    Validate a refresh token, revoke it, and issue a new one.

    Returns ``(user_id, new_raw_refresh_token)``.
    Raises ``ValueError`` if the token is not found or has expired.
    """
    token_hash = _hash_token(raw)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    record: RefreshToken | None = result.scalar_one_or_none()

    if record is None:
        raise ValueError("Refresh token not found")
    # SQLite returns timezone-naive datetimes; normalise before comparison
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.delete(record)
        raise ValueError("Refresh token expired")

    user_id = record.user_id
    await db.delete(record)
    new_raw = await create_refresh_token(user_id, db)
    return user_id, new_raw


async def revoke_refresh_token(raw: str, db: AsyncSession) -> None:
    """Delete a refresh token record (logout). Silent if not found."""
    token_hash = _hash_token(raw)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    record = result.scalar_one_or_none()
    if record:
        await db.delete(record)


# ---------------------------------------------------------------------------
# User lookup helpers
# ---------------------------------------------------------------------------


async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(user_id: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(email: str, password: str, db: AsyncSession) -> User:
    """Create and persist a new user. Raises ``ValueError`` if email is taken."""
    if await get_user_by_email(email, db):
        raise ValueError("Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=email.lower().strip(),
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()
    return user
