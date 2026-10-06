import ssl

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import Settings


def database_url(settings: Settings) -> URL:
    # URL.create escapes special characters in the password, unlike string formatting.
    return URL.create(
        "postgresql+asyncpg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def _ssl_context(settings: Settings) -> ssl.SSLContext | None:
    if settings.db_ssl == "disable":
        return None
    ctx = ssl.create_default_context(cafile=settings.db_ca_cert)
    # Cloud SQL server certs are issued for the instance name, not the private IP,
    # so we verify the CA chain but not the hostname.
    ctx.check_hostname = False
    if settings.db_ssl == "require":
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def create_engine(settings: Settings) -> AsyncEngine:
    connect_args = {}
    if (ctx := _ssl_context(settings)) is not None:
        connect_args["ssl"] = ctx
    return create_async_engine(
        database_url(settings),
        pool_size=settings.db_pool_size,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
