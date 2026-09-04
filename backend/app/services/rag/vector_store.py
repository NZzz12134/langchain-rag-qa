"""Chroma 管理：embedded/server 双模式、per-KB collection、HNSW 参数、批量增删。"""
import hashlib
import logging
import uuid
from functools import lru_cache

from chromadb import HttpClient, PersistentClient
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

HNSW_METADATA = {
    "hnsw:space": "cosine",
    "hnsw:M": 16,
    "hnsw:construction_ef": 200,
    "hnsw:search_ef": 100,
}


@lru_cache
def get_chroma_client():
    """Chroma 客户端单例。CHROMA_MODE=embedded（开发）| server（生产）。"""
    settings = get_settings()
    if settings.CHROMA_MODE == "server":
        headers = {"X-Chroma-Token": settings.CHROMA_TOKEN} if settings.CHROMA_TOKEN else {}
        return HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT, headers=headers)
    settings.chroma_persist_path.mkdir(parents=True, exist_ok=True)
    return PersistentClient(
        path=str(settings.chroma_persist_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def collection_name(kb_id: uuid.UUID) -> str:
    """collection 名带 embedding 模型 hash：更换模型（维度变化）自动启用新 collection，避免混用。"""
    model_hash = hashlib.md5(get_settings().EMBEDDING_MODEL.encode()).hexdigest()[:8]
    return f"kb_{kb_id.hex}_{model_hash}"


def ensure_collection(kb_id: uuid.UUID):
    """建 collection（幂等）。HNSW 参数建后不可改。"""
    return get_chroma_client().get_or_create_collection(
        name=collection_name(kb_id), metadata=HNSW_METADATA
    )


def get_collection(kb_id: uuid.UUID):
    return get_chroma_client().get_collection(name=collection_name(kb_id))


def delete_collection(kb_id: uuid.UUID) -> None:
    try:
        get_chroma_client().delete_collection(name=collection_name(kb_id))
        logger.info("Deleted chroma collection for kb %s", kb_id)
    except Exception as exc:  # collection 不存在时忽略
        logger.warning("delete_collection %s: %s", kb_id, exc)


def add_chunks(
    kb_id: uuid.UUID,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """批量写入（每批 100）。"""
    col = ensure_collection(kb_id)
    batch = 100
    for i in range(0, len(ids), batch):
        col.add(
            ids=ids[i : i + batch],
            embeddings=embeddings[i : i + batch],
            documents=documents[i : i + batch],
            metadatas=metadatas[i : i + batch],
        )


def delete_by_document(kb_id: uuid.UUID, document_id: uuid.UUID) -> None:
    try:
        get_collection(kb_id).delete(where={"document_id": str(document_id)})
    except Exception as exc:
        logger.warning("delete_by_document %s: %s", document_id, exc)


def query_collection(
    kb_id: uuid.UUID | None,
    query_embedding: list[float],
    n_results: int = 10,
    where: dict | None = None,
) -> tuple[list[str], list[str], list[dict], list[float]]:
    """按 kb 过滤查询。kb_id=None 时须对每个 kb 分别查询后合并（Chroma where 不支持多 collection 跨查）。

    返回 (ids, documents, metadatas, scores) —— score 由 cosine distance 转换：1 - distance。
    """
    if kb_id is not None:
        cols = [get_collection(kb_id)]
    else:
        cols = _all_collections()

    all_ids, all_docs, all_metas, all_scores = [], [], [], []
    for col in cols:
        res = col.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        if not res["ids"] or not res["ids"][0]:
            continue
        for i, cid in enumerate(res["ids"][0]):
            all_ids.append(cid)
            all_docs.append(res["documents"][0][i])
            all_metas.append(res["metadatas"][0][i] or {})
            all_scores.append(1 - res["distances"][0][i])
    return all_ids, all_docs, all_metas, all_scores


def _all_collections():
    """kb_id=None（会话未绑知识库）：检索全部知识库。collection 名过滤 kb_ 前缀。"""
    prefix = "kb_"
    return [
        col
        for col in get_chroma_client().list_collections()
        if col.name.startswith(prefix)
    ]
