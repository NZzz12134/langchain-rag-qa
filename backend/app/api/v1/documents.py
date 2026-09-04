"""文档管理路由（admin-only）：上传 / URL 抓取 / 列表 / 重解析 / 重试 / 删除 / 分块预览。"""
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.models import User
from app.schemas.document_schema import (
    ChunkListOut,
    DocumentListOut,
    DocumentOut,
    UrlDocumentIn,
)
from app.services import document_service

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"])


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    kb_id: uuid.UUID = Query(..., description="知识库 ID"),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.create_upload_document(db, admin, kb_id, file)
    return DocumentOut.model_validate(doc)


@router.post("/url", response_model=DocumentOut, status_code=201)
async def create_url_document(
    data: UrlDocumentIn,
    kb_id: uuid.UUID = Query(..., description="知识库 ID"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.create_url_document(db, admin, kb_id, data.url)
    return DocumentOut.model_validate(doc)


@router.get("", response_model=DocumentListOut)
async def list_documents(
    kb_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(db, kb_id, status, keyword, page, page_size)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.core.exceptions import BusinessError

    from app.models import Document

    doc = await db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise BusinessError("document_not_found", "文档不存在", 404)
    return DocumentOut.model_validate(doc)


@router.post("/{doc_id}/reparse", response_model=DocumentOut)
async def reparse_document(
    doc_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.reparse_document(db, doc_id)
    return DocumentOut.model_validate(doc)


@router.post("/{doc_id}/retry", response_model=DocumentOut)
async def retry_document(
    doc_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.retry_document(db, doc_id)
    return DocumentOut.model_validate(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await document_service.delete_document(db, doc_id)


@router.get("/{doc_id}/chunks", response_model=ChunkListOut)
async def list_chunks(
    doc_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_chunks(db, doc_id, page, page_size)
