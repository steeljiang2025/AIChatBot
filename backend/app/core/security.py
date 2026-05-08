"""STE-18：JWT + bcrypt 安全工具。

- access / refresh token 都用 HS256，密钥取自 `settings.jwt_secret`。
- claims 至少含 `sub`（user_id）/ `tenant_id` / `type`（access | refresh）/ `iat` / `exp`。
  access 额外带 `roles`；refresh 不带角色，刷新时再从用户表取。
- 鉴权失败统一抛 `InvalidTokenError`，由上层转 401，
  避免泄漏「过期 vs 篡改 vs 类型不符」差异给攻击者。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

# bcrypt 协议本身限制密码 ≤ 72 字节（超出部分被算法忽略）；
# 新版 bcrypt 4.x/5.x 不再静默截断而是直接抛 ValueError，所以我们在应用层
# 显式截断到 72 字节——这是 OWASP 推荐的做法，避免长密码登录失败。
# 历史背景：早期方案曾用 passlib[bcrypt]，但 passlib 1.7.x 与 bcrypt 4.x+
# 在 backend 探测阶段就会因这个限制崩，社区已迁移到 raw bcrypt / pwdlib。
_BCRYPT_MAX_BYTES: Final[int] = 72


class InvalidTokenError(Exception):
    """token 缺失 / 过期 / 签名错 / 类型不符等情况的统一异常。"""


# ---- 密码 ----


def _normalize_password(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_normalize_password(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_normalize_password(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # hash 字符串格式非法时 bcrypt 会抛 ValueError，统一兜成 False，避免 500
        return False


# ---- JWT ----


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def create_access_token(
    *,
    user_id: str,
    tenant_id: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    iat = _now_utc()
    exp = iat + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_expire_minutes)
    )
    claims: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": list(roles),
        "type": "access",
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    *,
    user_id: str,
    tenant_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    iat = _now_utc()
    exp = iat + (
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.jwt_refresh_expire_days)
    )
    claims: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "refresh",
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    if not token:
        raise InvalidTokenError("empty token")
    settings = get_settings()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if claims.get("type") != expected_type:
        raise InvalidTokenError("token type mismatch")
    return claims
