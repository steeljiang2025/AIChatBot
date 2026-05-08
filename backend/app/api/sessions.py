"""STE-19：会话与消息 CRUD。

所有路径都在 STE-18 JWT middleware 之后，依赖 ContextVar 注入的
`tenant_id` / `user_id` 做"先鉴权再操作"。任何「不存在 OR 越权」一律
返 404，避免泄漏存在性。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.core.deps import CurrentTenantId, CurrentUserId, MetaSession
from app.db.models import ChatSession, Message
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ---- request models ----


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=256)


class SessionPatch(BaseModel):
    """PATCH 语义：覆盖 title。null 表示清空标题。"""

    title: str | None = Field(default=None, max_length=256)


# ---- response models ----


class SessionResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int
    limit: int
    offset: int


class MessageResponse(BaseModel):
    id: str
    session_id: str
    tenant_id: str
    user_id: str | None
    role: str
    content: str
    token_usage: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    limit: int
    offset: int


# ---- helpers ----


def _to_session_response(s: ChatSession) -> SessionResponse:
    return SessionResponse(
        id=str(s.id),
        tenant_id=str(s.tenant_id),
        user_id=str(s.user_id),
        title=s.title,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _to_message_response(m: Message) -> MessageResponse:
    return MessageResponse(
        id=str(m.id),
        session_id=str(m.session_id),
        tenant_id=str(m.tenant_id),
        user_id=str(m.user_id) if m.user_id is not None else None,
        role=m.role,
        content=m.content,
        token_usage=m.token_usage,
        extra=m.extra,
        created_at=m.created_at,
    )


def _not_found() -> HTTPException:
    """会话不存在 OR 越权访问统一回 404，detail 不区分原因。"""
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Session not found")


# ---- endpoints ----


@router.get("", response_model=SessionListResponse, summary="列出当前用户的会话")
async def list_sessions(
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SessionListResponse:
    items, total = await session_service.list_sessions(
        db, tenant_id=tenant_id, user_id=user_id, limit=limit, offset=offset
    )
    return SessionListResponse(
        items=[_to_session_response(s) for s in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建一个空会话",
)
async def create_session(
    body: SessionCreate,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> SessionResponse:
    obj = await session_service.create_session(
        db, tenant_id=tenant_id, user_id=user_id, title=body.title
    )
    return _to_session_response(obj)


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="单个会话详情",
)
async def get_session(
    session_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> SessionResponse:
    obj = await session_service.get_session(
        db, session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )
    if obj is None:
        raise _not_found()
    return _to_session_response(obj)


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="重命名会话（覆盖 title）",
)
async def patch_session(
    session_id: uuid.UUID,
    body: SessionPatch,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> SessionResponse:
    obj = await session_service.rename_session(
        db,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        title=body.title,
    )
    if obj is None:
        raise _not_found()
    return _to_session_response(obj)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="物理删除会话（cascade 带走 messages）",
)
async def delete_session(
    session_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> Response:
    ok = await session_service.delete_session(
        db, session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )
    if not ok:
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{session_id}/messages",
    response_model=MessageListResponse,
    summary="列出某会话的消息（按 created_at asc）",
)
async def list_messages(
    session_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> MessageListResponse:
    result = await session_service.list_messages(
        db,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    if result is None:
        raise _not_found()
    items, total = result
    return MessageListResponse(
        items=[_to_message_response(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )
