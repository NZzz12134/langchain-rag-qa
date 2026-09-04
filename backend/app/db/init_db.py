"""建表 + 幂等种子数据（admin/123456）。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine
from app.models import User

logger = logging.getLogger(__name__)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123456"


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_admin(db: AsyncSession) -> None:
    """幂等：admin 不存在则创建（role=admin）。"""
    result = await db.execute(select(User).where(User.username == ADMIN_USERNAME))
    if result.scalar_one_or_none() is not None:
        return
    db.add(
        User(
            username=ADMIN_USERNAME,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role="admin",
        )
    )
    await db.commit()
    logger.info("Seeded admin user (please change password after first login!)")


async def init_db(db: AsyncSession) -> None:
    await create_tables()
    await seed_admin(db)
