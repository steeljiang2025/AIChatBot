"""STE-18：Bearer JWT 鉴权中间件。

设计要点：
- 公开路径（`/auth/login`、`/auth/refresh`、`/health`、`/version`、文档）
  直接放行，避免造成「登录前就需要登录」的死锁。
- 其它路径必须携带合法 access token；缺失 / 篡改 / 过期 / 类型不符一律 401，
  对外不暴露具体原因（避免给攻击者反馈侧信道）。
- 鉴权成功后把 `tenant_id / user_id / roles` 写入 ContextVar，
  请求结束后通过 token reset 还原，避免泄漏到下一个请求。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core import security
from app.core.context import current_tenant_id, current_user_id, current_user_roles

_PUBLIC_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/auth/login",
        "/auth/refresh",
        "/health",
        "/version",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return True
    # /docs/oauth2-redirect 等 swagger 资源
    return path.startswith("/docs/") or path.startswith("/redoc/")


def _unauthorized() -> JSONResponse:
    """统一 401 响应；不区分原因，避免泄漏「过期 vs 篡改 vs 类型不符」差异。"""
    return JSONResponse({"detail": "Not authenticated"}, status_code=401)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if _is_public(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return _unauthorized()

        try:
            claims = security.decode_token(token, expected_type="access")
        except security.InvalidTokenError:
            return _unauthorized()

        tenant_token = current_tenant_id.set(str(claims["tenant_id"]))
        user_token = current_user_id.set(str(claims["sub"]))
        roles_token = current_user_roles.set(tuple(claims.get("roles", []) or []))
        try:
            return await call_next(request)
        finally:
            current_tenant_id.reset(tenant_token)
            current_user_id.reset(user_token)
            current_user_roles.reset(roles_token)
