"""STE-19：会话 / 消息仓储。

所有"按租户 + 用户作用域"的查询都集中在此层，service 层只负责
组合调用与事务边界，避免越权过滤逻辑散落到各处。
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, Message

# ---- ChatSession ----


async def list_sessions_for_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[ChatSession], int]:
    """按 (tenant, user) 列出会话，按 updated_at desc；返回 (items, total)。"""
    base = select(ChatSession).where(
        ChatSession.tenant_id == tenant_id,
        ChatSession.user_id == user_id,
    )
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items_stmt = (
        base.order_by(ChatSession.updated_at.desc()).limit(limit).offset(offset)
    )
    result = await session.execute(items_stmt)
    return list(result.scalars().all()), int(total)


async def get_session_scoped(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatSession | None:
    """按 (id, tenant, user) 三元组查找；未命中（含越权）返回 None。"""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.tenant_id == tenant_id,
        ChatSession.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_session(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
) -> ChatSession:
    """创建并提交。"""
    obj = ChatSession(tenant_id=tenant_id, user_id=user_id, title=title)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update_session_title(
    session: AsyncSession,
    *,
    obj: ChatSession,
    title: str | None,
) -> ChatSession:
    """对调用方已经鉴权过的 ChatSession 实例改 title 并提交。"""
    obj.title = title
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_session(
    session: AsyncSession,
    *,
    obj: ChatSession,
) -> None:
    """物理删除已经鉴权过的 ChatSession 实例（cascade 带走 messages）。"""
    await session.delete(obj)
    await session.commit()


# ---- Message ----


async def list_messages_for_session(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[Message], int]:
    """列出某会话的消息，按 created_at asc；调用方需先用
    get_session_scoped 校验过权限，本函数不做租户 / 用户过滤。"""
    base = select(Message).where(Message.session_id == session_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items_stmt = (
        base.order_by(Message.created_at.asc()).limit(limit).offset(offset)
    )
    result = await session.execute(items_stmt)
    return list(result.scalars().all()), int(total)


async def add_message(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    role: str,
    content: str,
    extra: dict | None = None,
    token_usage: dict | None = None,
) -> Message:
    """STE-24：往某会话里追加一条消息。

    调用方需先用 get_session_scoped 校验过会话归属（本函数不做权限校验，
    只做插入）。tenant_id 冗余存到 Message 上，供 SQL 安全模块 / 审计
    在不 join 的情况下做多租户过滤。

    Returns: 已 flush 的 Message 实体（含 id / created_at）。
    """
    raise NotImplementedError
