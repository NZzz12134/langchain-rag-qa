"""会话与消息 API 测试：CRUD、所有权隔离、软删除、历史排序。"""
import uuid

import pytest


@pytest.fixture(autouse=True)
async def _clean(db_session):
    from sqlalchemy import delete

    from app.models import ChatSession, Message, User

    await db_session.execute(delete(Message))
    await db_session.execute(delete(ChatSession))
    await db_session.execute(delete(User).where(User.username != "admin"))
    await db_session.commit()
    yield


async def _register(client, username):
    resp = await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "abc12345"}
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def test_session_crud_flow(client):
    token = await _register(client, "sessuser1")

    # 新建
    resp = await client.post("/api/v1/sessions", json={"title": "我的会话"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    session_id = resp.json()["id"]
    assert resp.json()["title"] == "我的会话"

    # 列表
    resp = await client.get("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == session_id

    # 重命名
    resp = await client.patch(
        f"/api/v1/sessions/{session_id}", json={"title": "改名了"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "改名了"

    # 软删除
    resp = await client.delete(f"/api/v1/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
    resp = await client.get("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()["items"]) == 0


async def test_session_ownership_isolation(client, db_session):
    """用户 B 访问用户 A 的会话 → 404；消息历史同样隔离。"""
    token_a = await _register(client, "ownerA")
    token_b = await _register(client, "ownerB")

    resp = await client.post("/api/v1/sessions", json={"title": "A的会话"}, headers={"Authorization": f"Bearer {token_a}"})
    session_id = resp.json()["id"]

    # B 重命名 A 的会话 → 404
    resp = await client.patch(
        f"/api/v1/sessions/{session_id}", json={"title": "劫持"}, headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404

    # B 读 A 的消息历史 → 404
    resp = await client.get(
        f"/api/v1/sessions/{session_id}/messages", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404

    # B 删除 A 的会话 → 404
    resp = await client.delete(f"/api/v1/sessions/{session_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404


async def test_message_history_order_and_preview(client, db_session):
    """历史按 seq 正序；列表预览为最后一条消息。"""
    from app.db.base import utcnow
    from app.models import ChatSession, Message, User

    token = await _register(client, "histuser")

    # 直接 DB 造数据（同一秒内写入多条，模拟原秒级精度下的乱序风险场景）
    from datetime import timedelta

    user_row = (
        await db_session.execute(
            __import__("sqlalchemy").select(User).where(User.username == "histuser")
        )
    ).scalar_one()
    session = ChatSession(user_id=user_row.id, title="历史会话")
    db_session.add(session)
    await db_session.flush()
    now = utcnow()
    for i, (role, content) in enumerate(
        [("user", "问题1"), ("assistant", "回答1"), ("user", "问题2"), ("assistant", "回答2")]
    ):
        # 同一秒内、相隔仅微秒级（真实插入行为的模拟）
        db_session.add(
            Message(
                session_id=session.id, role=role, content=content,
                created_at=now + timedelta(microseconds=i * 1000),
            )
        )
    await db_session.commit()

    # 历史正序且交替
    resp = await client.get(
        f"/api/v1/sessions/{session.id}/messages", headers={"Authorization": f"Bearer {token}"}
    )
    items = resp.json()["items"]
    assert [m["role"] for m in items] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in items] == ["问题1", "回答1", "问题2", "回答2"]

    # 会话列表预览 = 最后一条
    resp = await client.get("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"})
    items = resp.json()["items"]
    assert items[0]["last_message_preview"] == "回答2"


async def test_invalid_session_404(client):
    token = await _register(client, "nobodyuser")
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/v1/sessions/{fake_id}/messages", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
