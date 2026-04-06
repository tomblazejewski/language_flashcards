"""
Development seed script.

Creates a default admin user so you can log in immediately after
running `make dev` for the first time.

Usage:
    make seed
    # or directly:
    uv run python backend/scripts/seed.py

The seed password must be supplied via the SEED_PASSWORD environment variable.
The script exits immediately with a non-zero status if the variable is not set,
to prevent accidental execution against shared or production environments.
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


async def main() -> None:
    seed_password = os.environ.get("SEED_PASSWORD", "")
    if not seed_password:
        print(
            "Error: SEED_PASSWORD environment variable is not set.\n"
            "Set it before running the seed script to prevent accidental use\n"
            "of a well-known password in shared or production environments.\n"
            "\n"
            "  export SEED_PASSWORD=<your-password>\n"
            "  uv run python backend/scripts/seed.py",
            file=sys.stderr,
        )
        sys.exit(1)

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
        print("  Password was set via SEED_PASSWORD env var.")


if __name__ == "__main__":
    asyncio.run(main())
