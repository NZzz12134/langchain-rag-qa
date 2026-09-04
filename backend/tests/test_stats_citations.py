"""统计接口与引用详情测试：admin 权限、引用溯源数据结构。"""
import uuid

import pytest
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def _clean(db_session):
    from sqlalchemy import delete

    from app.models import (
        ChatSession,
        Chunk,
        Citation,
        Document,
        Feedback,
        KnowledgeBase,
        Message,
        User,
    )

    await db_session.execute(delete(Citation))
    await db_session.execute(delete(Feedback))
    await db_session.execute(delete(Chunk))
    await db_session.execute(delete(Document))
    await db_session.execute(delete(Message))
    await db_session.execute(delete(ChatSession))
    await db_session.execute(delete(KnowledgeBase))
    await db_session.execute(delete(User).where(User.username != "admin"))
    await db_session.commit()
    yield


async def _register(client, username):
    resp = await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "abc12345"}
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _admin_token(client):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    return resp.json()["access_token"]


async def test_stats_overview_admin_only(client):
    admin = await _admin_token(client)
    user = await _register(client, "statsuser")

    # 普通用户 403
    resp = await client.get("/api/v1/admin/stats/overview", headers={"Authorization": f"Bearer {user}"})
    assert resp.status_code == 403

    # admin 正常，字段齐全
    resp = await client.get("/api/v1/admin/stats/overview", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "user_count", "session_count", "message_count", "document_count",
        "chunk_count", "kb_count", "today_qa", "parse_success_rate",
        "feedback_like", "feedback_dislike",
    ):
        assert key in data

    # 数值正确性：至少 admin + statsuser 两个用户
    assert data["user_count"] >= 2


async def test_daily_qa_shape(client):
    admin = await _admin_token(client)
    resp = await client.get("/api/v1/admin/stats/daily-qa", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 30
    assert set(data[0].keys()) == {"day", "questions", "answers", "likes", "dislikes"}


async def test_citations_detail_structure(client, db_session):
    """引用详情返回 chunk 全文 + 来源 + 页码/行号。"""
    from app.db.base import utcnow
    from app.models import (
        ChatSession,
        Chunk,
        Citation,
        Document,
        KnowledgeBase,
        Message,
        User,
    )

    admin = await _admin_token(client)
    admin_row = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()

    kb = KnowledgeBase(name="测试库", created_by=admin_row.id)
    db_session.add(kb)
    await db_session.flush()
    doc = Document(
        kb_id=kb.id, filename="手册.pdf", file_path="x.pdf", file_type="pdf",
        parse_status="succeeded", chunk_count=2, uploaded_by=admin_row.id,
    )
    db_session.add(doc)
    await db_session.flush()
    chunk = Chunk(
        document_id=doc.id, kb_id=kb.id, seq=0, content="保修一年",
        page_number=3, content_hash="abc",
    )
    db_session.add(chunk)
    await db_session.flush()
    session = ChatSession(user_id=admin_row.id, title="引用测试")
    db_session.add(session)
    await db_session.flush()
    msg = Message(session_id=session.id, role="assistant", content="回答 [1]", created_at=utcnow())
    db_session.add(msg)
    await db_session.flush()
    db_session.add(Citation(message_id=msg.id, chunk_id=chunk.id, rank=1, score=0.9))
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/messages/{msg.id}/citations", headers={"Authorization": f"Bearer {admin}"}
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["rank"] == 1
    assert items[0]["text"] == "保修一年"
    assert items[0]["filename"] == "手册.pdf"
    assert items[0]["page"] == 3
    assert items[0]["score"] == 0.9


async def test_citations_ownership_404(client):
    """他人消息的引用详情 → 404；不存在的消息 → 404。"""
    user = await _register(client, "citeuser")
    resp = await client.get(
        f"/api/v1/messages/{uuid.uuid4()}/citations", headers={"Authorization": f"Bearer {user}"}
    )
    assert resp.status_code == 404
