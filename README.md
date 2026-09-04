# 企业级 RAG 知识库问答系统

基于 **LangChain + FastAPI + Vue 3** 的通用知识库问答系统。上传任意领域的知识文档（商品手册、规章制度、产品资料、图书文档等），用户即可通过浏览器进行**带引用溯源的多轮流式问答**；管理员可管理知识库、上传文档、查看使用统计。内置企业级能力：混合检索、缓存优化、限流、权限控制、状态自愈。

## ✨ 核心特性

| 特性 | 说明 |
|---|---|
| 流式问答 + 引用溯源 | SSE token 级流式输出；回答标注 `[1][2]` 编号，引用卡片显示片段文本、来源文件、页码/行号/章节，可点击查看全文 |
| 混合检索 | 向量检索（Chroma HNSW）+ BM25 中文分词 + RRF 融合 + Rerank 重排，`RETRIEVAL_MODE` 可切换 |
| 多轮对话 | 追问自动改写为独立检索问题（如"那它的续航呢？"→理解指代） |
| 防编造 | 检索为空时短路返回「知识库中未找到相关内容」，不调用大模型 |
| 多用户多会话 | 每用户独立会话、服务端持久化、跨设备找回历史；会话可绑定指定知识库或全库检索 |
| 7 类文档解析 | PDF / Word / Excel / CSV / Markdown / TXT / 网页 URL，异步解析 + 进度展示 + 失败重试 |
| 成本优化 | embedding 去重缓存（30 天）、答案缓存（1 小时），重复内容不重复调用 API |
| 安全 | JWT + bcrypt、RBAC 权限（管理接口前后端双重校验）、上传文件 magic bytes 校验、URL SSRF 防护、登录连败锁定、API 限流 |
| 管理后台 | 知识库 CRUD、文档上传/解析状态/重试/删除/分块预览、数据看板（问答趋势/反馈/文档分布） |

## 🏗 技术栈

| 层 | 选型 |
|---|---|
| RAG 框架 | LangChain 0.3（LCEL 链） |
| 后端 | Python 3.11 / FastAPI / SQLAlchemy 2.0 async / Celery |
| 数据库 | MySQL 8.0（用户/会话/消息/文档/分块/引用/反馈，8 张表） |
| 向量库 | Chroma 0.5（embedded / server 双模式） |
| 缓存/队列 | Redis 7（限流、embedding 去重、答案缓存、Celery broker） |
| 大模型 | 通义千问（默认 qwen-plus / text-embedding-v3 / gte-rerank），**Provider 抽象层可切换 DeepSeek/智谱等任意 OpenAI 兼容服务** |
| 前端 | Vue 3 + Element Plus + Pinia + Vite + ECharts |
| 部署 | Docker Compose（全栈）/ 本机开发模式 |

## 📁 目录结构

```
├── backend/                # 后端（FastAPI + LangChain）
│   ├── app/
│   │   ├── api/v1/         # 路由：认证/会话/聊天(SSE)/引用/反馈/知识库/文档/统计
│   │   ├── services/
│   │   │   ├── parsing/    # 7 类文档解析器 + 分块策略 + 解析 pipeline
│   │   │   ├── providers/  # LLM/Embedding/Rerank 抽象层（配置切换）
│   │   │   └── rag/        # Chroma/BM25/混合检索/问答链/缓存
│   │   ├── models/         # SQLAlchemy 模型
│   │   └── workers/        # Celery 文档解析任务
│   ├── tests/              # 36 个单元测试
│   └── requirements.txt
├── frontend/               # 前端（Vue 3 + Element Plus）
├── docs/                   # API 文档、部署手册
├── scripts/                # 冒烟测试脚本、示例文档生成
├── docker-compose.yml      # 生产全栈部署
├── docker-compose.dev.yml  # 开发基础设施（可选）
├── start_dev.bat           # Windows 一键启动（本机开发模式）
├── stop_dev.bat            # Windows 一键停止
└── .env.example            # 配置模板（复制为 backend/.env 后填写）
```

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- 二选一：
  - **Docker + Docker Compose**（推荐，一条命令启动全部服务）
  - **本机服务**：MySQL 8.0 + Redis（Windows 可用 Memurai）

### 方式一：Docker Compose 一键部署（推荐）

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env，必填项：
#   LLM_API_KEY / EMBEDDING_API_KEY / RERANK_API_KEY  —— 你的大模型 API Key
#   CHROMA_TOKEN      —— 任意随机串（如 openssl rand -hex 32），Chroma 认证用
#   MYSQL_ROOT_PASSWORD —— MySQL root 密码
#   JWT_SECRET        —— 任意随机串（如 openssl rand -hex 32）

# 2. 启动（首次构建约几分钟）
docker compose up -d --build

# 3. 访问
# 浏览器打开 http://localhost
```

停止：`docker compose down`（数据保存在卷中，不会丢失）

### 方式二：本机开发模式（不装 Docker）

<details>
<summary>Windows 步骤（Linux/macOS 类比，命令差异见备注）</summary>

**1. 准备数据库与 Redis**

- MySQL 8.0：建库建号（Linux/macOS 用包管理器安装后执行相同 SQL）

```sql
CREATE DATABASE rag_qa CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'rag_user'@'localhost' IDENTIFIED BY 'rag_pass_2024';
GRANT ALL PRIVILEGES ON rag_qa.* TO 'rag_user'@'localhost';
```

- Redis：Windows 安装 [Memurai](https://www.memurai.com/get-memurai)（Redis 兼容服务）；Linux/macOS 用系统包安装 redis
- ⚠️ 配置里 Redis/MySQL 地址用 `127.0.0.1`，不要用 `localhost`（Python 解析 localhost 优先 IPv6，而多数 Windows 服务只监听 IPv4）

**2. 后端**

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
cp ../.env.example .env                            # 填入你的 API Key
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

**3. 文档解析 Worker**（另开一个终端）

```bash
cd backend
# Windows 必须加 -P solo；Linux/macOS 可去掉
.venv\Scripts\python -m celery -A app.workers.celery_app worker -P solo -l info
```

**4. 前端**（再开一个终端）

```bash
cd frontend
npm install
npm run dev        # 打开 http://localhost:5173
```

**5. 一键脚本（仅 Windows）**：双击 `start_dev.bat` 启动全部、`stop_dev.bat` 停止全部。

</details>

## ⚙️ 配置说明（.env）

| 配置项 | 说明 |
|---|---|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_BASE_URL` | 大模型提供商。默认通义千问 qwen-plus；`LLM_PROVIDER=deepseek` 并留空 `LLM_BASE_URL` 即切换 DeepSeek（自动使用其默认地址） |
| `LLM_API_KEY` / `EMBEDDING_API_KEY` / `RERANK_API_KEY` | 三把 API Key（同一家可相同）。阿里云百炼申请：bailian.console.aliyun.com |
| `RERANK_ENABLED` | 重排序开关。未开通 gte-rerank 模型权限时建议 `false`（会自动降级，不影响回答） |
| `RETRIEVAL_MODE` | `hybrid`（混合检索，默认）/ `vector`（纯向量） |
| `CHROMA_MODE` | `embedded`（本机开发）/ `server`（生产，compose 已自动配置） |
| `JWT_SECRET` | 生产必改随机串 |
| `SCORE_THRESHOLD` / `VECTOR_TOP_K` / `RERANK_TOP_N` | 检索调优参数 |

> ⚠️ 更换 `EMBEDDING_MODEL` 后（向量维度变化），需在管理后台对全部文档执行「重新解析」重建向量。

## 📖 使用指南

### 管理员（默认账号 admin / 123456）

1. 登录后点击右上角头像菜单 →「知识库管理后台」
2. **知识库列表**：新建/编辑/启停/删除知识库
3. **文档管理**：选择目标知识库 → 上传文档或抓取网页 → 自动解析（可看进度）→ 成功后即可被问答检索
   - 支持格式：pdf（**文字版**，扫描版需先 OCR）/ docx / xlsx / csv / md / txt / URL，单文件 ≤ 50MB
   - 失败可查看具体原因（如「该 PDF 为扫描版/图片型」）并重试
4. **数据看板**：用户/会话/问答量/解析成功率/反馈趋势

### 普通用户

1. 注册账号登录
2. 点击「新建会话」：填写标题（可留空，自动生成）+ 选择检索范围（**全部知识库**或指定某一个）
3. 直接提问。回答流式输出，句末 `[1][2]` 对应下方引用卡片，点击卡片查看来源全文
4. 多轮追问自然对话；左侧可切换/重命名/删除会话，历史记录持久保存
5. 对回答点赞/点踩，帮助优化知识库质量

> ⚠️ **安全提醒**：部署后请立即在「个人中心 → 修改密码」中修改 admin 默认密码。

## 🧪 测试

```bash
cd backend
.venv\Scripts\python -m pytest tests/       # 36 个用例：认证/权限/会话/解析/安全/RAG 链路/反馈/统计
# 生成 HTML 报告
.venv\Scripts\python -m pytest tests/ --html=../docs/test-report.html --self-contained-html
```

测试规范见 `.claude/skills/unit-test/SKILL.md`。

## ❓ 常见问题

| 问题 | 解决 |
|---|---|
| 扫描版 PDF 解析失败 | 系统仅支持文字型 PDF。扫描件请先 OCR 转换，或转存为 Word/文本格式 |
| 上传后一直「待解析」 | Worker 未启动（开发模式需单独跑 Celery）；或 Redis 不可用——检查 `REDIS_URL` 是否为 `127.0.0.1` |
| 问答报「模型 API 返回错误」 | 检查 .env 的 API Key 是否正确、账号是否有额度 |
| 引用排序效果一般 | 开通 gte-rerank 模型权限（百炼控制台，免费额度），或调大 `RERANK_TOP_N` |
| 部署后访问不了 | 检查 `docker compose ps` 各服务是否 healthy；`curl http://localhost/healthz` 应返回 `{"status":"ok"}` |
| Windows 开发时 Celery 报错 | 必须使用 `-P solo` 参数 |
| 想换大模型厂商 | 改 .env 的 `LLM_PROVIDER`/`EMBEDDING_PROVIDER` 等字段即可，代码零改动（详见 docs/deployment.md） |

## 📚 更多文档

- [API 接口清单](docs/api.md) —— 全部路由、参数、SSE 事件协议
- [部署手册](docs/deployment.md) —— 生产部署、备份恢复、模型切换、性能调参、上线检查清单

## 📄 License

MIT
