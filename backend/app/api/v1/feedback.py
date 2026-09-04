"""回答反馈：点赞/点踩（同消息同用户一条，可修改），取消反馈。"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.exceptions import BusinessError
from app.models import ChatSession, Feedback, Message, User

router = APIRouter(tags=["feedback"])


class FeedbackIn(BaseModel):
    rating: str = Field(pattern="^(like|dislike)$")
    comment: str | None = Field(default=None, max_length=500)


async def _check_message_owner(db: AsyncSession, message_id: uuid.UUID, user_id: uuid.UUID) -> Message:
    row = (
        await db.execute(
            select(Message, ChatSession)
            .join(ChatSession, ChatSession.id == Message.session_id)
            .where(Message.id == message_id)
        )
    ).first()
    if row is None or row[1].user_id != user_id:
        raise BusinessError("message_not_found", "消息不存在", 404)
    if row[0].role != "assistant":
        raise BusinessError("invalid_target", "只能对回答进行反馈", 400)
    return row[0]


@router.post("/messages/{message_id}/feedback", status_code=201)
async def submit_feedback(
    message_id: uuid.UUID,
    data: FeedbackIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_message_owner(db, message_id, user.id)
    existing = (
        await db.execute(
            select(Feedback).where(Feedback.message_id == message_id, Feedback.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.rating = data.rating
        existing.comment = data.comment
        await db.commit()
        return {"message_id": str(message_id), "rating": data.rating, "updated": True}
    db.add(Feedback(message_id=message_id, user_id=user.id, rating=data.rating, comment=data.comment))
    try:
        await db.commit()
    except IntegrityError:
        # 并发重复提交撞唯一约束：回退为更新
        await db.rollback()
        existing = (
            await db.execute(
                select(Feedback).where(Feedback.message_id == message_id, Feedback.user_id == user.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.rating = data.rating
            existing.comment = data.comment
            await db.commit()
            return {"message_id": str(message_id), "rating": data.rating, "updated": True}
        raise
    return {"message_id": str(message_id), "rating": data.rating, "updated": False}


@router.delete("/messages/{message_id}/feedback", status_code=204)
async def delete_feedback(
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_message_owner(db, message_id, user.id)
    await db.execute(
        delete(Feedback).where(Feedback.message_id == message_id, Feedback.user_id == user.id)
    )
    await db.commit()
