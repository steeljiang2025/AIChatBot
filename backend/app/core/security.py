"""STE-18：JWT + bcrypt 安全工具（占位）。

本提交（commit 1）只暴露符号让测试 import 不爆，所有函数主体抛
`NotImplementedError`，由 commit 2 落地真实逻辑。

约定：
- access / refresh token 都用 HS256；claims 至少含 sub/tenant_id/type/iat/exp。
- 鉴权失败统一抛 `InvalidTokenError`，由上层路由 / 中间件转 401，
  避免泄漏「过期 vs 篡改 vs 类型不符」等可被探测的差异。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any


class InvalidTokenError(Exception):
    """token 缺失 / 过期 / 签名错 / 类型不符等情况的统一异常。"""


def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 哈希。"""
    raise NotImplementedError


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    raise NotImplementedError


def create_access_token(
    *,
    user_id: str,
    tenant_id: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """签发 access token；`expires_delta` 主要给测试构造过期 token。"""
    raise NotImplementedError


def create_refresh_token(
    *,
    user_id: str,
    tenant_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """签发 refresh token（不带 roles，刷新时再从用户表取）。"""
    raise NotImplementedError


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    """解码并校验 token；`expected_type` 限定 access/refresh，错类型一律拒绝。"""
    raise NotImplementedError
