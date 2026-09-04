# API 清单（前缀 /api/v1）

鉴权：`Authorization: Bearer <JWT>`；错误统一格式 `{"detail": {"code": "...", "message": "..."}}`。

## 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/register | 注册 `{username, password, email?}` → token+user；限流 3/min/IP |
| POST | /auth/login | 登录 → token+user；限流 5/min，连败 5 次锁 15 分钟 |
| GET | /auth/me | 当前用户（含 role） |
| POST | /auth/change-password | `{old_password, new_password}` |

## 会话 / 消息

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /sessions | 我的会话分页（含最后消息预览、kb 名） |
| POST | /sessions | 新建 `{title?, kb_id?}` |
| PATCH | /sessions/{id} | 重命名 |
| DELETE | /sessions/{id} | 软删除 |
| GET | /sessions/{id}/messages | 历史消息分页（正序） |
| GET | /messages/{id}/citations | 回答的引用详情（chunk 全文 + 来源 + 页码/行号） |
| POST / DELETE | /messages/{id}/feedback | 点赞/点踩 `{rating: like|dislike, comment?}` |

## 问答（SSE）

**POST /chat/stream** `{session_id, question}` → `text/event-stream`：

```
event: citations   data: {"citations":[{id,text,filename,page,row_start,row_end,heading_path,score}], "mode":"hybrid+rerank"}
event: token       data: {"content":"..."}    (×N)
event: done        data: {"message_id":"..."}
event: error       data: {"message":"..."}
```

限流 10/min/用户；全局并发 4；空检索时 token 直接返回「知识库中未找到相关内容」。

## 知识库

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | /kbs | 登录用户 | 活跃知识库列表 |
| GET | /admin/kbs | admin | 列表（含文档/分块/状态统计） |
| POST | /admin/kbs | admin | 新建 |
| PATCH | /admin/kbs/{id} | admin | 编辑 / 启停 |
| DELETE | /admin/kbs/{id} | admin | 删除（级联清理向量） |

## 文档管理（admin）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /admin/documents?kb_id= | multipart 上传（pdf/docx/xlsx/csv/md/txt，≤50MB，SHA256 去重） |
| POST | /admin/documents/url?kb_id= | 网页抓取 `{url}` |
| GET | /admin/documents | 分页 + filter(kb_id/status/keyword) |
| GET | /admin/documents/{id} | 详情（进度/错误） |
| POST | /admin/documents/{id}/reparse | 重新解析 |
| POST | /admin/documents/{id}/retry | 失败重试 |
| DELETE | /admin/documents/{id} | 删除 |
| GET | /admin/documents/{id}/chunks | 分块预览 |

## 统计（admin）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /admin/stats/overview | 用户/会话/消息/文档/分块/今日问答/解析成功率/反馈 |
| GET | /admin/stats/daily-qa | 近 30 天每日提问/回答/点赞/点踩 |
| GET | /admin/stats/documents | 各知识库文档状态分布 |

## 健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /healthz | 存活探针 |
| GET | /readyz | （预留）依赖连通探针 |
