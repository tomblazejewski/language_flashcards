"""
Development seed script.

Creates a default admin user so you can log in immediately after
running `make dev` for the first time.

Usage:
    make seed
    # or directly:
    uv run python backend/scripts/seed.py

The seed password is read from the SEED_PASSWORD environment variable.
If not set, a default of "password123" is used and a warning is printed.
The password is never echoed to stdout.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make sure the backend package is importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import AsyncSessionLocal, Base, engine
from app.services.auth import create_user, get_user_by_email

SEED_EMAIL = "admin@example.com"
_DEFAULT_PASSWORD = "password123"


async def main() -> None:
    seed_password = os.environ.get("SEED_PASSWORD", "")
    using_default = not seed_password
    if using_default:
        seed_password = _DEFAULT_PASSWORD
        print(
            "Warning: SEED_PASSWORD env var not set. "
            f"Using default password for {SEED_EMAIL}. "
            "Set SEED_PASSWORD to override."
        )

    # Ensure tables exist (handy if running against a fresh SQLite dev.db
    # without having run `make migrate` first).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        existing = await get_user_by_email(SEED_EMAIL, session)
        if existing:
            print(f"Seed user already exists: {SEED_EMAIL}")
            return

        user = await create_user(SEED_EMAIL, seed_password, session)
        await session.commit()
        print(f"Created seed user: {user.email}")
        if using_default:
            print("  Login with the default password (see SEED_PASSWORD warning above).")
        else:
            print("  Password was set via SEED_PASSWORD env var.")


if __name__ == "__main__":
    asyncio.run(main())
