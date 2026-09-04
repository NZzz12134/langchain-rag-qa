# 部署手册

## 一、开发模式（本机，无 Docker）

本仓库开发环境即按此模式运行（MySQL 8.0 本机安装版 + Memurai Redis + Chroma 嵌入式）。

1. **MySQL 8.0**：建库建号（见 README）。修改 root/rag_user 密码时同步改 `backend/.env`
2. **Redis**：Windows 安装 Memurai（服务自启）；Linux/macOS 用系统包管理器
3. **后端**：`cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000`
4. **Worker**：`cd backend && .venv/Scripts/python -m celery -A app.workers.celery_app worker -P solo -l info`
   - ⚠️ Windows 下 Celery 必须 `-P solo`（prefork 不可用）
   - ⚠️ 开发模式 Chroma 为嵌入式（`CHROMA_MODE=embedded`），**API 与 Worker 各自持有一个嵌入式实例会互相锁冲突**——因此开发模式必须保持：Celery 单 worker + 单进程。若需多进程，切 `CHROMA_MODE=server`
5. **前端**：`cd frontend && npm run dev`（vite 已配置 `/api` 代理到 8000，SSE 缓冲已关闭）

## 二、生产模式（Docker Compose）

```bash
# 1. 配置
cp .env.example .env
#   - JWT_SECRET：改为随机长字符串（openssl rand -hex 32）
#   - MYSQL_ROOT_PASSWORD：MySQL root 密码
#   - LLM/EMBEDDING/RERANK_API_KEY：真实 key
#   - CORS_ORIGINS：生产域名（若前端走 nginx 同域反代则无需改）

# 2. 构建并启动
docker compose up -d --build

# 3. 验证
curl http://localhost/healthz          # 经 nginx
docker compose ps                      # 6 个服务 running/healthy
```

生产模式下 compose 已强制覆盖 `CHROMA_MODE=server`、`CHROMA_HOST=chroma`，worker 用 prefork 并发 2。

### 升级 / 备份

```bash
# 数据备份：MySQL + Chroma 卷（卷名在 compose 中显式声明，见 docker-compose.yml volumes 段）
docker compose exec mysql mysqldump -u root -p rag_qa > backup.sql
docker run --rm -v $(pwd):/b -v rag_qa_chroma_data:/d alpine tar czf /b/chroma_backup.tgz -C /d .

# 恢复
docker compose exec -T mysql mysql -u root -p rag_qa < backup.sql
docker run --rm -v $(pwd):/b -v rag_qa_chroma_data:/d alpine tar xzf /b/chroma_backup.tgz -C /d
```

### 表结构升级（重要）

`create_all` 不会对已存在的表做增量 ALTER。开发期手工改过表结构后，生产升级需要执行等价 DDL（如曾手工执行 `ALTER TABLE messages ADD COLUMN seq INT NOT NULL AUTO_INCREMENT UNIQUE AFTER id;`）。后续引入 alembic 迁移后可彻底替代手工 DDL。

### 上线检查清单

- [ ] admin 密码已修改（默认 123456 必须改！）
- [ ] JWT_SECRET 已替换为随机串
- [ ] .env 未提交到版本库（.gitignore 已排除）
- [ ] 防火墙仅开放 80/443（Chroma 8001、Redis 6379、MySQL 3306 不对外）
- [ ] 生产启用 HTTPS（nginx 前挂证书或改 compose 端口映射）
- [ ] 定期备份 MySQL + Chroma 卷

## 三、模型切换（Provider 抽象）

| 场景 | 操作 |
|---|---|
| 换 LLM（如 DeepSeek） | .env：`LLM_PROVIDER=deepseek`、`LLM_BASE_URL=https://api.deepseek.com/v1`、`LLM_MODEL=deepseek-chat` |
| 换 Embedding | .env：`EMBEDDING_*` 三项。⚠️ **换模型=维度变化，必须重建向量**：删除知识库重建，或在管理端对全部文档点「重新解析」（collection 名含模型 hash，自动启用新 collection，旧 collection 保留需手动清理） |
| 关 Rerank | `RERANK_ENABLED=false` |
| 纯向量检索 | `RETRIEVAL_MODE=vector` |

## 四、性能调参

| 参数 | 默认 | 说明 |
|---|---|---|
| VECTOR_TOP_K / SCORE_THRESHOLD | 10 / 0.35 | 向量召回数与 cosine 阈值，BGE 系起步值；漏召回调低阈值 |
| BM25_TOP_K / RRF_K | 10 / 60 | BM25 召回数 / RRF 融合常数 |
| RERANK_TOP_N | 5 | 重排后送 LLM 的块数 |
| CHAT_CACHE_TTL | 3600 | 相同问题答案缓存（Redis） |
| EMBED_CACHE_TTL | 2592000 | embedding 去重缓存，省 API 费用核心 |
| worker --concurrency | 2 | 解析并发（受 embedding API 限速约束） |
