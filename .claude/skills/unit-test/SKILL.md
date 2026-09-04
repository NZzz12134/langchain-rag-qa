---
name: unit-test
description: 为本项目（LangChain RAG 知识库问答系统）编写、运行、修复后端单元测试时使用。触发场景：用户要求"写测试/单测"、"跑测试"、"测试报错"、新增后端功能后要求验证、或任何涉及 backend/tests 的改动。
---

# 单元测试 Skill（本项目专用）

## 测试框架与环境

- **框架**：pytest + pytest-asyncio（[pytest.ini](../../../backend/pytest.ini) 已配置 `asyncio_mode=auto`）
- **位置**：所有测试在 `backend/tests/`，文件命名 `test_*.py`
- **测试数据库**：独立库 `rag_qa_test`（**绝不使用开发库 rag_qa**）。[conftest.py](../../../backend/tests/conftest.py) 顶部在 import app 之前设置环境变量：
  ```python
  os.environ["MYSQL_DB"] = "rag_qa_test"
  os.environ["CHROMA_PERSIST_DIR"] = "storage/chroma_test"
  os.environ["REDIS_URL"] = "redis://localhost:6379/9"
  ```
  新测试如涉及环境切换，必须遵守同一模式（先设 env，再 import）。

## 运行命令

```bash
cd backend
PYTHONIOENCODING=utf-8 .venv/Scripts/python -m pytest tests/ -v        # 全部
.venv/Scripts/python -m pytest tests/test_auth.py::test_wrong_password -v  # 单个
.venv/Scripts/python -m pytest tests/ -x                                # 遇错即停
```

⚠️ 必须带 `PYTHONIOENCODING=utf-8`（Windows 下中文断言输出乱码）。

## 测试分层与写法

### 1. API 集成测试（走 ASGITransport，不依赖真实网络）

使用 [conftest.py](../../../backend/tests/conftest.py) 的 `client` fixture（httpx AsyncClient + ASGITransport）：

```python
async def test_something(client):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    resp = await client.get("/api/v1/admin/kbs", headers={"Authorization": f"Bearer {token}"})
```

参考范例：[test_auth.py](../../../backend/tests/test_auth.py)（认证/锁定/RBAC 全覆盖）。

### 2. 纯单元测试（解析器/分块器，无 DB 无网络）

直接调用函数，用 `tmp_path` 构造临时文件：

```python
def test_markdown_heading_paths(md_file):   # md_file 是 tmp_path fixture 产物
    docs = load_markdown(md_file)
    ...
```

参考范例：[test_parsing.py](../../../backend/tests/test_parsing.py)。

### 3. RAG 链路测试（外部依赖全 mock）

**铁律：测试绝不调用真实 LLM/Embedding/Rerank API**。用 monkeypatch 替换 [chain.py](../../../backend/app/services/rag/chain.py) 模块命名空间里的符号：

```python
monkeypatch.setattr(chain_module, "get_llm", lambda: FakeListChatModel(responses=["回答"]))
monkeypatch.setattr(chain_module, "embed_with_cache", fake_embed)       # async def
monkeypatch.setattr(chain_module, "hybrid_retrieve", fake_retrieve)    # async def
monkeypatch.setattr(chain_module.cache, "get_cached_answer", fake_get_cached)
```

参考范例：[test_rag_chain.py](../../../backend/tests/test_rag_chain.py)（空检索短路、citations 事件、condense）。

## 必知陷阱（本项目踩过的坑，写测试时绕开）

1. **monkeypatch 三参数形式**：`monkeypatch.setattr(模块, "符号名", 替换值)`。写成 `setattr(模块.符号, 值)` 会抛 TypeError
2. **异步 mock 必须 `async def`**：被 mock 的函数是 `await` 调用的，返回普通 lambda 会在 `await None` 处炸 TypeError
3. **共享可变 mock 对象**：登录锁定类测试的 FakeRedis 必须复用同一实例（每次调用返回新实例会导致计数丢失）：
   ```python
   fake_redis = FakeRedis()
   monkeypatch.setattr(auth_service, "get_redis", lambda: fake_redis)
   ```
4. **Redis 单例跨 loop 问题**：[conftest.py](../../../backend/tests/conftest.py) 的 autouse fixture `_reset_redis_per_test` 已处理（每测试前 `get_redis.cache_clear()`）。不要在测试里保存 `get_redis()` 返回的连接跨测试复用
5. **限流干扰**：conftest 已全局 `limiter.enabled = False`，测试内不要重新打开
6. **数据隔离**：auth 类测试用 autouse fixture 清理非 admin 用户（`delete(User).where(User.username != "admin")`）；涉及其他表的测试同理要自清理，保证可重复执行
7. **SSE 流测试**：不要用 `resp.read()` 一次性读（chunked 尾部会 IncompleteRead），逐行消费即可
8. **时间排序断言**：消息顺序类断言依赖 `seq` 列（created_at 是秒级精度不可靠），断言 user/assistant 交替时只比对 role 序列，不要比对时间戳相等

## 编写新测试的流程

1. 确认被测功能属于哪一层（API / 纯函数 / RAG 链路）
2. 按对应分层写法搭骨架，参考同层已有测试文件的风格
3. 外部依赖（LLM/Embedding/Rerank/Redis 状态）一律 mock；DB 走测试库
4. 运行 `pytest tests/test_xxx.py -v` 确认通过
5. 全部用例 `pytest tests/` 回归一遍（当前基线 15 个用例全绿才算完成）

## 验收标准

- 新增测试文件遵循 `test_*.py` 命名与分层规范
- 不产生对真实 API/生产数据的依赖
- 单独运行与全量运行都通过（测试间无执行顺序耦合）
- 前端无测试设施（未配置 vitest）；如需前端测试，先在 frontend 引入 vitest + @vue/test-utils，再按本 skill 的 mock 原则扩展
