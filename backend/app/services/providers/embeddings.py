"""Embedding Provider + Redis 去重缓存（省 API 成本核心）。

自定义 OpenAICompatEmbeddings（继承 LangChain Embeddings 接口）：
langchain-openai 0.3.6 的 OpenAIEmbeddings 会发送 token id + base64 格式，
DashScope 等国内兼容端点不支持 —— 这里用 httpx 直调，请求体固定 {"input": [str...], "model"}。
"""
import hashlib
import json
import logging
import zlib
from functools import lru_cache

import httpx
from langchain_core.embeddings import Embeddings
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32
EMBED_BATCH_SLEEP = 0.3  # 批间 sleep 防国内 API 限速


class OpenAICompatEmbeddings(Embeddings):
    """OpenAI 兼容 embedding 端点（DashScope / DeepSeek / SiliconFlow / 智谱）。"""

    def __init__(self, model: str, api_key: str, base_url: str, timeout: float = 60.0):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def _call(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": texts},
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        data.sort(key=lambda x: x.get("index", 0))
        return [d["embedding"] for d in data]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._call(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return (await self._call([text]))[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.aembed_documents(texts))

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAICompatEmbeddings:
    s = get_settings()
    return OpenAICompatEmbeddings(
        model=s.EMBEDDING_MODEL,
        api_key=s.EMBEDDING_API_KEY,
        base_url=s.EMBEDDING_BASE_URL,
    )


def _cache_key(text: str) -> str:
    s = get_settings()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embed:{s.EMBEDDING_PROVIDER}:{s.EMBEDDING_MODEL}:{digest}"


@retry(wait=wait_exponential(multiplier=1, max=60), stop=stop_after_attempt(3), reraise=True)
async def _embed_remote(texts: list[str]) -> list[list[float]]:
    return await get_embeddings().aembed_documents(texts)


async def embed_with_cache(texts: list[str]) -> list[list[float]]:
    """批量向量化，Redis 命中直接复用（TTL 30 天）。"""
    from app.core.redis_client import get_redis

    settings = get_settings()
    redis = get_redis()
    vectors: list[tuple[int, list[float]]] = []
    missing_idx: list[int] = []
    missing_texts: list[str] = []

    for i, text in enumerate(texts):
        key = _cache_key(text)
        cached = None
        try:
            cached = await redis.get(key)
        except Exception:
            pass
        if cached:
            try:
                vectors.append((i, json.loads(zlib.decompress(cached))))
                continue
            except Exception:
                pass
        missing_idx.append(i)
        missing_texts.append(text)

    if missing_texts:
        logger.info(
            "embedding cache hit %d/%d, calling API for %d",
            len(vectors), len(texts), len(missing_texts),
        )
        remote = await _embed_remote(missing_texts)
        for j, vec in enumerate(remote):
            idx = missing_idx[j]
            key = _cache_key(missing_texts[j])
            try:
                await redis.set(
                    key, zlib.compress(json.dumps(vec).encode("utf-8")),
                    ex=settings.EMBED_CACHE_TTL,
                )
            except Exception:
                pass
            vectors.append((idx, vec))

    vectors.sort(key=lambda x: x[0])
    return [v for _, v in vectors]


async def embed_texts_batched(texts: list[str]) -> list[list[float]]:
    """分批调用（带缓存），供解析 pipeline 使用。"""
    import asyncio

    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        all_vectors.extend(await embed_with_cache(batch))
        if i + EMBED_BATCH_SIZE < len(texts):
            await asyncio.sleep(EMBED_BATCH_SLEEP)
    return all_vectors
