"""Celery 应用：Redis broker（db1）/ result backend（db2）。

Windows 开发启动（必须 -P solo）：
    cd backend && .venv\\Scripts\\celery -A app.workers.celery_app worker -P solo -l info
"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()


def _swap_db(url: str, db_index: int) -> str:
    base = url.rsplit("/", 1)[0]
    return f"{base}/{db_index}"


celery_app = Celery(
    "rag_worker",
    broker=_swap_db(settings.REDIS_URL, 1),
    backend=_swap_db(settings.REDIS_URL, 2),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
)

# include 确保 worker 启动时导入任务模块（autodiscover 只找 tasks.py，不递归包内子模块）
celery_app.conf.update(include=["app.workers.tasks.document_tasks"])
