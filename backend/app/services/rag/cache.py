"""聊天答案缓存：相同问题（+KB+prompt版本+模型）1 小时内复用，伪流式回放。"""
import hashlib
import json
import logging

from app.core.config import get_settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"


def _cache_key(question: str, kb_id: str, model: str) -> str:
    raw = f"{question}|{kb_id}|{PROMPT_VERSION}|{model}"
    return f"chatcache:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


async def get_cached_answer(question: str, kb_id: str | None, model: str) -> dict | None:
    key = _cache_key(question, kb_id or "all", model)
    try:
        data = await get_redis().get(key)
        return json.loads(data) if data else None
    except Exception:
        return None


async def set_cached_answer(
    question: str, kb_id: str | None, model: str, answer: str, citations: list[dict]
) -> None:
    key = _cache_key(question, kb_id or "all", model)
    try:
        await get_redis().set(
            key,
            json.dumps({"answer": answer, "citations": citations}, ensure_ascii=False),
            ex=get_settings().CHAT_CACHE_TTL,
        )
    except Exception as exc:
        logger.warning("chat cache write skipped: %s", exc)
