import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import CATALOG_KEY, Cache, views_key
from app.config import Settings, get_settings
from app.deps import current_user, get_cache, get_db, get_storage
from app.models import User, Video, VideoStatus
from app.observability import VIDEO_VIEWS
from app.schemas import VideoOut, VideoPlayback
from app.storage import Storage

router = APIRouter(prefix="/api/videos", tags=["videos"])


async def with_views(cache: Cache, videos: list[dict]) -> list[VideoOut]:
    counts = await cache.get_counts([views_key(v["id"]) for v in videos])
    return [VideoOut(**v, views=c) for v, c in zip(videos, counts, strict=True)]


@router.get("", response_model=list[VideoOut])
async def list_videos(
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> list[VideoOut]:
    # Cache-aside: the catalog changes rarely, view counts are read live from Redis.
    catalog = await cache.get_json(CATALOG_KEY)
    if catalog is None:
        rows = await db.scalars(
            select(Video)
            .where(Video.is_published.is_(True), Video.status == VideoStatus.READY)
            .order_by(Video.created_at.desc())
        )
        catalog = [
            VideoOut.model_validate(v).model_dump(mode="json", exclude={"views"}) for v in rows
        ]
        await cache.set_json(CATALOG_KEY, catalog, settings.catalog_cache_ttl_seconds)
    return await with_views(cache, catalog)


@router.get("/{video_id}", response_model=VideoPlayback)
async def get_video(
    video_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
    storage: Storage = Depends(get_storage),
) -> VideoPlayback:
    video = await db.get(Video, video_id)
    visible = video is not None and video.status == VideoStatus.READY
    if not visible or not (video.is_published or user.is_admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")

    views = await cache.incr(views_key(video.id)) or 0
    VIDEO_VIEWS.inc()
    out = VideoOut.model_validate(video).model_dump(exclude={"views"})
    return VideoPlayback(**out, views=views, url=await storage.download_url(video.object_key))
