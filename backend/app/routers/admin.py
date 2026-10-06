import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import CATALOG_KEY, Cache, views_key
from app.config import Settings, get_settings
from app.deps import admin_user, get_cache, get_db, get_storage
from app.models import User, Video, VideoStatus
from app.routers.videos import with_views
from app.schemas import UploadTicket, UserOut, VideoCreateIn, VideoOut, VideoUpdateIn
from app.storage import Storage, object_key

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_user)])


async def _get_or_404(db: AsyncSession, video_id: uuid.UUID) -> Video:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    return video


@router.get("/videos", response_model=list[VideoOut])
async def list_all_videos(
    db: AsyncSession = Depends(get_db), cache: Cache = Depends(get_cache)
) -> list[VideoOut]:
    rows = await db.scalars(select(Video).order_by(Video.created_at.desc()))
    videos = [VideoOut.model_validate(v).model_dump(exclude={"views"}) for v in rows]
    return await with_views(cache, videos)


@router.post("/videos", response_model=UploadTicket, status_code=status.HTTP_201_CREATED)
async def create_video(
    body: VideoCreateIn,
    admin: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> UploadTicket:
    """Step 1 of an upload: register the video and hand back a signed upload URL."""
    if body.content_type not in settings.allowed_video_types:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Allowed types: {', '.join(settings.allowed_video_types)}",
        )
    if body.size_bytes > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")

    video_id = uuid.uuid4()
    video = Video(
        id=video_id,
        title=body.title,
        description=body.description,
        object_key=object_key(video_id, body.filename),
        content_type=body.content_type,
        created_by=admin.id,
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    url, headers = await storage.upload_url(video.object_key, video.content_type)
    return UploadTicket(video=VideoOut.model_validate(video), upload_url=url, headers=headers)


@router.post("/videos/{video_id}/complete", response_model=VideoOut)
async def complete_upload(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> Video:
    """Step 2: the browser finished uploading; verify the object really exists."""
    video = await _get_or_404(db, video_id)
    size = await storage.size(video.object_key)
    if size is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Upload not found in storage")
    if size > settings.max_upload_bytes:
        await storage.delete(video.object_key)
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")
    video.size_bytes = size
    video.status = VideoStatus.READY
    await db.commit()
    await db.refresh(video)
    return video


@router.patch("/videos/{video_id}", response_model=VideoOut)
async def update_video(
    video_id: uuid.UUID,
    body: VideoUpdateIn,
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
) -> Video:
    video = await _get_or_404(db, video_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("is_published") and video.status != VideoStatus.READY:
        raise HTTPException(status.HTTP_409_CONFLICT, "Upload is not complete yet")
    for field, value in changes.items():
        setattr(video, field, value)
    await db.commit()
    await db.refresh(video)
    await cache.delete(CATALOG_KEY)
    return video


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
    storage: Storage = Depends(get_storage),
) -> None:
    video = await _get_or_404(db, video_id)
    await storage.delete(video.object_key)
    await db.delete(video)
    await db.commit()
    await cache.delete(CATALOG_KEY, views_key(video_id))


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    return list(await db.scalars(select(User).order_by(User.created_at.desc())))
