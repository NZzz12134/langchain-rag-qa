"""引用详情：某条回答引用的知识库片段全文与来源。"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.exceptions import BusinessError
from app.models import ChatSession, Chunk, Citation, Document, Message, User

router = APIRouter(tags=["citations"])


@router.get("/messages/{message_id}/citations")
async def list_citations(
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """校验消息归属（message → session → user），返回引用块详情。"""
    row = (
        await db.execute(
            select(Message, ChatSession)
            .join(ChatSession, ChatSession.id == Message.session_id)
            .where(Message.id == message_id)
        )
    ).first()
    if row is None or row[1].user_id != user.id:
        raise BusinessError("message_not_found", "消息不存在", 404)

    rows = (
        await db.execute(
            select(Citation, Chunk, Document)
            .join(Chunk, Chunk.id == Citation.chunk_id)
            .join(Document, Document.id == Chunk.document_id)
            .where(Citation.message_id == message_id)
            .order_by(Citation.rank)
        )
    ).all()

    return [
        {
            "rank": cit.rank,
            "score": cit.score,
            "chunk_id": str(chunk.id),
            "text": chunk.content,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "source": doc.source_url or doc.file_path,
            "page": chunk.page_number,
            "row_start": chunk.row_start,
            "row_end": chunk.row_end,
            "heading_path": chunk.heading_path,
        }
        for cit, chunk, doc in rows
    ]
