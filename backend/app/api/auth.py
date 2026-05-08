"""STE-18：鉴权 API：/auth/login、/auth/refresh、/auth/me。

约定：
- 所有失败一律 401 + `{"detail": "..."}`，不区分原因，避免侧信道泄漏。
- /auth/login、/auth/refresh 在 middleware 中是公开路径，直接放行；
  /auth/me 走 middleware 注入 ContextVar 后再用 deps.get_current_user 取。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core import security
from app.core.config import get_settings
from app.core.deps import CurrentUser, MetaSession
from app.db.models import User
from app.services import auth_service, user_repo

router = APIRouter(prefix="/auth", tags=["auth"])


# ---- request / response 契约 ----


class LoginRequest(BaseModel):
    tenant_code: str = Field(..., min_length=1, max_length=64)
    # 这里用 str 而不是 EmailStr，避免引入 email-validator 额外依赖；
    # 真实业务校验交给数据库 unique 约束 + 前端 input type=email。
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AccessOnly(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    display_name: str | None
    roles: list[str]
    is_active: bool


# ---- 内部工具 ----


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def _build_token_pair(user: User) -> TokenPair:
    settings = get_settings()
    access = security.create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=list(user.roles or []),
    )
    refresh = security.create_refresh_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_expire_minutes * 60,
    )


# ---- 端点 ----


@router.post("/login", response_model=TokenPair, summary="账号密码登录")
async def login(
    body: LoginRequest,
    session: MetaSession,
) -> TokenPair:
    user = await auth_service.authenticate(
        session,
        tenant_code=body.tenant_code,
        email=body.email,
        password=body.password,
    )
    if user is None:
        raise _unauthorized()
    return _build_token_pair(user)


@router.post("/refresh", response_model=AccessOnly, summary="刷新 access token")
async def refresh(
    body: RefreshRequest,
    session: MetaSession,
) -> AccessOnly:
    try:
        claims = security.decode_token(body.refresh_token, expected_type="refresh")
    except security.InvalidTokenError as exc:
        raise _unauthorized() from exc

    # 双保险：验证用户仍存在且未禁用，避免「拿到 refresh 就能永久续 access」
    try:
        user_id = uuid.UUID(claims["sub"])
    except (ValueError, TypeError, KeyError) as exc:
        raise _unauthorized() from exc

    user = await user_repo.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()

    settings = get_settings()
    access = security.create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=list(user.roles or []),
    )
    return AccessOnly(access_token=access, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=UserResponse, summary="当前登录用户信息")
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        display_name=user.display_name,
        roles=list(user.roles or []),
        is_active=user.is_active,
    )
