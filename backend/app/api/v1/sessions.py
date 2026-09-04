"""会话路由：列表 / 新建 / 重命名 / 软删除 / 历史消息。"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models import User
from app.schemas.message_schema import MessageListOut
from app.schemas.session_schema import SessionCreate, SessionListOut, SessionOut, SessionUpdate
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=SessionListOut)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.list_sessions(db, user.id, page, page_size)


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(
    data: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.create_session(db, user.id, data.title, data.kb_id)
    return SessionOut(
        id=session.id, title=session.title, kb_id=session.kb_id,
        created_at=session.created_at, updated_at=session.updated_at,
    )


@router.patch("/{session_id}", response_model=SessionOut)
async def rename_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.rename_session(db, user.id, session_id, data.title)
    return SessionOut(
        id=session.id, title=session.title, kb_id=session.kb_id,
        created_at=session.created_at, updated_at=session.updated_at,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await session_service.delete_session(db, user.id, session_id)


@router.get("/{session_id}/messages", response_model=MessageListOut)
async def list_messages(
    session_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.list_messages(db, user.id, session_id, page, page_size)
