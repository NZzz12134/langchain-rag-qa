"""会话服务：列表（含最后消息预览）、新建、重命名、软删除、历史消息。"""
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session_or_404
from app.core.exceptions import BusinessError
from app.db.base import utcnow
from app.models import ChatSession, KnowledgeBase, Message


async def list_sessions(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> dict:
    base = select(ChatSession).where(
        ChatSession.user_id == user_id, ChatSession.is_deleted.is_(False)
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(desc(ChatSession.updated_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    sessions: list[ChatSession] = list(rows)

    # 批量取最后一条消息预览（避免 N+1）：created_at 为微秒精度，max 即最后一条
    previews: dict[uuid.UUID, str] = {}
    if sessions:
        ids = [s.id for s in sessions]
        subq = (
            select(Message.session_id, func.max(Message.created_at).label("max_ts"))
            .where(Message.session_id.in_(ids))
            .group_by(Message.session_id)
            .subquery()
        )
        last_msgs = (
            (
                await db.execute(
                    select(Message).join(
                        subq,
                        Message.created_at == subq.c.max_ts,
                    )
                )
            )
            .scalars()
            .all()
        )
        for m in last_msgs:
            previews[m.session_id] = m.content[:80]

    # kb 名称映射
    kb_ids = [s.kb_id for s in sessions if s.kb_id]
    kb_names: dict[uuid.UUID, str] = {}
    if kb_ids:
        kbs = (
            (await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))))
            .scalars()
            .all()
        )
        kb_names = {k.id: k.name for k in kbs}

    return {
        "items": [
            {
                "id": s.id,
                "title": s.title,
                "kb_id": s.kb_id,
                "kb_name": kb_names.get(s.kb_id) if s.kb_id else None,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "last_message_preview": previews.get(s.id),
            }
            for s in sessions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def create_session(
    db: AsyncSession, user_id: uuid.UUID, title: str | None, kb_id: uuid.UUID | None
) -> ChatSession:
    if kb_id is not None:
        kb = await db.get(KnowledgeBase, kb_id)
        if kb is None or not kb.is_active:
            raise BusinessError("kb_not_found", "知识库不存在", 404)
    session = ChatSession(
        user_id=user_id, kb_id=kb_id, title=(title or "新会话")[:200]
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def rename_session(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, title: str) -> ChatSession:
    session = await get_session_or_404(db, session_id, user_id)
    session.title = title[:200]
    session.updated_at = utcnow()
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    session = await get_session_or_404(db, session_id, user_id)
    session.is_deleted = True  # 软删除，保留消息
    await db.commit()


async def list_messages(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, page: int = 1, page_size: int = 50
) -> dict:
    await get_session_or_404(db, session_id, user_id)
    base = select(Message).where(Message.session_id == session_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(Message.created_at.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    messages = list(rows)

    # 批量填充：当前用户的反馈状态 + 每条回答的引用数量（避免 N+1）
    feedback_map: dict[uuid.UUID, str] = {}
    citations_map: dict[uuid.UUID, int] = {}
    msg_ids = [m.id for m in messages]
    if msg_ids:
        from app.models import Citation, Feedback

        fb_rows = (
            await db.execute(
                select(Feedback).where(Feedback.message_id.in_(msg_ids), Feedback.user_id == user_id)
            )
        ).scalars().all()
        feedback_map = {f.message_id: f.rating for f in fb_rows}
        cite_rows = await db.execute(
            select(Citation.message_id, func.count())
            .where(Citation.message_id.in_(msg_ids))
            .group_by(Citation.message_id)
        )
        citations_map = {mid: cnt for mid, cnt in cite_rows.all()}

    return {
        "items": [
            {
                "id": m.id,
                "session_id": m.session_id,
                "role": m.role,
                "content": m.content,
                "status": m.status,
                "token_usage": m.token_usage,
                "error_message": m.error_message,
                "created_at": m.created_at,
                "feedback": feedback_map.get(m.id),
                "citations_count": citations_map.get(m.id, 0),
            }
            for m in messages
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
