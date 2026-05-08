"""STE-18：用户仓储（占位）。

抽出 `get_user_by_tenant_email` / `get_user_by_id` 两个查询函数，
方便在测试中 monkeypatch 成内存实现，避免真连 PG。
真实 SQLAlchemy 实现在 commit 3 落地。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import User


async def get_user_by_tenant_email(
    session: "AsyncSession",
    tenant_code: str,
    email: str,
) -> "User | None":
    """按 (tenant_code, email) 联合查找用户；未命中返回 None。"""
    raise NotImplementedError


async def get_user_by_id(
    session: "AsyncSession",
    user_id: uuid.UUID | str,
) -> "User | None":
    """按主键 id 查找用户；未命中返回 None。"""
    raise NotImplementedError
