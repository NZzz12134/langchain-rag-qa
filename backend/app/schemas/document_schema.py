import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int | None = None
    source_url: str | None = None
    parse_status: str
    parse_progress: int
    chunk_count: int
    error_message: str | None = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class UrlDocumentIn(BaseModel):
    url: str = Field(min_length=8, max_length=1000)


class ChunkOut(BaseModel):
    id: uuid.UUID
    seq: int
    content: str
    page_number: int | None = None
    row_start: int | None = None
    row_end: int | None = None
    heading_path: str | None = None
    token_count: int

    model_config = {"from_attributes": True}


class ChunkListOut(BaseModel):
    items: list[ChunkOut]
    total: int
    page: int
    page_size: int
