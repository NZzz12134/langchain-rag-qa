"""问题改写（condense）：多轮对话时把追问改写为独立可检索问题。"""
import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from app.services.providers.llm import get_llm
from app.services.rag.prompts import CONDENSE_PROMPT

logger = logging.getLogger(__name__)

_condense_chain = CONDENSE_PROMPT | get_llm() | StrOutputParser()


async def condense_question(history: list[dict], question: str) -> str:
    """history: [{"role": "user"/"assistant", "content": str}] 最近 3 轮，时间正序。"""
    if not history:
        return question
    messages = [
        HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
        for m in history[-6:]  # 最近 3 轮
    ]
    try:
        standalone = await _condense_chain.ainvoke(
            {"history": messages, "question": question}
        )
        return standalone.strip() or question
    except Exception as exc:
        logger.warning("condense failed, use raw question: %s", exc)
        return question
