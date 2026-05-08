"""STE-24：/chat/stream 路由。

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

from app.core.config import get_settings
from app.core.deps import CurrentTenantId, CurrentUserId, MetaSession
from app.services import chat_service, session_repo

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatStreamRequest(BaseModel):
    session_id: uuid.UUID = Field(
        ..., description="ChatSession.id（也是 LangGraph thread_id）"
    )
    content: str = Field(..., min_length=1, max_length=4000)


_SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


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
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LangGraph workflow not available",
        )
    biz_engine = getattr(request.app.state, "business_engine", None)
    meta_factory = getattr(request.app.state, "meta_session_factory", None)
    if biz_engine is None or meta_factory is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend resources not initialized",
        )

    sess = await session_repo.get_session_scoped(
        db,
        session_id=body.session_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if sess is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")

    settings = get_settings()
    iterator = chat_service.stream_chat(
        graph=graph,
        meta_session=db,
        meta_session_factory=meta_factory,
        biz_engine=biz_engine,
        settings=settings,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=body.session_id,
        user_content=body.content,
    )
    return StreamingResponse(
        iterator,
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
