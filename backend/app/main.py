from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app.cache import Cache, create_redis
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.observability import MetricsMiddleware, configure_logging
from app.routers import admin, auth, health, media, videos
from app.storage import create_storage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = create_engine(settings)
        app.state.sessionmaker = create_sessionmaker(app.state.engine)
        redis = create_redis(settings)
        app.state.cache = Cache(redis)
        app.state.storage = create_storage(settings)
        yield
        await redis.aclose()
        await app.state.engine.dispose()

    docs = settings.enable_docs
    app = FastAPI(
        title=f"{settings.app_name} API",
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    app.add_middleware(MetricsMiddleware)

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(videos.router)
    app.include_router(admin.router)
    if settings.storage_backend == "local":
        app.include_router(media.router)
    return app


app = create_app()
