import asyncio
import os
import shutil
import tempfile
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# Point at the test database before anything reads settings. Defaults match docker-compose.
os.environ["DB_NAME"] = os.getenv("TEST_DB_NAME", "learnhub_test")
os.environ["REDIS_DB"] = os.getenv("TEST_REDIS_DB", "15")
os.environ.setdefault("REDIS_PASSWORD", "local-redis-password")
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = tempfile.mkdtemp(prefix="dsg-media-")
os.environ["COOKIE_SECURE"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

from sqlalchemy import text

from app.config import Settings
from app.db import create_engine
from app.main import create_app
from app.models import Base, User
from app.security import hash_password

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def media_dir():
    yield
    shutil.rmtree(os.environ["LOCAL_STORAGE_DIR"], ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    async def reset() -> None:
        engine = create_engine(Settings())
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(reset())


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
async def app(settings: Settings):
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with application.state.engine.begin() as conn:
            await conn.execute(text("TRUNCATE videos, users CASCADE"))
        await application.state.cache.redis.flushdb()
        yield application


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
async def client(app):
    async with _client(app) as c:
        yield c


async def signup(client: AsyncClient, email: str | None = None) -> dict:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup", json={"email": email, "full_name": "Test User", "password": PASSWORD}
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
async def user_client(app):
    async with _client(app) as c:
        await signup(c)
        yield c


@pytest.fixture
async def admin_client(app):
    async with app.state.sessionmaker() as db:
        db.add(
            User(
                email="admin@example.com",
                full_name="Admin",
                password_hash=hash_password(PASSWORD),
                is_admin=True,
            )
        )
        await db.commit()
    async with _client(app) as c:
        r = await c.post(
            "/api/auth/login", json={"email": "admin@example.com", "password": PASSWORD}
        )
        assert r.status_code == 200, r.text
        yield c
