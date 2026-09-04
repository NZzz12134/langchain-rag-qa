"""全局配置：单一来源（.env / 环境变量），Provider 与检索参数全部可配置切换。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # ===== 数据库 (MySQL) =====
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "rag_user"
    MYSQL_PASSWORD: str = "rag_pass_2024"
    MYSQL_DB: str = "rag_qa"

    # ===== Redis =====
    REDIS_URL: str = "redis://localhost:6379/0"

    # ===== JWT =====
    JWT_SECRET: str = "dev-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ===== LLM Provider =====
    LLM_PROVIDER: str = "qwen"
    LLM_MODEL: str = "qwen-plus"
    # 默认为空：由 provider 映射表兜底默认地址；显式设置则覆盖（切换 provider 时更不易踩坑）
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2048

    # ===== Embedding Provider =====
    EMBEDDING_PROVIDER: str = "dashscope"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_API_KEY: str = ""

    # ===== Rerank =====
    RERANK_ENABLED: bool = True
    RERANK_PROVIDER: str = "dashscope"  # dashscope(原生端点) | siliconflow 等(OpenAI 兼容)
    RERANK_MODEL: str = "gte-rerank"
    RERANK_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    RERANK_API_KEY: str = ""

    # ===== 检索 =====
    RETRIEVAL_MODE: str = "hybrid"  # hybrid | vector
    VECTOR_TOP_K: int = 10
    BM25_TOP_K: int = 10
    RRF_K: int = 60
    SCORE_THRESHOLD: float = 0.35
    RERANK_TOP_N: int = 5

    # ===== Chroma =====
    CHROMA_MODE: str = "embedded"  # embedded | server
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_TOKEN: str = ""
    CHROMA_PERSIST_DIR: str = "storage/chroma"

    # ===== 文件存储 =====
    STORAGE_DIR: str = "storage/documents"
    MAX_UPLOAD_MB: int = 50

    # ===== 缓存 TTL =====
    EMBED_CACHE_TTL: int = 2592000
    CHAT_CACHE_TTL: int = 3600
    LOGIN_LOCK_SECONDS: int = 900

    # ===== CORS =====
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        return BASE_DIR / self.STORAGE_DIR

    @property
    def chroma_persist_path(self) -> Path:
        return BASE_DIR / self.CHROMA_PERSIST_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
