"""认证路由：注册 / 登录 / 当前用户 / 修改密码。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models import User
from app.schemas.auth_schema import ChangePasswordIn, LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit("3/minute")
async def register(request: Request, data: RegisterIn, db: AsyncSession = Depends(get_db)):
    token, user = await auth_service.register(db, data)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
@limiter.limit("5/minute")
async def login(request: Request, data: LoginIn, db: AsyncSession = Depends(get_db)):
    token, user = await auth_service.login(db, data)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.post("/change-password", status_code=204)
async def change_password(
    data: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.change_password(db, user, data.old_password, data.new_password)
