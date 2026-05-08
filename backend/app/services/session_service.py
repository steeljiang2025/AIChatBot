"""STE-19：会话与消息服务层（占位）。

把"先按 (tenant, user) 鉴权 → 再做业务"的范式收敛到 service 层，
让 router 只关心 HTTP 形态、不重复写过滤逻辑。

约定：服务层任何"不存在 OR 越权"都返回 None / False，
由 router 统一转 404，避免泄漏存在性。

实现见 commit 2；本提交先暴露符号让测试 import 不爆。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import ChatSession, Message


async def list_sessions(
    session: "AsyncSession",
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list["ChatSession"], int]:
    raise NotImplementedError


async def create_session(
    session: "AsyncSession",
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
) -> "ChatSession":
    raise NotImplementedError


async def get_session(
    session: "AsyncSession",
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> "ChatSession | None":
    raise NotImplementedError


async def rename_session(
    session: "AsyncSession",
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
) -> "ChatSession | None":
    raise NotImplementedError


async def delete_session(
    session: "AsyncSession",
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    raise NotImplementedError


async def list_messages(
    session: "AsyncSession",
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list["Message"], int] | None:
    """先校验 session 归属于 (tenant, user)；不属于返回 None 让上层 404。"""
    raise NotImplementedError
