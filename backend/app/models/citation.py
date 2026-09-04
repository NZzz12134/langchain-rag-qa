import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Citation(Base, UUIDPkMixin, TimestampMixin):
    """回答 → 引用块 映射。rank 对应回答中 [1][2] 编号顺序。"""

    __tablename__ = "citations"
    __table_args__ = (
        Index("idx_citations_message", "message_id", "rank"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
