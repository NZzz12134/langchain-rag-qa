"""文档解析任务：Celery 执行 load → chunk → embed → Chroma 入库。

关键点：worker 每任务用 asyncio.run 新建事件循环，而 get_embeddings/get_redis
等是进程级 lru_cache 单例（内含绑定 loop 的客户端）——任务开始/结束必须清理，
否则第二个任务复用绑定已关闭 loop 的客户端会挂起/崩溃。
"""
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _reset_loop_bound_singletons() -> None:
    """清掉绑定旧事件循环的单例，让本任务在新 loop 上重建客户端。"""
    from app.core.redis_client import get_redis
    from app.services.providers.embeddings import get_embeddings
    from app.services.providers.rerank import _client

    get_redis.cache_clear()
    get_embeddings.cache_clear()
    _client.cache_clear()


@celery_app.task(
    name="documents.parse",
    bind=True,
    max_retries=3,
    soft_time_limit=1800,  # 30 分钟兜底
    time_limit=1860,
)
def parse_document(self, document_id: str) -> dict:
    """任务入口。失败指数退避重试（30s/60s/120s），最终置 failed。

    pipeline 内部对内容类错误直接返回 failed（不 raise），
    只有网络/队列类异常会走到重试。
    """
    import asyncio

    from app.services.parsing.pipeline import run_parse_pipeline

    _reset_loop_bound_singletons()
    try:
        return asyncio.run(run_parse_pipeline(document_id))
    except Exception as exc:
        logger.exception(
            "parse_document %s failed (attempt %s): %s", document_id, self.request.retries, exc
        )
        if self.request.retries >= self.max_retries:
            _mark_failed(document_id, str(exc))
            raise
        # 指数退避：30s / 60s / 120s
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        _reset_loop_bound_singletons()


def _mark_failed(document_id: str, error: str) -> None:
    import asyncio

    from app.db.session import SessionLocal
    from app.models import Document

    async def _run():
        async with SessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is not None:
                doc.parse_status = "failed"
                doc.error_message = (error or "解析失败")[:2000]
                await db.commit()

    _reset_loop_bound_singletons()
    asyncio.run(_run())
