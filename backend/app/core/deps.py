"""FastAPI 依赖：数据库会话、当前用户、管理员校验。"""
import uuid
from typing import AsyncGenerator

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BusinessError
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import User

settings = get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    """从 Authorization: Bearer <token> 解析当前用户（并挂到 request.state 供限流 key_func 使用）。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise BusinessError("unauthorized", "未登录或登录已过期", 401)
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise BusinessError("unauthorized", "登录已过期，请重新登录", 401)
    except jwt.PyJWTError:
        raise BusinessError("unauthorized", "无效的登录凭证", 401)

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise BusinessError("unauthorized", "账号不存在或已被禁用", 401)
    request.state.user_id = str(user.id)
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """管理员专用依赖：非 admin 返回 403（后端强制校验，前端隐藏仅为体验）。"""
    if user.role != "admin":
        raise BusinessError("forbidden", "无权访问该资源", 403)
    return user


async def get_session_or_404(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID):
    """会话所有权校验：不存在或不属于当前用户均 404。"""
    from app.models import ChatSession

    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id or session.is_deleted:
        raise BusinessError("session_not_found", "会话不存在", 404)
    return session
