from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import Cache
from app.config import Settings, get_settings
from app.models import User
from app.security import decode_token
from app.storage import Storage


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_cache(request: Request) -> Cache:
    return request.app.state.cache


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def client_ip(request: Request, settings: Settings) -> str:
    """Client IP, taking only the X-Forwarded-For entries our own proxies appended.

    The left side of XFF is client-controlled, so reading it blindly lets anyone dodge rate limits.
    """
    hops = settings.trusted_xff_hops
    if hops > 0:
        parts = [
            p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()
        ]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


async def current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise unauthorized
    user_id = decode_token(token, settings)
    if user_id is None:
        raise unauthorized
    # Look the user up on every request so deactivation and role changes apply immediately.
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


async def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
