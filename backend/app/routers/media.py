"""Serves the local storage backend. Only mounted when STORAGE_BACKEND=local (GCS serves itself)."""

import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.deps import get_storage
from app.storage import LocalStorage

router = APIRouter(prefix="/api/media", tags=["media"])


def _authorize(storage: LocalStorage, method: str, key: str, exp: int, sig: str) -> None:
    # The signature is the authorization: it was issued to a logged-in user (GET) or admin (PUT).
    if not storage.verify(method, key, exp, sig):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid or expired link")


@router.put("/{key:path}", status_code=status.HTTP_201_CREATED)
async def upload(
    key: str,
    request: Request,
    exp: int = Query(),
    sig: str = Query(),
    storage: LocalStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> dict[str, int]:
    _authorize(storage, "PUT", key, exp, sig)
    path = storage.path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    # Stream to a temp file and rename, so a half-finished upload never looks complete.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as f:
            async for chunk in request.stream():
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")
                f.write(chunk)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
    return {"size": written}


@router.get("/{key:path}")
async def download(
    key: str,
    exp: int = Query(),
    sig: str = Query(),
    storage: LocalStorage = Depends(get_storage),
) -> FileResponse:
    _authorize(storage, "GET", key, exp, sig)
    path = storage.path_for(key)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    # FileResponse honours Range headers, so the player can seek.
    return FileResponse(path)
