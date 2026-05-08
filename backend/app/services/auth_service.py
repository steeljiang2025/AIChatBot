"""STE-18：认证服务（薄层）。

把「按 (tenant, email, password) 验身份」从路由抽出来，
未来要换 LDAP / OAuth2 / Magic Link 时只动这里，不动 router。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.models import User
from app.services import user_repo


async def authenticate(
    session: AsyncSession,
    *,
    tenant_code: str,
    email: str,
    password: str,
) -> User | None:
    """验证账号密码；任何一步失败都返回 None，调用方据此返回 401。"""
    user = await user_repo.get_user_by_tenant_email(session, tenant_code, email)
    if user is None:
        return None
    if not user.is_active:
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user
