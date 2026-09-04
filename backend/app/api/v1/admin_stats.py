"""管理端统计接口（admin-only）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.models import User
from app.services import stats_service

router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


@router.get("/overview")
async def overview(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await stats_service.overview(db)


@router.get("/daily-qa")
async def daily_qa(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await stats_service.daily_qa(db)


@router.get("/documents")
async def document_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await stats_service.document_stats(db)
