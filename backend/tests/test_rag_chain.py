"""RAG 链路测试：用 Fake 组件验证编排逻辑（condense、空检索短路、citations 事件）。"""
import pytest

from app.services.rag import chain as chain_module
from app.services.rag.retrievers import RetrievedChunk


@pytest.fixture
def fake_chunks():
    return [
        RetrievedChunk(
            id="11111111-1111-1111-1111-111111111111",
            text="官方售价：299 元",
            score=0.85,
            metadata={"filename": "products.md", "page": 1},
        ),
        RetrievedChunk(
            id="22222222-2222-2222-2222-222222222222",
            text="续航 8 小时",
            score=0.72,
            metadata={"filename": "products.md", "page": 1},
        ),
    ]


async def test_empty_retrieval_short_circuit(monkeypatch):
    """检索为空 → 不调 LLM，直接返回固定文案。"""
    async def fake_embed(texts):
        return [[0.1] * 8 for _ in texts]

    async def fake_retrieve(*args, **kwargs):
        return []

    monkeypatch.setattr(chain_module, "embed_with_cache", fake_embed)
    monkeypatch.setattr(chain_module, "hybrid_retrieve", fake_retrieve)

    events = []
    async for event, payload in chain_module.run_qa_stream(None, "问题", []):
        events.append((event, payload))

    assert events == [("token", {"content": "知识库中未找到相关内容"})]


async def test_citations_event_emitted(monkeypatch, fake_chunks):
    """有检索结果 → 先发 citations 事件，再流式 token。"""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    async def fake_embed(texts):
        return [[0.1] * 8 for _ in texts]

    async def fake_retrieve(*args, **kwargs):
        return fake_chunks

    async def fake_get_cached(*a, **k):
        return None

    fake_llm = FakeListChatModel(responses=["回答内容"])
    monkeypatch.setattr(chain_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(chain_module, "embed_with_cache", fake_embed)
    monkeypatch.setattr(chain_module, "hybrid_retrieve", fake_retrieve)
    # 关闭答案缓存干扰
    monkeypatch.setattr(chain_module.cache, "get_cached_answer", fake_get_cached)
    monkeypatch.setattr(chain_module.cache, "set_cached_answer", _fake_set)

    events = []
    async for event, payload in chain_module.run_qa_stream(None, "问题", []):
        events.append((event, payload))

    kinds = [e for e, _ in events]
    assert kinds[0] == "citations"
    assert kinds[-1] == "usage"
    citations = events[0][1]["citations"]
    assert len(citations) == 2
    assert citations[0]["filename"] == "products.md"
    assert citations[0]["page"] == 1
    tokens = [p["content"] for e, p in events if e == "token"]
    assert "".join(tokens) == "回答内容"


async def _fake_set(*args, **kwargs):
    return None


async def test_condense_without_history_is_identity():
    """无历史时 condense 直接返回原问题（不调 LLM）。"""
    result = await chain_module.condense_question([], "蓝牙耳机续航？")
    assert result == "蓝牙耳机续航？"
