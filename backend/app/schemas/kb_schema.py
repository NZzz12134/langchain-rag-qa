import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class KBCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class KBUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class KBOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    # 管理端统计字段（用户侧列表为 None）
    document_count: int | None = None
    chunk_count: int | None = None
    parse_stats: dict[str, int] | None = None
