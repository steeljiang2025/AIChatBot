"""STE-18：用户仓储。

抽出 `get_user_by_tenant_email` / `get_user_by_id` 两个查询函数，
路由 / service 层只依赖这两个函数，方便在测试里 monkeypatch 成内存
实现，避免真连 PG。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant, User


async def get_user_by_tenant_email(
    session: AsyncSession,
    tenant_code: str,
    email: str,
) -> User | None:
    """按 (tenant_code, email) 联合查找用户；未命中返回 None。"""
    stmt = (
        select(User)
        .join(Tenant, Tenant.id == User.tenant_id)
        .where(Tenant.code == tenant_code, User.email == email)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(
    session: AsyncSession,
    user_id: uuid.UUID | str,
) -> User | None:
    """按主键 id 查找用户；未命中返回 None。"""
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
