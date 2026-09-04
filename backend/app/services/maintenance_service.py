"""周期维护：僵尸解析状态兜底（worker 崩溃/入队失败后的自愈）。"""
import logging
from datetime import timedelta

from sqlalchemy import update

from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models import Document

logger = logging.getLogger(__name__)

# parsing 超过该时长视为任务中断（embedding 大批量文档最坏约 30 分钟）
STALE_PARSING_MINUTES = 30
# pending 且无 task_id 超过该时长视为入队失败
STALE_PENDING_HOURS = 2


async def sweep_stale_documents() -> dict:
    """把超时的 parsing/pending 文档置 failed（附可操作的错误提示）。"""
    now = utcnow()
    parsing_cutoff = now - timedelta(minutes=STALE_PARSING_MINUTES)
    pending_cutoff = now - timedelta(hours=STALE_PENDING_HOURS)

    async with SessionLocal() as db:
        r1 = await db.execute(
            update(Document)
            .where(
                Document.parse_status == "parsing",
                Document.updated_at < parsing_cutoff,
                Document.deleted_at.is_(None),
            )
            .values(
                parse_status="failed",
                error_message="解析任务中断（可能因服务重启），请点击「重试」",
            )
        )
        r2 = await db.execute(
            update(Document)
            .where(
                Document.parse_status == "pending",
                Document.task_id.is_(None),
                Document.created_at < pending_cutoff,
                Document.deleted_at.is_(None),
            )
            .values(
                parse_status="failed",
                error_message="任务未能入队（队列服务异常），请点击「重试」",
            )
        )
        await db.commit()

    swept = (r1.rowcount or 0) + (r2.rowcount or 0)
    if swept:
        logger.info("maintenance swept %d stale documents", swept)
    return {"swept_parsing": r1.rowcount or 0, "swept_pending": r2.rowcount or 0}


async def maintenance_loop(interval_seconds: int = 300) -> None:
    """常驻循环（由 API lifespan 启动），每 interval 秒执行一次兜底扫描。"""
    import asyncio

    while True:
        try:
            await sweep_stale_documents()
        except Exception as exc:
            logger.warning("maintenance sweep failed: %s", exc)
        await asyncio.sleep(interval_seconds)
