import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    status: str
    token_usage: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    # 当前用户的反馈状态（like/dislike/None）与引用片段数量（详情按需拉 /messages/{id}/citations）
    feedback: str | None = None
    citations_count: int = 0


class MessageListOut(BaseModel):
    items: list[MessageOut]
    total: int
    page: int
    page_size: int
