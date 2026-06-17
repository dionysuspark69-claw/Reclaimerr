"""One-off admin password reset.

Usage:
    uv run python scripts/reset_admin.py <new-password>

Resets the first admin account's password to the value supplied.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from backend.core.auth import get_password_hash
from backend.database import async_db
from backend.database.models import User
from backend.enums import UserRole


async def reset(new_password: str) -> None:
    async with async_db() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.ADMIN).order_by(User.id)
        )
        admin = result.scalars().first()
        if admin is None:
            print("No admin user found. Start the app and use the setup wizard.")
            return
        admin.password_hash = get_password_hash(new_password)
        await session.commit()
        print(f"Password reset for admin '{admin.username}'.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/reset_admin.py <new-password>")
        sys.exit(1)
    asyncio.run(reset(sys.argv[1]))
