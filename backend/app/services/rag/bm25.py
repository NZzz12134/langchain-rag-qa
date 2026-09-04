"""BM25 中文混合检索索引：jieba 分词 + rank_bm25，进程内存 + Redis 版本号失效。

注意：所有事件循环操作（DB 查询）都在调用方的 async 上下文执行，
仅 jieba 分词/BM25 构造（纯 CPU）通过 asyncio.to_thread 放入线程池 ——
严禁在线程内再开事件循环（会导致连接池跨 loop，Windows 上直接崩进程）。
"""
import asyncio
import logging
import uuid

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.core.redis_client import get_redis
from app.db.session import SessionLocal
from app.models import Chunk, Document

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return jieba.lcut_for_search(text)


def _make_bm25(docs: list[str]) -> BM25Okapi | None:
    """纯 CPU 函数（线程安全）：构造 BM25 索引。"""
    if not docs:
        return None
    return BM25Okapi(docs, tokenizer=_tokenize)


class BM25IndexManager:
    """每 KB 一份索引。查询前比对 Redis kb:version 决定是否重建（全量，秒级）。"""

    def __init__(self):
        self._indexes: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def get_version(self, kb_id: uuid.UUID) -> int:
        try:
            return int(await get_redis().get(f"kb:version:{kb_id}") or 0)
        except Exception:
            return 0

    async def get_index(self, kb_id: uuid.UUID) -> dict:
        """返回 {"bm25": BM25Okapi|None, "ids": [...], "docs": [...], "metas": [...]}"""
        version = await self.get_version(kb_id)
        key = str(kb_id)
        cached = self._indexes.get(key)
        if cached and cached["version"] == version:
            return cached
        async with self._lock:
            # double-check：拿到锁后可能已被其他协程重建
            cached = self._indexes.get(key)
            if cached and cached["version"] == version:
                return cached
            index = await self._build(kb_id, version)
            self._indexes[key] = index
            return index

    async def _build(self, kb_id: uuid.UUID, version: int) -> dict:
        # DB 查询在当前 async 上下文（调用方 loop）
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(
                        Chunk.id, Chunk.content, Chunk.page_number,
                        Chunk.row_start, Chunk.row_end, Chunk.heading_path,
                        Chunk.kb_id, Document.filename, Document.file_path,
                    )
                    .join(Document, Document.id == Chunk.document_id)
                    .where(Chunk.kb_id == kb_id, Document.deleted_at.is_(None))
                    .order_by(Chunk.seq)
                )
            ).all()

        ids = [str(r[0]) for r in rows]
        docs = [r[1] for r in rows]
        metas = [
            {
                "page": r[2],
                "row_start": r[3],
                "row_end": r[4],
                "heading_path": r[5],
                "kb_id": str(r[6]),
                "filename": r[7],
                "source": r[8],
            }
            for r in rows
        ]
        # 纯 CPU 分词/建索引放线程池（无 loop 操作）
        bm25 = await asyncio.to_thread(_make_bm25, docs)
        logger.info("BM25 index built for kb %s: %d chunks (v%s)", kb_id, len(docs), version)
        return {"version": version, "bm25": bm25, "ids": ids, "docs": docs, "metas": metas}

    def search(self, kb_id: uuid.UUID, query: str, top_k: int) -> list[tuple[str, float, dict]]:
        """同步检索（需先 await get_index 保证最新）。返回 [(chunk_id, score, metadata)]"""
        index = self._indexes.get(str(kb_id))
        if not index or not index["bm25"]:
            return []
        bm25: BM25Okapi = index["bm25"]
        scores = bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            (index["ids"][i], float(scores[i]), index["metas"][i])
            for i in ranked
            if scores[i] > 0
        ]


bm25_manager = BM25IndexManager()


async def warmup_all_indexes() -> None:
    """启动预热：为全部 KB 建索引（lifespan 中执行）。"""
    from app.models import KnowledgeBase

    async with SessionLocal() as db:
        kb_ids = list((await db.execute(select(KnowledgeBase.id))).scalars().all())
    for kb_id in kb_ids:
        try:
            await bm25_manager.get_index(kb_id)
        except Exception as exc:
            logger.warning("BM25 warmup failed for kb %s: %s", kb_id, exc)
