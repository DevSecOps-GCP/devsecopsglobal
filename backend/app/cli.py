"""python -m app.cli bootstrap-admin: create (or promote) ADMIN_EMAIL. Runs in the migration job."""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import func, select

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import User
from app.security import hash_password

log = logging.getLogger("cli")


async def bootstrap_admin() -> int:
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        log.info("ADMIN_EMAIL / ADMIN_PASSWORD not set, skipping")
        return 0
    email = settings.admin_email.lower()
    engine = create_engine(settings)
    try:
        async with create_sessionmaker(engine)() as db:
            user = await db.scalar(select(User).where(func.lower(User.email) == email))
            if user is None:
                db.add(
                    User(
                        email=email,
                        full_name=settings.admin_full_name,
                        password_hash=hash_password(settings.admin_password.get_secret_value()),
                        is_admin=True,
                    )
                )
                log.info("created admin %s", email)
            elif not user.is_admin:
                user.is_admin = True
                log.info("promoted %s to admin", email)
            else:
                # Never overwrite the password: it may have been changed since bootstrap.
                log.info("admin %s already exists", email)
            await db.commit()
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=["bootstrap-admin"])
    parser.parse_args()
    return asyncio.run(bootstrap_admin())


if __name__ == "__main__":
    sys.exit(main())
