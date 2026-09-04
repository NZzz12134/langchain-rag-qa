"""FastAPI 应用入口：lifespan 建表/种子、CORS、异常处理、路由挂载。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.db.init_db import init_db
from app.db.session import SessionLocal

settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建表 + 种子 admin + 存储目录 + BM25 预热
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.chroma_persist_path.mkdir(parents=True, exist_ok=True)
    async with SessionLocal() as db:
        await init_db(db)
    try:
        from app.services.rag.bm25 import warmup_all_indexes

        await warmup_all_indexes()
    except Exception as exc:
        logger.warning("BM25 warmup skipped: %s", exc)

    # 周期维护任务：僵尸 parsing/pending 兜底置 failed（worker 崩溃/入队失败自愈）
    import asyncio

    from app.services.maintenance_service import maintenance_loop

    maintenance_task = asyncio.create_task(maintenance_loop())
    logger.info("Application started")
    yield
    maintenance_task.cancel()


app = FastAPI(title="RAG 知识库问答系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

register_exception_handlers(app)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": {"code": "rate_limited", "message": "请求过于频繁，请稍后再试"}},
    )


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


app.include_router(api_router)
