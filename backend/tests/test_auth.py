"""认证流程测试：注册/登录/me/改密/锁定/权限。"""
import pytest


@pytest.fixture(autouse=True)
async def _clean_users(db_session):
    """每个测试前清理测试用户（保留 admin）。"""
    from sqlalchemy import delete

    from app.models import User

    await db_session.execute(delete(User).where(User.username != "admin"))
    await db_session.commit()
    yield


async def test_register_login_flow(client):
    # 注册
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "flowuser", "password": "abc12345"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"]
    assert data["user"]["username"] == "flowuser"
    assert data["user"]["role"] == "user"

    # 重复注册 409
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "flowuser", "password": "abc12345"},
    )
    assert resp.status_code == 409

    # 登录
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "flowuser", "password": "abc12345"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # me
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "flowuser"


async def test_wrong_password(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpass"},
    )
    assert resp.status_code == 401


async def test_change_password(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "pwuser", "password": "oldpass123"},
    )
    token = resp.json()["access_token"]

    # 原密码错误 → 400
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "bad", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400

    # 正确改密
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "oldpass123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # 旧密码失效，新密码可登录
    resp = await client.post("/api/v1/auth/login", json={"username": "pwuser", "password": "oldpass123"})
    assert resp.status_code == 401
    resp = await client.post("/api/v1/auth/login", json={"username": "pwuser", "password": "newpass456"})
    assert resp.status_code == 200


async def test_admin_seed_and_rbac(client):
    # admin 种子存在
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "admin"

    # 普通用户访问管理接口 → 403
    resp = await client.post(
        "/api/v1/auth/register", json={"username": "rbacuser", "password": "abc12345"}
    )
    token = resp.json()["access_token"]
    resp = await client.get("/api/v1/admin/kbs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403

    # 无 token → 401
    resp = await client.get("/api/v1/admin/kbs")
    assert resp.status_code == 401


class FakeRedis:
    """内存版 Redis：锁定计数逻辑测试用（真实连通性由开发环境验证）。"""

    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def incr(self, key):
        self.data[key] = int(self.data.get(key) or 0) + 1
        return self.data[key]

    async def expire(self, key, ttl):
        return True

    async def delete(self, *keys):
        for k in keys:
            self.data.pop(k, None)


async def test_login_lockout(client, monkeypatch):
    from app.services import auth_service

    fake_redis = FakeRedis()
    monkeypatch.setattr(auth_service, "get_redis", lambda: fake_redis)

    # 连续 5 次错误 → 锁定
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "lockuser", "password": "bad"},
        )
        assert resp.status_code == 401
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "lockuser", "password": "bad"},
    )
    assert resp.status_code == 403
    assert "锁定" in resp.json()["detail"]["message"]
