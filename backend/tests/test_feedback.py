"""回答反馈 API 测试：提交/修改/删除、目标限制、所有权隔离。"""
import pytest
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def _clean(db_session):
    from sqlalchemy import delete

    from app.models import ChatSession, Feedback, Message, User

    await db_session.execute(delete(Feedback))
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


async def _make_session_with_messages(db_session, username: str, extra_user: bool = False):
    """造一个用户 + 会话 + 一对消息，返回 (token, session_id, assistant_msg_id)。"""
    from app.db.base import utcnow
    from app.models import ChatSession, Message, User

    result = await db_session.execute(select(User).where(User.username == username))
    user = result.scalar_one()
    session = ChatSession(user_id=user.id, title="反馈测试")
    db_session.add(session)
    await db_session.flush()
    user_msg = Message(session_id=session.id, role="user", content="问题", created_at=utcnow())
    ai_msg = Message(session_id=session.id, role="assistant", content="回答", created_at=utcnow())
    db_session.add_all([user_msg, ai_msg])
    await db_session.commit()
    return session.id, user_msg.id, ai_msg.id


async def test_feedback_submit_update_delete(client, db_session):
    token = await _register(client, "fbuser")
    _sid, _uid, ai_id = await _make_session_with_messages(db_session, "fbuser")
    auth = {"Authorization": f"Bearer {token}"}

    # 点赞
    resp = await client.post(f"/api/v1/messages/{ai_id}/feedback", json={"rating": "like"}, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["updated"] is False

    # 改为点踩（同消息同用户只有一条）
    resp = await client.post(f"/api/v1/messages/{ai_id}/feedback", json={"rating": "dislike"}, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["updated"] is True

    # 删除
    resp = await client.delete(f"/api/v1/messages/{ai_id}/feedback", headers=auth)
    assert resp.status_code == 204

    # 非法 rating 被 pydantic 拦截
    resp = await client.post(f"/api/v1/messages/{ai_id}/feedback", json={"rating": "bad"}, headers=auth)
    assert resp.status_code == 422


async def test_feedback_only_on_assistant_message(client, db_session):
    token = await _register(client, "fbuser2")
    _sid, user_msg_id, _ai_id = await _make_session_with_messages(db_session, "fbuser2")
    resp = await client.post(
        f"/api/v1/messages/{user_msg_id}/feedback",
        json={"rating": "like"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "只能对回答进行反馈" in resp.json()["detail"]["message"]


async def test_feedback_ownership_isolation(client, db_session):
    token_a = await _register(client, "fbownerA")
    token_b = await _register(client, "fbownerB")
    _sid, _uid, ai_id = await _make_session_with_messages(db_session, "fbownerA")

    # B 给 A 的回答点赞 → 404
    resp = await client.post(
        f"/api/v1/messages/{ai_id}/feedback",
        json={"rating": "like"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404

    # A 自己可以
    resp = await client.post(
        f"/api/v1/messages/{ai_id}/feedback",
        json={"rating": "like"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 201
