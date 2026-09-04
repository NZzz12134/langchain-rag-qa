"""认证服务：注册、登录（连败锁定）、改密。"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BusinessError
from app.core.redis_client import get_redis
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import utcnow
from app.models import User
from app.schemas.auth_schema import LoginIn, RegisterIn

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_LOGIN_FAILS = 5


def _fail_key(username: str) -> str:
    return f"login:fail:{username}"


async def register(db: AsyncSession, data: RegisterIn) -> tuple[str, User]:
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none() is not None:
        raise BusinessError("username_taken", "用户名已被注册", 409)
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role="user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id, user.role)
    return token, user


async def login(db: AsyncSession, data: LoginIn) -> tuple[str, User]:
    redis = get_redis()
    fail_key = _fail_key(data.username)

    # 连败锁定检查（Redis 不可用时降级跳过）
    try:
        fails = int(await redis.get(fail_key) or 0)
    except Exception:
        fails = 0
    if fails >= MAX_LOGIN_FAILS:
        raise BusinessError(
            "account_locked", "登录失败次数过多，账号已锁定，请 15 分钟后再试", 403
        )

    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(data.password, user.hashed_password):
        await _record_fail(redis, fail_key, fails)
        raise BusinessError("bad_credentials", "用户名或密码错误", 401)
    if not user.is_active:
        raise BusinessError("user_disabled", "账号已被禁用", 403)

    try:
        await redis.delete(fail_key)
    except Exception:
        pass

    user.last_login_at = utcnow()
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id, user.role)
    return token, user


async def _record_fail(redis, fail_key: str, current: int) -> None:
    try:
        await redis.incr(fail_key)
        if current == 0:
            await redis.expire(fail_key, settings.LOGIN_LOCK_SECONDS)
    except Exception:
        logger.warning("Redis unavailable, login fail counter skipped")


async def change_password(
    db: AsyncSession, user: User, old_password: str, new_password: str
) -> None:
    if not verify_password(old_password, user.hashed_password):
        raise BusinessError("wrong_password", "原密码不正确", 400)
    user.hashed_password = hash_password(new_password)
    await db.commit()
    logger.info("Password changed for user %s", user.username)
