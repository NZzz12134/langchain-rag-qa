"""文档解析全流程（Celery 任务内执行）：load → chunk → embed → Chroma/DB 入库。

幂等与并发安全：
- 状态转换用原子 CAS（UPDATE ... WHERE status IN ('pending','failed')），
  抢不到执行权的任务直接退出，杜绝双任务并发清写；
- 写入前复检 deleted_at，防止「删除文档」与「解析任务」竞态导致数据复活。
"""
import asyncio
import logging
import uuid

from sqlalchemy import delete, update

from app.db.session import SessionLocal
from app.models import Chunk, Document
from app.services.parsing.chunkers import chunk_documents
from app.services.parsing.loaders import load_document
from app.services.providers.embeddings import embed_texts_batched
from app.services.rag import vector_store
from app.utils.file_utils import resolve_storage_path

logger = logging.getLogger(__name__)


async def run_parse_pipeline(document_id: str) -> dict:
    doc_uuid = uuid.UUID(document_id)
    async with SessionLocal() as db:
        doc = await db.get(Document, doc_uuid)
        if doc is None or doc.deleted_at is not None:
            return {"status": "skipped", "reason": "document not found"}

        # 原子 CAS 抢占执行权：pending/failed → parsing；已在 parsing 则退出
        result = await db.execute(
            update(Document)
            .where(
                Document.id == doc_uuid,
                Document.parse_status.in_(("pending", "failed")),
            )
            .values(parse_status="parsing", parse_progress=0, error_message=None)
        )
        await db.commit()
        if result.rowcount == 0:
            return {"status": "skipped", "reason": "already parsing"}
        await db.refresh(doc)

        try:
            # 1. 加载
            source = doc.source_url if doc.file_type == "url" else str(resolve_storage_path(doc.file_path))
            docs = await asyncio.to_thread(load_document, doc.file_type, source)
            if not docs:
                raise ValueError("文档解析后无有效内容")

            # 2. 分块
            chunk_dicts = list(chunk_documents(doc.file_type, docs))
            if not chunk_dicts:
                raise ValueError("文档分块后无有效内容")
            total = len(chunk_dicts)

            # 3. 清旧数据（幂等）
            await db.execute(delete(Chunk).where(Chunk.document_id == doc_uuid))
            await db.commit()
            vector_store.delete_by_document(doc.kb_id, doc_uuid)

            # 4. 批量 embedding（缓存 + 限速 + 重试），期间更新进度
            texts = [c["content"] for c in chunk_dicts]
            all_vectors = await embed_texts_batched(texts)
            doc.parse_progress = 90
            await db.commit()

            # 5. 写入前复检：期间被管理员删除则回滚退出（防复活）
            await db.refresh(doc)
            if doc.deleted_at is not None:
                logger.info("document %s deleted during parse, aborting", document_id)
                return {"status": "skipped", "reason": "deleted during parse"}

            chunk_rows: list[Chunk] = []
            ids: list[str] = []
            metadatas: list[dict] = []
            for idx, c in enumerate(chunk_dicts):
                cid = uuid.uuid4()
                chunk_rows.append(
                    Chunk(
                        id=cid,
                        document_id=doc_uuid,
                        kb_id=doc.kb_id,
                        seq=idx,
                        content=c["content"],
                        page_number=c["page_number"],
                        row_start=c["row_start"],
                        row_end=c["row_end"],
                        heading_path=c["heading_path"],
                        token_count=c["token_count"],
                        content_hash=c["content_hash"],
                    )
                )
                ids.append(str(cid))
                metadatas.append(
                    {
                        "document_id": str(doc_uuid),
                        "kb_id": str(doc.kb_id),
                        "filename": doc.filename,
                        "file_type": doc.file_type,
                        "source": doc.source_url or doc.file_path,
                        "page": c["page_number"] or 0,
                        "row_start": c["row_start"] or 0,
                        "row_end": c["row_end"] or 0,
                        "heading_path": c["heading_path"] or "",
                        "seq": idx,
                    }
                )

            db.add_all(chunk_rows)
            await db.flush()
            vector_store.add_chunks(doc.kb_id, ids, all_vectors, texts, metadatas)
            await db.commit()

            # 6. 完成
            doc.parse_status = "succeeded"
            doc.parse_progress = 100
            doc.chunk_count = total
            await db.commit()
            await _bump_version(doc.kb_id)
            logger.info("Document %s parsed: %d chunks", document_id, total)
            return {"status": "succeeded", "chunks": total}

        except Exception as exc:
            friendly = _friendly_error(exc)
            # 回滚未提交的 chunk 插入，再落失败状态
            await db.rollback()
            await db.refresh(doc)
            doc.parse_status = "failed"
            doc.error_message = friendly
            await db.commit()
            logger.exception("parse pipeline failed for document %s: %s", document_id, exc)
            # 内容类错误不重试（用户可手动重试）；网络类错误向上抛让 Celery 退避重试
            if _is_retryable(exc):
                raise
            return {"status": "failed", "error": friendly[:500]}


def _is_retryable(exc: Exception) -> bool:
    """网络/服务类错误交给 Celery 退避重试；内容/校验类错误直接 failed。"""
    import httpx

    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500  # 4xx 重试无意义
    return False


def _friendly_error(exc: Exception) -> str:
    """把底层异常映射为面向管理员的中文提示（原始信息进日志）。"""
    if isinstance(exc, ValueError):
        return str(exc)[:2000]  # loader 已抛出中文说明
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 401:
            return "API Key 无效或无权限，请检查 .env 中的密钥配置"
        if exc.response.status_code == 429:
            return "模型 API 限流，请稍后点击「重试」"
        if exc.response.status_code >= 500:
            return "模型服务暂时不可用，请稍后点击「重试」"
        return f"模型 API 返回错误（HTTP {exc.response.status_code}），请稍后重试"
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return "网络连接失败或超时，请检查网络后点击「重试」"
    return (str(exc) or exc.__class__.__name__)[:2000]


async def _bump_version(kb_id: uuid.UUID) -> None:
    try:
        from app.core.redis_client import get_redis

        await get_redis().incr(f"kb:version:{kb_id}")
    except Exception as exc:
        logger.warning("kb version bump skipped: %s", exc)
