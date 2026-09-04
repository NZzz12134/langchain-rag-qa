import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    kb_id: uuid.UUID | None = None


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    kb_id: uuid.UUID | None = None
    kb_name: str | None = None
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None


class SessionListOut(BaseModel):
    items: list[SessionOut]
    total: int
    page: int
    page_size: int
