import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Chunk(Base, UUIDPkMixin, TimestampMixin):
    """知识分块。id 即 Chroma 中该 chunk 的文档 id —— 引用溯源的唯一锚点。"""

    __tablename__ = "chunks"
    __table_args__ = (
        Index("idx_chunks_document", "document_id", "seq"),
        Index("idx_chunks_kb", "kb_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)  # PDF 页码 1-based
    row_start: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Excel/CSV 行范围
    row_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # MD 标题路径
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # embedding 去重键
