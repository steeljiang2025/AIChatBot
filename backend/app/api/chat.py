"""STE-24：/chat/stream 路由（占位）。

`POST /chat/stream`：
- body: {session_id: UUID, content: str}
- 鉴权：JWTAuthMiddleware 已注入 ContextVar；CurrentUserId / CurrentTenantId 取出
- 校验 session 归属（404 if not）
- 返回 StreamingResponse(media_type='text/event-stream')，由 chat_service.stream_chat
  逐帧 yield SSE bytes
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.deps import CurrentTenantId, CurrentUserId, MetaSession

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatStreamRequest(BaseModel):
    session_id: uuid.UUID = Field(..., description="ChatSession.id（也是 LangGraph thread_id）")
    content: str = Field(..., min_length=1, max_length=4000)


@router.post(
    "/stream",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "SSE 事件流"},
        404: {"description": "会话不存在或不属于当前用户"},
        503: {"description": "LangGraph 工作流未装配"},
    },
)
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> StreamingResponse:
    """SSE 事件流：token / node / sql / rows / chart / error / done。"""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "chat_stream not implemented yet")
