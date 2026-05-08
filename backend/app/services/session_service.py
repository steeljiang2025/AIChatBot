"""STE-19：会话与消息服务层。

把"先按 (tenant, user) 鉴权 → 再做业务"的范式收敛到 service 层，
让 router 只关心 HTTP 形态、不重复写过滤逻辑。

约定：服务层任何"不存在 OR 越权"都返回 None / False，
由 router 统一转 404，避免泄漏存在性。
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, Message
from app.services import session_repo


async def list_sessions(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[ChatSession], int]:
    return await session_repo.list_sessions_for_user(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


async def create_session(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
) -> ChatSession:
    return await session_repo.create_session(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
    )


async def get_session(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatSession | None:
    return await session_repo.get_session_scoped(
        session,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )


async def rename_session(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
) -> ChatSession | None:
    obj = await session_repo.get_session_scoped(
        session,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if obj is None:
        return None
    return await session_repo.update_session_title(session, obj=obj, title=title)


async def delete_session(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    obj = await session_repo.get_session_scoped(
        session,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if obj is None:
        return False
    await session_repo.delete_session(session, obj=obj)
    return True


async def list_messages(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[Message], int] | None:
    """先校验 session 归属于 (tenant, user)；不属于返回 None 让上层 404。"""
    parent = await session_repo.get_session_scoped(
        session,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if parent is None:
        return None
    return await session_repo.list_messages_for_session(
        session,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )
