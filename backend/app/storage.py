"""Video object storage.

Browsers upload and stream directly against short-lived signed URLs, so large files never
pass through the API pods or the load balancer's request timeout.
- local: files on disk, URLs signed with HMAC and served by app.routers.media (dev / compose)
- gcs:   V4 signed URLs. On GKE, Workload Identity has no private key, so signing goes
         through the IAM signBlob API (the GSA needs roles/iam.serviceAccountTokenCreator
         on itself).
"""

import asyncio
import contextlib
import hashlib
import hmac
import os
import re
import time
from datetime import timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from app.config import Settings

_KEY_RE = re.compile(r"^videos/[0-9a-f-]{36}/[A-Za-z0-9._-]{1,200}$")


def object_key(video_id: object, filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).name).strip(".-") or "video"
    return f"videos/{video_id}/{stem[-200:]}"


def is_valid_key(key: str) -> bool:
    return bool(_KEY_RE.match(key))


class Storage(Protocol):
    async def upload_url(self, key: str, content_type: str) -> tuple[str, dict[str, str]]: ...
    async def download_url(self, key: str) -> str: ...
    async def size(self, key: str) -> int | None: ...
    async def delete(self, key: str) -> None: ...


class LocalStorage:
    url_prefix = "/api/media"

    def __init__(self, settings: Settings):
        self.base_dir = Path(settings.local_storage_dir)
        self.secret = settings.jwt_secret.get_secret_value().encode()
        self.upload_ttl = settings.upload_url_ttl_seconds
        self.download_ttl = settings.download_url_ttl_seconds

    def _sig(self, method: str, key: str, exp: int) -> str:
        msg = f"{method}\n{key}\n{exp}".encode()
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def _signed(self, method: str, key: str, ttl: int) -> str:
        exp = int(time.time()) + ttl
        return (
            f"{self.url_prefix}/{key}?{urlencode({'exp': exp, 'sig': self._sig(method, key, exp)})}"
        )

    def verify(self, method: str, key: str, exp: int, sig: str) -> bool:
        if exp < time.time() or not is_valid_key(key):
            return False
        return hmac.compare_digest(self._sig(method, key, exp), sig)

    def path_for(self, key: str) -> Path:
        if not is_valid_key(key):
            raise ValueError("invalid object key")
        return self.base_dir / key

    async def upload_url(self, key: str, content_type: str) -> tuple[str, dict[str, str]]:
        return self._signed("PUT", key, self.upload_ttl), {"Content-Type": content_type}

    async def download_url(self, key: str) -> str:
        return self._signed("GET", key, self.download_ttl)

    async def size(self, key: str) -> int | None:
        try:
            return await asyncio.to_thread(os.path.getsize, self.path_for(key))
        except FileNotFoundError:
            return None

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.path_for(key).unlink, missing_ok=True)


class GCSStorage:
    def __init__(self, settings: Settings):
        if not settings.gcs_bucket:
            raise ValueError("GCS_BUCKET is required when STORAGE_BACKEND=gcs")
        from google.cloud import storage  # imported lazily: heavy, unused in local mode

        self.client = storage.Client()
        self.bucket = self.client.bucket(settings.gcs_bucket)
        self.upload_ttl = timedelta(seconds=settings.upload_url_ttl_seconds)
        self.download_ttl = timedelta(seconds=settings.download_url_ttl_seconds)

    def _signing_kwargs(self) -> dict[str, str]:
        import google.auth.transport.requests

        creds = self.client._credentials
        if hasattr(creds, "sign_bytes") and getattr(creds, "signer", None) is not None:
            return {}  # key-file credentials can sign locally
        if not creds.valid:
            creds.refresh(google.auth.transport.requests.Request())
        return {"service_account_email": creds.service_account_email, "access_token": creds.token}

    def _sign(self, key: str, method: str, ttl: timedelta, content_type: str | None) -> str:
        return self.bucket.blob(key).generate_signed_url(
            version="v4",
            expiration=ttl,
            method=method,
            content_type=content_type,
            **self._signing_kwargs(),
        )

    async def upload_url(self, key: str, content_type: str) -> tuple[str, dict[str, str]]:
        url = await asyncio.to_thread(self._sign, key, "PUT", self.upload_ttl, content_type)
        return url, {"Content-Type": content_type}

    async def download_url(self, key: str) -> str:
        return await asyncio.to_thread(self._sign, key, "GET", self.download_ttl, None)

    async def size(self, key: str) -> int | None:
        blob = await asyncio.to_thread(self.bucket.get_blob, key)
        return blob.size if blob is not None else None

    async def delete(self, key: str) -> None:
        from google.api_core.exceptions import NotFound

        with contextlib.suppress(NotFound):
            await asyncio.to_thread(self.bucket.blob(key).delete)


def create_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "gcs":
        return GCSStorage(settings)
    return LocalStorage(settings)
