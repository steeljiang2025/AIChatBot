"""STE-18：鉴权 API 端到端测试。

通过 monkeypatch 把 `services.user_repo` 的两个查询函数兑换成内存实现，
不依赖真实 PostgreSQL，可在 CI / 本地 venv 内独立跑。

覆盖：
- /auth/login：成功 / 密码错 / 用户不存在 / 禁用用户
- /auth/me：未带 / 篡改 / 过期 / refresh 类型 token 全部 401；正常 200
- /auth/refresh：refresh 正常返回新 access；用 access 当 refresh → 401；垃圾 → 401
- 公开路径 /health、/openapi.json 不被 middleware 拦截
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import security


# ---- 测试夹具：构造 dict-like 用户对象 ----


_ALICE_ID = "00000000-0000-0000-0000-000000000001"
_ACME_TENANT_ID = "00000000-0000-0000-0000-0000000000aa"
_ALICE_PWD = "S3cret-Pwd!"


class _FakeUser:
    """模拟 ORM `User` 对象，仅暴露鉴权层会读到的属性。"""

    def __init__(
        self,
        *,
        user_id: str,
        tenant_id: str,
        email: str,
        password_hash: str,
        roles: list[str],
        is_active: bool,
        display_name: str | None,
    ) -> None:
        self.id = uuid.UUID(user_id)
        self.tenant_id = uuid.UUID(tenant_id)
        self.email = email
        self.password_hash = password_hash
        self.roles = roles
        self.is_active = is_active
        self.display_name = display_name


@pytest.fixture()
def alice() -> _FakeUser:
    return _FakeUser(
        user_id=_ALICE_ID,
        tenant_id=_ACME_TENANT_ID,
        email="alice@example.com",
        password_hash=security.hash_password(_ALICE_PWD),
        roles=["analyst"],
        is_active=True,
        display_name="Alice",
    )


@pytest.fixture()
def inactive_user() -> _FakeUser:
    return _FakeUser(
        user_id="00000000-0000-0000-0000-000000000002",
        tenant_id=_ACME_TENANT_ID,
        email="banned@example.com",
        password_hash=security.hash_password(_ALICE_PWD),
        roles=[],
        is_active=False,
        display_name="Banned",
    )


@pytest.fixture()
def auth_app(
    monkeypatch: pytest.MonkeyPatch,
    alice: _FakeUser,
    inactive_user: _FakeUser,
) -> Any:
    """构造 app 并 mock 数据库探针 + user_repo 查询。"""

    async def _fake_ping(_engine: Any) -> bool:
        return True

    monkeypatch.setattr("app.api.health.ping_engine", _fake_ping)
    monkeypatch.setattr("app.main.ping_engine", _fake_ping)

    users_by_email = {
        ("acme", alice.email): alice,
        ("acme", inactive_user.email): inactive_user,
    }
    users_by_id = {str(alice.id): alice, str(inactive_user.id): inactive_user}

    async def _get_user_by_tenant_email(
        _session: Any, tenant_code: str, email: str
    ) -> _FakeUser | None:
        return users_by_email.get((tenant_code, email))

    async def _get_user_by_id(_session: Any, user_id: Any) -> _FakeUser | None:
        return users_by_id.get(str(user_id))

    monkeypatch.setattr(
        "app.services.user_repo.get_user_by_tenant_email", _get_user_by_tenant_email
    )
    monkeypatch.setattr("app.services.user_repo.get_user_by_id", _get_user_by_id)

    # 延迟 import：避免在 monkeypatch 之前 `app.main` 把真实 user_repo 名字捕获到本地变量
    from app.main import create_app

    return create_app()


@pytest.fixture()
async def auth_client(auth_app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---- /auth/login ----


async def test_login_success_returns_access_and_refresh(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "acme",
            "email": "alice@example.com",
            "password": _ALICE_PWD,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert isinstance(body["expires_in"], int) and body["expires_in"] > 0


async def test_login_wrong_password_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "acme",
            "email": "alice@example.com",
            "password": "WRONG",
        },
    )
    assert r.status_code == 401


async def test_login_unknown_user_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "acme",
            "email": "nobody@example.com",
            "password": "x",
        },
    )
    assert r.status_code == 401


async def test_login_unknown_tenant_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "ghost",
            "email": "alice@example.com",
            "password": _ALICE_PWD,
        },
    )
    assert r.status_code == 401


async def test_login_inactive_user_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "acme",
            "email": "banned@example.com",
            "password": _ALICE_PWD,
        },
    )
    assert r.status_code == 401


# ---- /auth/me ----


async def test_me_without_token_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/auth/me")
    assert r.status_code == 401


async def test_me_with_invalid_token_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


async def test_me_with_wrong_scheme_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/auth/me", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


async def test_me_with_expired_token_returns_401(auth_client: AsyncClient) -> None:
    expired = security.create_access_token(
        user_id=_ALICE_ID,
        tenant_id=_ACME_TENANT_ID,
        roles=["analyst"],
        expires_delta=timedelta(seconds=-1),
    )
    r = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert r.status_code == 401


async def test_me_with_refresh_token_returns_401(auth_client: AsyncClient) -> None:
    """access 中间件不接受 refresh 类型 token。"""
    refresh = security.create_refresh_token(user_id=_ALICE_ID, tenant_id=_ACME_TENANT_ID)
    r = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert r.status_code == 401


async def test_me_with_valid_token_returns_user_info(auth_client: AsyncClient) -> None:
    login = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "acme",
            "email": "alice@example.com",
            "password": _ALICE_PWD,
        },
    )
    access = login.json()["access_token"]
    r = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == _ALICE_ID
    assert body["tenant_id"] == _ACME_TENANT_ID
    assert body["email"] == "alice@example.com"
    assert body["display_name"] == "Alice"
    assert body["roles"] == ["analyst"]
    assert body["is_active"] is True


# ---- /auth/refresh ----


async def test_refresh_with_valid_refresh_token_returns_new_access(
    auth_client: AsyncClient,
) -> None:
    login = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "acme",
            "email": "alice@example.com",
            "password": _ALICE_PWD,
        },
    )
    refresh = login.json()["refresh_token"]
    r = await auth_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert isinstance(body["expires_in"], int) and body["expires_in"] > 0


async def test_refresh_with_access_token_returns_401(auth_client: AsyncClient) -> None:
    """refresh 接口拒绝 access 类型 token。"""
    login = await auth_client.post(
        "/auth/login",
        json={
            "tenant_code": "acme",
            "email": "alice@example.com",
            "password": _ALICE_PWD,
        },
    )
    access = login.json()["access_token"]
    r = await auth_client.post("/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401


async def test_refresh_with_garbage_returns_401(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401


async def test_refresh_with_expired_refresh_returns_401(
    auth_client: AsyncClient,
) -> None:
    expired = security.create_refresh_token(
        user_id=_ALICE_ID,
        tenant_id=_ACME_TENANT_ID,
        expires_delta=timedelta(seconds=-1),
    )
    r = await auth_client.post("/auth/refresh", json={"refresh_token": expired})
    assert r.status_code == 401


# ---- 公开路径不被 middleware 拦截 ----


async def test_health_remains_public_without_token(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/health")
    assert r.status_code == 200


async def test_openapi_remains_public_without_token(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/openapi.json")
    assert r.status_code == 200
