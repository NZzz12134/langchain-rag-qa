"""LLM Provider 抽象：默认通义千问（OpenAI 兼容），切换只改 .env。"""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings

_PROVIDER_DEFAULT_BASE = {
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=s.LLM_MODEL,
        api_key=s.LLM_API_KEY,
        base_url=s.LLM_BASE_URL or _PROVIDER_DEFAULT_BASE[s.LLM_PROVIDER],
        temperature=s.LLM_TEMPERATURE,
        max_tokens=s.LLM_MAX_TOKENS,
        streaming=True,
        request_timeout=120,
        max_retries=2,
    )
