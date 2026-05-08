"""STE-19：会话/消息仓储（占位）。

所有"按租户 + 用户作用域"的查询都集中在此层，service 层只负责
组合调用与事务边界，避免越权过滤逻辑散落到各处。

实现见 commit 2；本提交先暴露符号让测试 import 不爆。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import ChatSession, Message


# ---- ChatSession ----


async def list_sessions_for_user(
    session: "AsyncSession",
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list["ChatSession"], int]:
    """按 (tenant, user) 列出会话，按 updated_at desc；返回 (items, total)。"""
    raise NotImplementedError


async def get_session_scoped(
    session: "AsyncSession",
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> "ChatSession | None":
    """按 (id, tenant, user) 三元组查找；未命中（含越权）返回 None。"""
    raise NotImplementedError


async def create_session(
    session: "AsyncSession",
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
) -> "ChatSession":
    """创建并提交。"""
    raise NotImplementedError


async def update_session_title(
    session: "AsyncSession",
    *,
    obj: "ChatSession",
    title: str | None,
) -> "ChatSession":
    """对调用方已经鉴权过的 ChatSession 实例改 title 并提交。"""
    raise NotImplementedError


async def delete_session(
    session: "AsyncSession",
    *,
    obj: "ChatSession",
) -> None:
    """物理删除已经鉴权过的 ChatSession 实例（cascade 带走 messages）。"""
    raise NotImplementedError


# ---- Message ----


async def list_messages_for_session(
    session: "AsyncSession",
    *,
    session_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list["Message"], int]:
    """列出某会话的消息，按 created_at asc；调用方需先用
    get_session_scoped 校验过权限，本函数不做租户 / 用户过滤。"""
    raise NotImplementedError
