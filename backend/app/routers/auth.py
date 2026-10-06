from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import Cache
from app.config import Settings, get_settings
from app.deps import client_ip, current_user, get_cache, get_db
from app.models import User
from app.observability import LOGINS, SIGNUPS
from app.schemas import LoginIn, SignupIn, UserOut
from app.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session(response: Response, user: User, settings: Settings) -> None:
    response.set_cookie(
        settings.cookie_name,
        create_token(user.id, settings),
        max_age=settings.jwt_ttl_minutes * 60,
        httponly=True,  # not readable by JS, so XSS can't steal the session
        secure=settings.cookie_secure,
        samesite="strict",  # never sent on cross-site requests, which blocks CSRF
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many attempts, try again later",
        headers={"Retry-After": str(retry_after)},
    )


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> User:
    ip = client_ip(request, settings)
    if await cache.is_rate_limited(f"rl:signup:{ip}", settings.signups_per_hour_per_ip, 3600):
        raise _too_many(3600)

    user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email exists") from None
    await db.refresh(user)
    SIGNUPS.inc()
    _set_session(response, user, settings)
    return user


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> User:
    email = body.email.lower()
    limit = settings.login_attempts_per_minute
    # Per account (slows password guessing) and per IP (slows credential stuffing).
    limited_email = await cache.is_rate_limited(f"rl:login:email:{email}", limit, 60)
    ip = client_ip(request, settings)
    limited_ip = await cache.is_rate_limited(f"rl:login:ip:{ip}", limit * 6, 60)
    if limited_email or limited_ip:
        LOGINS.labels(result="rate_limited").inc()
        raise _too_many(60)

    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if not verify_password(body.password, user.password_hash if user else None) or not (
        user and user.is_active
    ):
        LOGINS.labels(result="failure").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    LOGINS.labels(result="success").inc()
    _set_session(response, user, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: Settings = Depends(get_settings)) -> None:
    response.delete_cookie(
        settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> User:
    return user
