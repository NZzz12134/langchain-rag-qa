"""RAG 问答编排链：condense → 混合检索 → QA 生成（LCEL + astream）。

返回 async generator：yield ("citations"|"token"|"usage", payload)
"""
import logging
import uuid
from typing import AsyncGenerator

from langchain_core.output_parsers import StrOutputParser

from app.core.config import get_settings
from app.services.providers.embeddings import embed_with_cache
from app.services.providers.llm import get_llm
from app.services.rag import cache
from app.services.rag.condense import condense_question
from app.services.rag.prompts import NO_CONTEXT_ANSWER, QA_PROMPT
from app.services.rag.retrievers import RetrievedChunk, hybrid_retrieve

logger = logging.getLogger(__name__)
settings = get_settings()


def _format_context(chunks: list[RetrievedChunk]) -> tuple[str, list[dict]]:
    """构造 prompt 上下文与 citations 载荷。引用编号 [1..n] 与 citations 顺序一致。"""
    parts = []
    citations = []
    for i, c in enumerate(chunks, start=1):
        src = c.metadata.get("filename") or c.metadata.get("source") or "未知来源"
        location = ""
        if c.metadata.get("page"):
            location += f"，第 {c.metadata['page']} 页"
        if c.metadata.get("row_start"):
            location += f"，第 {c.metadata['row_start']}-{c.metadata.get('row_end') or c.metadata['row_start']} 行"
        parts.append(f"[{i}] {c.text}\n（来源: {src}{location}）")
        citations.append(
            {
                "id": c.id,
                "text": c.text,
                "filename": c.metadata.get("filename"),
                "source": c.metadata.get("source"),
                "page": c.metadata.get("page"),
                "row_start": c.metadata.get("row_start"),
                "row_end": c.metadata.get("row_end"),
                "heading_path": c.metadata.get("heading_path"),
                "score": round(c.score, 4),
            }
        )
    return "\n\n".join(parts), citations


async def run_qa_stream(
    session_kb_id: uuid.UUID | None,
    question: str,
    history: list[dict],
) -> AsyncGenerator[tuple[str, dict], None]:
    """完整问答流。事件类型：citations / token / usage。"""
    # 1. 问题改写（带历史时）
    standalone = await condense_question(history, question)

    # 2. 检索
    try:
        query_embedding = (await embed_with_cache([standalone]))[0]
    except Exception as exc:
        logger.exception("embedding failed for question: %s", exc)
        yield "token", {"content": "检索服务暂时不可用，请稍后再试。"}
        return

    chunks = await hybrid_retrieve(standalone, session_kb_id, query_embedding)

    if not chunks:
        # 空检索短路：不调 LLM，防编造
        yield "token", {"content": NO_CONTEXT_ANSWER}
        return

    context, citations = _format_context(chunks)
    yield "citations", {"citations": citations, "mode": _retrieval_mode_desc()}

    # 3. 答案缓存
    model = settings.LLM_MODEL
    cached = await cache.get_cached_answer(standalone, str(session_kb_id) if session_kb_id else None, model)
    if cached:
        answer = cached["answer"]
        # 缓存里同时存了 citations，命中时同样要发（引用卡片不能丢）
        if cached.get("citations"):
            yield "citations", {"citations": cached["citations"], "mode": _retrieval_mode_desc()}
        # 伪流式回放：按 24 字符分片
        for i in range(0, len(answer), 24):
            yield "token", {"content": answer[i : i + 24]}
        yield "usage", {"cached": True}
        return

    # 4. LLM 流式生成
    chain = QA_PROMPT | get_llm() | StrOutputParser()
    full = []
    usage_meta = None
    try:
        async for piece in chain.astream(
            {"context": context, "question": standalone}
        ):
            full.append(piece)
            yield "token", {"content": piece}
    except Exception as exc:
        logger.exception("LLM stream failed")
        raise exc

    answer = "".join(full)
    if answer.strip():
        await cache.set_cached_answer(
            standalone, str(session_kb_id) if session_kb_id else None, model,
            answer, citations,
        )
    yield "usage", {"cached": False, "model": model}


def _retrieval_mode_desc() -> str:
    parts = [settings.RETRIEVAL_MODE]
    if settings.RERANK_ENABLED:
        parts.append("rerank")
    return "+".join(parts)
