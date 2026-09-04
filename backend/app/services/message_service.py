"""消息服务：历史获取、占位创建、流式追加/完结、引用落库、标题生成。"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import Citation, ChatSession, Message

logger = logging.getLogger(__name__)


async def get_recent_history(db: AsyncSession, session_id: uuid.UUID, limit: int = 6) -> list[dict]:
    rows = (
        await db.execute(
            select(Message)
            .where(Message.session_id == session_id, Message.status.in_(("completed", "stopped")))
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {"role": m.role, "content": m.content}
        for m in reversed(rows)
        if m.content  # 过滤空内容（中断的空占位）
    ]


async def create_user_message(db: AsyncSession, session_id: uuid.UUID, content: str) -> Message:
    msg = Message(session_id=session_id, role="user", content=content, status="completed")
    db.add(msg)
    await db.flush()
    return msg


async def create_assistant_placeholder(db: AsyncSession, session_id: uuid.UUID) -> Message:
    msg = Message(session_id=session_id, role="assistant", content="", status="generating")
    db.add(msg)
    await db.flush()
    return msg


async def finalize_message(
    db: AsyncSession,
    message: Message,
    content: str,
    status: str = "completed",
    error: str | None = None,
) -> None:
    message.content = content
    message.status = status
    message.error_message = error
    await db.commit()


async def touch_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    session = await db.get(ChatSession, session_id)
    if session is not None:
        session.updated_at = utcnow()
        await db.commit()


async def save_citations(
    db: AsyncSession, message_id: uuid.UUID, citations: list[dict]
) -> None:
    for rank, c in enumerate(citations, start=1):
        db.add(
            Citation(
                message_id=message_id,
                chunk_id=uuid.UUID(c["id"]),
                rank=rank,
                score=c.get("score"),
            )
        )
    await db.commit()


async def auto_title_session(db: AsyncSession, session_id: uuid.UUID, first_question: str) -> None:
    """首条消息后用 LLM 生成会话标题（失败静默，保持默认标题）。"""
    try:
        from langchain_core.output_parsers import StrOutputParser

        from app.services.rag.prompts import TITLE_PROMPT

        session = await db.get(ChatSession, session_id)
        if session is None or session.title not in ("新会话", ""):
            return
        chain = TITLE_PROMPT | __import__(
            "app.services.providers.llm", fromlist=["get_llm"]
        ).get_llm() | StrOutputParser()
        title = (await chain.ainvoke({"question": first_question})).strip()
        if title:
            session.title = title[:200]
            await db.commit()
    except Exception as exc:
        logger.warning("auto title failed: %s", exc)
