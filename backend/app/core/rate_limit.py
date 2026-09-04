"""API 限流（slowapi）：Redis 存储，Redis 不可用时自动降级内存。"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()


def user_or_ip_key(request):
    """优先按用户限流（get_current_user 挂在 request.state.user_id），未登录按 IP。"""
    user_id = getattr(request.state, "user_id", None)
    return user_id or get_remote_address(request)


# in_memory_fallback=["*"]：Redis 挂掉时限流降级到进程内存，不阻断服务
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    in_memory_fallback=["*"],
    default_limits=["200/minute"],
)
