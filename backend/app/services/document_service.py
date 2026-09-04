"""文档服务：上传落盘/URL 抓取 → 建 Celery 任务；重解析/重试/删除编排。"""
import logging
import uuid

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BusinessError
from app.core.redis_client import get_redis
from app.db.base import utcnow
from app.models import Chunk, Document, KnowledgeBase, User
from app.services.rag import vector_store
from app.utils.file_utils import save_upload, validate_upload

logger = logging.getLogger(__name__)
settings = get_settings()


async def _bump_kb_version(kb_id: uuid.UUID) -> None:
    """BM25 索引失效信号：+1 版本号，API 进程比对后重建。"""
    try:
        await get_redis().incr(f"kb:version:{kb_id}")
    except Exception as exc:
        logger.warning("Redis unavailable, kb version bump skipped: %s", exc)


def _enqueue_parse(document_id: uuid.UUID) -> str:
    from app.workers.tasks.document_tasks import parse_document

    task = parse_document.delay(str(document_id))
    return task.id


async def _enqueue_or_fail(db: AsyncSession, doc: Document) -> str | None:
    """入队；broker 不可用时把文档置 failed（可重试），返回 task_id 或 None。"""
    try:
        doc.task_id = _enqueue_parse(doc.id)
        await db.commit()
        return doc.task_id
    except Exception as exc:
        logger.error("enqueue parse task failed for %s: %s", doc.id, exc)
        doc.parse_status = "failed"
        doc.error_message = "任务未能入队（队列服务异常），请点击「重试」"
        await db.commit()
        raise BusinessError("enqueue_failed", "任务队列不可用，文档已置为失败状态，请稍后重试", 503)


async def _get_kb(db: AsyncSession, kb_id: uuid.UUID) -> KnowledgeBase:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise BusinessError("kb_not_found", "知识库不存在", 404)
    return kb


async def create_upload_document(
    db: AsyncSession, user: User, kb_id: uuid.UUID, file: UploadFile
) -> Document:
    await _get_kb(db, kb_id)
    filename = file.filename or "unnamed"
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    # 先按 size 预检（starlette 已 spool，超大文件不必全量进内存）
    if file.size is not None and file.size > max_bytes:
        raise BusinessError("file_too_large", f"文件大小超过限制（{settings.MAX_UPLOAD_MB}MB）")
    content = await file.read()

    file_type, checksum = validate_upload(filename, content, settings.MAX_UPLOAD_MB)

    # SHA256 去重（同 KB 内）
    dup = (
        await db.execute(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.checksum == checksum,
                Document.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise BusinessError("duplicate_document", f"该文件已存在：{dup.filename}", 409)

    rel_path = save_upload(content, file_type)
    doc = Document(
        kb_id=kb_id,
        filename=filename[:255],
        file_path=rel_path,
        file_type=file_type,
        file_size=len(content),
        checksum=checksum,
        parse_status="pending",
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    await _enqueue_or_fail(db, doc)
    return doc


def _validate_url(url: str) -> None:
    """URL 白名单 + SSRF 防护：仅 http/https，拒绝私网/环回/链路本地地址。"""
    import ipaddress
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BusinessError("invalid_url", "仅支持 http/https 链接")
    host = parsed.hostname
    if not host:
        raise BusinessError("invalid_url", "链接缺少有效主机名")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None  # 域名，解析阶段的 DNS rebinding 不在本期防护范围
    if ip is not None and (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    ):
        raise BusinessError("invalid_url", "不允许访问内网或保留地址")


async def create_url_document(
    db: AsyncSession, user: User, kb_id: uuid.UUID, url: str
) -> Document:
    await _get_kb(db, kb_id)
    _validate_url(url)
    doc = Document(
        kb_id=kb_id,
        filename=url[:255],
        file_path=url,
        file_type="url",
        source_url=url,
        parse_status="pending",
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    await _enqueue_or_fail(db, doc)
    return doc


async def reparse_document(db: AsyncSession, doc_id: uuid.UUID) -> Document:
    doc = await _get_doc(db, doc_id)
    if doc.parse_status == "parsing":
        raise BusinessError("conflict", "文档正在解析中，请稍后再试", 409)
    if doc.parse_status == "pending" and doc.task_id:
        # 已有任务在队列中：拒绝重复入队
        raise BusinessError("conflict", "文档已在解析队列中，请稍后再试", 409)
    doc.parse_status = "pending"
    doc.parse_progress = 0
    doc.error_message = None
    doc.task_id = None
    await db.commit()
    await _enqueue_or_fail(db, doc)
    await db.refresh(doc)
    return doc


async def retry_document(db: AsyncSession, doc_id: uuid.UUID) -> Document:
    doc = await _get_doc(db, doc_id)
    if doc.parse_status != "failed":
        raise BusinessError("conflict", "仅失败状态的文档可重试", 409)
    doc.parse_status = "pending"
    doc.parse_progress = 0
    doc.error_message = None
    doc.task_id = None
    doc.retry_count += 1
    await db.commit()
    await _enqueue_or_fail(db, doc)
    await db.refresh(doc)
    return doc


async def delete_document(db: AsyncSession, doc_id: uuid.UUID) -> None:
    doc = await _get_doc(db, doc_id)
    doc.deleted_at = utcnow()  # 软删除
    await db.commit()
    vector_store.delete_by_document(doc.kb_id, doc.id)
    await _bump_kb_version(doc.kb_id)
    logger.info("Document %s deleted (soft)", doc_id)


async def _get_doc(db: AsyncSession, doc_id: uuid.UUID) -> Document:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise BusinessError("document_not_found", "文档不存在", 404)
    return doc


async def list_documents(
    db: AsyncSession,
    kb_id: uuid.UUID | None,
    status: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> dict:
    conds = [Document.deleted_at.is_(None)]
    if kb_id is not None:
        conds.append(Document.kb_id == kb_id)
    if status:
        conds.append(Document.parse_status == status)
    if keyword:
        conds.append(Document.filename.like(f"%{keyword}%"))

    base = select(Document).where(*conds)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(Document.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return {"items": list(rows), "total": total, "page": page, "page_size": page_size}


async def list_chunks(db: AsyncSession, doc_id: uuid.UUID, page: int, page_size: int) -> dict:
    await _get_doc(db, doc_id)
    base = select(Chunk).where(Chunk.document_id == doc_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(Chunk.seq.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return {"items": list(rows), "total": total, "page": page, "page_size": page_size}
