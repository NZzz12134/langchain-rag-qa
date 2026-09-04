"""SSE 流式问答端点。

事件协议：
    event: citations  data: {"citations":[{id,text,filename,page,row_start,row_end,heading_path,score}], "mode": "hybrid+rerank"}
    event: token      data: {"content": "..."}   ×N
    event: done       data: {"message_id": "...", "usage": {...}}
    event: error      data: {"message": "..."}
"""
import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_session_or_404
from app.core.exceptions import BusinessError
from app.core.rate_limit import limiter, user_or_ip_key
from app.models import User
from app.schemas.chat_schema import ChatIn
from app.services import message_service
from app.services.rag.chain import run_qa_stream
from app.utils.sse import sse_event, sse_ping

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# 全局并发信号量：防 LLM API 打爆
_llm_semaphore = asyncio.Semaphore(4)


@router.post("/chat/stream")
@limiter.limit("10/minute", key_func=user_or_ip_key)
async def chat_stream(
    request: Request,
    data: ChatIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(db, data.session_id, user.id)

    async def event_generator():
        await _llm_semaphore.acquire()
        assistant_msg = None
        full_content: list[str] = []
        try:
            # 历史（先取，不含本条提问）
            history = await message_service.get_recent_history(db, data.session_id, limit=6)

            # 落 user message + assistant 占位
            await message_service.create_user_message(db, data.session_id, data.question)
            assistant_msg = await message_service.create_assistant_placeholder(db, data.session_id)
            await message_service.touch_session(db, data.session_id)
            await db.commit()
            message_id = str(assistant_msg.id)

            yielded_citations = False
            stream = run_qa_stream(session.kb_id, data.question, history)
            # 心跳实现：用 asyncio.wait 限时等待下一事件，超时只发 ping、不取消
            # 生成器任务（asyncio.timeout 会取消内部 await，导致 generator 报废）
            next_event_task = asyncio.ensure_future(stream.__anext__())
            while True:
                done, _ = await asyncio.wait([next_event_task], timeout=15)
                if not done:
                    # 15 秒无事件：心跳保活（防 nginx/代理 read_timeout 掐断长流）
                    if await request.is_disconnected():
                        await message_service.finalize_message(
                            db, assistant_msg, "".join(full_content), status="stopped"
                        )
                        return
                    yield sse_ping()
                    continue
                try:
                    event, payload = next_event_task.result()
                except StopAsyncIteration:
                    break

                if await request.is_disconnected():
                    await message_service.finalize_message(
                        db, assistant_msg, "".join(full_content), status="stopped"
                    )
                    return

                if event == "citations":
                    yielded_citations = True
                    await message_service.save_citations(db, assistant_msg.id, payload["citations"])
                    yield sse_event("citations", payload)
                elif event == "token":
                    full_content.append(payload["content"])
                    yield sse_event("token", payload)
                elif event == "usage":
                    # usage 事件不发前端，仅记录
                    pass
                next_event_task = asyncio.ensure_future(stream.__anext__())

            await message_service.finalize_message(
                db, assistant_msg, "".join(full_content), status="completed"
            )
            yield sse_event("done", {"message_id": message_id})

            # 异步生成会话标题（首条消息）
            await message_service.auto_title_session(db, data.session_id, data.question)

        except asyncio.CancelledError:
            if assistant_msg is not None:
                await message_service.finalize_message(
                    db, assistant_msg, "".join(full_content), status="stopped"
                )
            raise
        except Exception as exc:
            logger.exception("chat stream failed")
            if assistant_msg is not None:
                await message_service.finalize_message(
                    db, assistant_msg, "".join(full_content), status="failed", error=str(exc)[:500]
                )
            yield sse_event("error", {"message": "生成失败，请稍后再试"})
        finally:
            _llm_semaphore.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
