"""混合检索编排：向量 + BM25 → RRF 融合 → 可选 Rerank → top_k 引用块。"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.providers.rerank import rerank as rerank_api
from app.services.rag import vector_store
from app.services.rag.bm25 import bm25_manager

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    id: str  # chunk uuid（Chroma id = chunks.id）
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


async def hybrid_retrieve(
    query: str,
    kb_id: uuid.UUID | None,
    query_embedding: list[float] | None = None,
) -> list[RetrievedChunk]:
    """返回融合排序后的引用块列表（已截断 top_k / rerank top_n）。"""
    mode = settings.RETRIEVAL_MODE
    results: dict[str, RetrievedChunk] = {}

    # ---- 向量检索（Chroma 磁盘 IO/HTTP 放线程池，避免阻塞事件循环）----
    if query_embedding is not None and mode in ("vector", "hybrid"):
        ids, docs, metas, scores = await asyncio.to_thread(
            vector_store.query_collection,
            kb_id, query_embedding, settings.VECTOR_TOP_K,
        )
        for i, cid in enumerate(ids):
            if scores[i] < settings.SCORE_THRESHOLD:
                continue
            results[cid] = RetrievedChunk(id=cid, text=docs[i], score=scores[i], metadata=metas[i])

    # ---- BM25 ----
    if mode == "hybrid":
        kb_list = [kb_id] if kb_id is not None else await _all_kb_ids()
        for kb in kb_list:
            try:
                await bm25_manager.get_index(kb)
                bm25_hits = await asyncio.to_thread(
                    bm25_manager.search, kb, query, settings.BM25_TOP_K
                )
                for cid, score, meta in bm25_hits:
                    if cid in results:
                        continue  # 向量已有则保留（RRF 按排名融合，重复不叠加）
                    results[cid] = RetrievedChunk(id=cid, text="", score=0.0, metadata=meta)
            except Exception as exc:
                logger.warning("BM25 search failed for kb %s: %s", kb, exc)

    if not results:
        return []

    # ---- RRF 融合 ----
    if mode == "hybrid" and query_embedding is not None:
        chunks = await _rrf_fuse(query_embedding, kb_id, query, list(results.values()))
    else:
        chunks = sorted(results.values(), key=lambda c: c.score, reverse=True)

    # BM25-only 结果的 text 为空 → 从 DB 回填
    await _fill_texts(chunks)

    # ---- Rerank ----
    if settings.RERANK_ENABLED and len(chunks) > 1:
        try:
            ranked = await rerank_api(query, [c.text for c in chunks], top_n=settings.RERANK_TOP_N)
            chunks = [chunks[idx] for idx, score in sorted(ranked, key=lambda x: -x[1])]
        except Exception as exc:
            logger.warning("rerank failed, fallback to fused order: %s", exc)

    return chunks


async def _rrf_fuse(
    query_embedding: list[float],
    kb_id: uuid.UUID | None,
    query: str,
    candidates: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """RRF：score = Σ 1/(k + rank)，k=60。重新跑两路取排名。"""
    k = settings.RRF_K
    rrf: dict[str, float] = {}

    ids, _, _, _ = await asyncio.to_thread(
        vector_store.query_collection, kb_id, query_embedding, settings.VECTOR_TOP_K
    )
    for rank, cid in enumerate(ids):
        if cid in {c.id for c in candidates}:
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (k + rank + 1)

    kb_list = [kb_id] if kb_id is not None else await _all_kb_ids()
    for kb in kb_list:
        try:
            await bm25_manager.get_index(kb)
            bm25_hits = await asyncio.to_thread(
                bm25_manager.search, kb, query, settings.BM25_TOP_K
            )
            for rank, (cid, _score, _meta) in enumerate(bm25_hits):
                if cid in rrf or cid in {c.id for c in candidates}:
                    rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (k + rank + 1)
        except Exception as exc:
            logger.warning("RRF BM25 pass failed for kb %s: %s", kb, exc)

    by_id = {c.id: c for c in candidates}
    merged = [by_id[cid] for cid, _ in sorted(rrf.items(), key=lambda x: -x[1]) if cid in by_id]
    for c in merged:
        c.score = rrf[c.id]
    return merged[: settings.RERANK_TOP_N + 3] if settings.RERANK_ENABLED else merged[: settings.RERANK_TOP_N]


async def _fill_texts(chunks: list[RetrievedChunk]) -> None:
    """BM25 索引不带全文，从 chunks 表回填（仅缺失时）。"""
    missing = [uuid.UUID(c.id) for c in chunks if not c.text]
    if not missing:
        return
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Chunk

    async with SessionLocal() as db:
        rows = (
            await db.execute(select(Chunk.id, Chunk.content).where(Chunk.id.in_(missing)))
        ).all()
    text_map = {str(r[0]): r[1] for r in rows}
    for c in chunks:
        if not c.text:
            c.text = text_map.get(c.id, "")


async def _all_kb_ids() -> list[uuid.UUID]:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import KnowledgeBase

    async with SessionLocal() as db:
        return list((await db.execute(select(KnowledgeBase.id))).scalars().all())
