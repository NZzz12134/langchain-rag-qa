"""知识库路由：用户侧只读列表（GET /kbs）；管理端 CRUD（/admin/kbs）。"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models import User
from app.schemas.kb_schema import KBCreate, KBOut, KBUpdate
from app.services import kb_service

router = APIRouter(tags=["knowledge-bases"])


@router.get("/kbs", response_model=list[KBOut])
async def list_kbs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户侧：活跃知识库列表（会话绑定用）。"""
    kbs = await kb_service.list_active_kbs(db)
    return [
        KBOut(
            id=k.id, name=k.name, description=k.description,
            is_active=k.is_active, created_at=k.created_at,
        )
        for k in kbs
    ]


admin_router = APIRouter(prefix="/admin/kbs", tags=["admin-kbs"])


@admin_router.get("", response_model=list[KBOut])
async def admin_list_kbs(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await kb_service.list_kbs_admin(db)


@admin_router.post("", response_model=KBOut, status_code=201)
async def admin_create_kb(
    data: KBCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    kb = await kb_service.create_kb(db, data.name, data.description, admin.id)
    return KBOut(
        id=kb.id, name=kb.name, description=kb.description,
        is_active=kb.is_active, created_at=kb.created_at,
    )


@admin_router.patch("/{kb_id}", response_model=KBOut)
async def admin_update_kb(
    kb_id: uuid.UUID,
    data: KBUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    kb = await kb_service.update_kb(db, kb_id, data.name, data.description, data.is_active)
    return KBOut(
        id=kb.id, name=kb.name, description=kb.description,
        is_active=kb.is_active, created_at=kb.created_at,
    )


@admin_router.delete("/{kb_id}", status_code=204)
async def admin_delete_kb(
    kb_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await kb_service.delete_kb(db, kb_id)
