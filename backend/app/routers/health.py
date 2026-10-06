from fastapi import APIRouter, Depends, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.cache import Cache
from app.deps import get_cache

# Not under /api: the load balancer only routes /api/* to the backend, so these stay internal.
router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is up. Deliberately checks no dependencies."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(
    request: Request, response: Response, cache: Cache = Depends(get_cache)
) -> dict[str, str]:
    """Readiness: Postgres is required. Redis is reported only, since the app runs without it."""
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db = "ok"
    except Exception:
        db = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"database": db, "redis": "ok" if await cache.ping() else "degraded"}


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
