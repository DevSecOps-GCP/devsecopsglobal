import json
import logging
import sys
import time
from datetime import UTC, datetime

from prometheus_client import Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
CACHE_REQUESTS = Counter("learnhub_cache_requests_total", "Catalog cache lookups", ["result"])
REDIS_ERRORS = Counter("learnhub_redis_errors_total", "Redis operations that failed", ["op"])
LOGINS = Counter("learnhub_logins_total", "Login attempts", ["result"])
SIGNUPS = Counter("learnhub_signups_total", "Successful signups")
VIDEO_VIEWS = Counter("learnhub_video_views_total", "Video playback URLs issued")

_UNMEASURED = {"/metrics", "/healthz", "/readyz"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            # "severity" is the field Cloud Logging maps to log level
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True


class MetricsMiddleware:
    """Records latency per route template (not raw path, to keep label cardinality bounded)."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self.log = logging.getLogger("access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in _UNMEASURED:
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            route = getattr(scope.get("route"), "path", "unmatched")
            HTTP_LATENCY.labels(scope["method"], route, str(status)).observe(elapsed)
            self.log.info(
                "%s %s %s",
                scope["method"],
                route,
                status,
                extra={
                    "extra_fields": {
                        "method": scope["method"],
                        "route": route,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 2),
                    }
                },
            )
