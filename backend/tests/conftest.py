"""测试夹具：独立测试库、建表种子、httpx AsyncClient。

测试库 schema 保证与模型定义一致：每次会话启动时 drop_all + create_all
（create_all 不会对已存在的表做增量 ALTER，重建是最简单可靠的同步方式；
测试库是纯临时数据，无保留价值）。
"""
import os

# 必须在 import app 前设置，指向测试库
os.environ["MYSQL_DB"] = "rag_qa_test"
os.environ["CHROMA_PERSIST_DIR"] = "storage/chroma_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/9"

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.init_db import init_db, seed_admin
from app.db.session import SessionLocal, engine
from app.main import app

# 测试环境禁用限流，避免多用例共享 IP 触发 429
limiter.enabled = False


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    async def _setup():
        # 重建全部表：schema 与模型定义严格一致（规避手工 ALTER 漂移）
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as db:
            await seed_admin(db)

    asyncio.run(_setup())
    yield
    asyncio.run(engine.dispose())


@pytest.fixture(autouse=True)
async def _reset_redis_per_test():
    """每个测试前重置 Redis 连接单例：pytest-asyncio 每测试新建 event loop，
    缓存连接绑定旧 loop 会导致挂起。"""
    from app.core.redis_client import get_redis

    get_redis.cache_clear()
    yield
    try:
        r = get_redis()
        await r.aclose()
    except Exception:
        pass
    get_redis.cache_clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db_session():
    async with SessionLocal() as db:
        yield db


@pytest.fixture
async def admin_token(client):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200
    return resp.json()["access_token"]
