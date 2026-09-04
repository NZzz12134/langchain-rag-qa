"""Rerank Provider。

- RERANK_PROVIDER=dashscope：DashScope 原生端点（兼容模式不支持 /rerank）
  POST {base}/api/v1/services/rerank/text-rerank/text-rerank
- 其他（如 siliconflow）：OpenAI 兼容端点 POST {base}/rerank
"""
import logging
from functools import lru_cache

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DASHSCOPE_RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"


@lru_cache(maxsize=1)
def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30)


def _retryable(exc: BaseException) -> bool:
    """4xx 客户端错误（权限/格式）重试无意义，仅网络错误与 5xx 重试。"""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


@retry(
    wait=wait_exponential(multiplier=1, max=30),
    stop=stop_after_attempt(2),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
async def rerank(query: str, documents: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
    """返回 [(原文档索引, 相关度分数)]，按分数降序。"""
    s = get_settings()
    if not s.RERANK_ENABLED:
        raise RuntimeError("rerank disabled")
    top_n = top_n or min(len(documents), s.RERANK_TOP_N)
    headers = {"Authorization": f"Bearer {s.RERANK_API_KEY}"}

    if s.RERANK_PROVIDER == "dashscope":
        payload = {
            "model": s.RERANK_MODEL,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": top_n, "return_documents": False},
        }
        resp = await _client().post(DASHSCOPE_RERANK_URL, json=payload, headers=headers)
        resp.raise_for_status()
        results = resp.json().get("output", {}).get("results", [])
    else:
        payload = {
            "model": s.RERANK_MODEL,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        url = f"{s.RERANK_BASE_URL.rstrip('/')}/rerank"
        resp = await _client().post(url, json=payload, headers=headers)
        resp.raise_for_status()
        results = resp.json().get("results", [])

    return [(r["index"], r.get("relevance_score", 0.0)) for r in results]
