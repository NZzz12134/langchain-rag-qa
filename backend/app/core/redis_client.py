"""Redis 异步客户端单例。Redis 不可用时各业务层自行 try/except 降级。"""
from functools import lru_cache

from redis import asyncio as aioredis

from app.core.config import get_settings


@lru_cache
def get_redis() -> aioredis.Redis:
    return aioredis.from_url(
        get_settings().REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1.5,
        socket_timeout=1.5,  # 短超时：缓存层有降级语义，快失败优于慢重试拖垮主流程
        socket_keepalive=True,
        health_check_interval=30,  # 空闲连接健康检查，避免被服务端关闭后首次写入超时
        # 注意：不启用 retry_on_timeout —— 关键路径上重试会放大 Redis 故障影响
    )
