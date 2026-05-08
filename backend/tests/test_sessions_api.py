"""STE-19：会话与消息 CRUD 端到端测试。

策略：
- access token 直接用 STE-18 的 security.create_access_token 构造，
  避免再 mock user_repo（sessions 端点用 ContextVar 拿 user_id/tenant_id，
  不会去查 users 表）。
- session_repo 的全部函数 monkeypatch 成 _SessionStore 上的内存实现，
  数据存在 fixture 实例里，测试间相互隔离。
- 不连真实 PG，跑得快。

覆盖点：
- 鉴权：未带 token / 篡改 token → 401
- list：空 / 多条 / 分页 / 仅返当前用户的
- create：带 title / 不带 title
- get / patch / delete：owner 200|204；同租户跨用户 → 404；跨租户 → 404；不存在 → 404
- list messages：owner 200 + 排序 + 分页；越权 → 404
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import security


# ---- 测试身份 ----


_USER_A = uuid.uuid4()  # alice in tenant X
_USER_B = uuid.uuid4()  # bob in tenant X (跨用户验证)
_USER_C = uuid.uuid4()  # carol in tenant Y (跨租户验证)
_TENANT_X = uuid.uuid4()
_TENANT_Y = uuid.uuid4()


def _make_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    return security.create_access_token(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        roles=["analyst"],
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token_alice() -> str:
    return _make_token(user_id=_USER_A, tenant_id=_TENANT_X)


def _token_bob() -> str:
    return _make_token(user_id=_USER_B, tenant_id=_TENANT_X)


def _token_carol() -> str:
    return _make_token(user_id=_USER_C, tenant_id=_TENANT_Y)


# ---- 内存替身 ----


class _FakeSession:
    """模拟 ORM ChatSession，仅暴露 schema 用到的字段。"""

    def __init__(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None,
    ) -> None:
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.title = title
        now = datetime.now(tz=timezone.utc)
        self.created_at = now
        self.updated_at = now


class _FakeMessage:
    def __init__(
        self,
        *,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        role: str,
        content: str,
        created_at: datetime,
    ) -> None:
        self.id = uuid.uuid4()
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.role = role
        self.content = content
        self.token_usage: dict[str, Any] | None = None
        self.extra: dict[str, Any] | None = None
        self.created_at = created_at


class _SessionStore:
    """所有 session_repo 函数的内存实现；签名与真实 repo 对齐。"""

    def __init__(self) -> None:
        self.sessions: dict[uuid.UUID, _FakeSession] = {}
        self.messages: dict[uuid.UUID, list[_FakeMessage]] = {}

    # 测试辅助
    def seed_message(
        self,
        *,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        role: str,
        content: str,
        offset_ms: int = 0,
    ) -> _FakeMessage:
        msg = _FakeMessage(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            content=content,
            created_at=datetime.now(tz=timezone.utc) + timedelta(milliseconds=offset_ms),
        )
        self.messages.setdefault(session_id, []).append(msg)
        return msg

    # session_repo 接口实现
    async def list_sessions_for_user(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[_FakeSession], int]:
        owned = [
            s
            for s in self.sessions.values()
            if s.tenant_id == tenant_id and s.user_id == user_id
        ]
        owned.sort(key=lambda s: s.updated_at, reverse=True)
        return owned[offset : offset + limit], len(owned)

    async def get_session_scoped(
        self,
        _db: Any,
        *,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> _FakeSession | None:
        s = self.sessions.get(session_id)
        if s is None:
            return None
        if s.tenant_id != tenant_id or s.user_id != user_id:
            return None
        return s

    async def create_session(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None,
    ) -> _FakeSession:
        s = _FakeSession(tenant_id=tenant_id, user_id=user_id, title=title)
        self.sessions[s.id] = s
        return s

    async def update_session_title(
        self,
        _db: Any,
        *,
        obj: _FakeSession,
        title: str | None,
    ) -> _FakeSession:
        obj.title = title
        obj.updated_at = datetime.now(tz=timezone.utc)
        return obj

    async def delete_session(self, _db: Any, *, obj: _FakeSession) -> None:
        self.sessions.pop(obj.id, None)
        self.messages.pop(obj.id, None)

    async def list_messages_for_session(
        self,
        _db: Any,
        *,
        session_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[_FakeMessage], int]:
        msgs = sorted(
            self.messages.get(session_id, []), key=lambda m: m.created_at
        )
        return msgs[offset : offset + limit], len(msgs)


# ---- fixtures ----


@pytest.fixture()
def store() -> _SessionStore:
    return _SessionStore()


@pytest.fixture()
def auth_app(monkeypatch: pytest.MonkeyPatch, store: _SessionStore) -> Any:
    async def _fake_ping(_engine: Any) -> bool:
        return True

    monkeypatch.setattr("app.api.health.ping_engine", _fake_ping)
    monkeypatch.setattr("app.main.ping_engine", _fake_ping)

    monkeypatch.setattr(
        "app.services.session_repo.list_sessions_for_user",
        store.list_sessions_for_user,
    )
    monkeypatch.setattr(
        "app.services.session_repo.get_session_scoped", store.get_session_scoped
    )
    monkeypatch.setattr("app.services.session_repo.create_session", store.create_session)
    monkeypatch.setattr(
        "app.services.session_repo.update_session_title", store.update_session_title
    )
    monkeypatch.setattr("app.services.session_repo.delete_session", store.delete_session)
    monkeypatch.setattr(
        "app.services.session_repo.list_messages_for_session",
        store.list_messages_for_session,
    )

    from app.main import create_app

    return create_app()


@pytest.fixture()
async def client(auth_app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---- 鉴权 ----


async def test_list_sessions_without_token_returns_401(client: AsyncClient) -> None:
    r = await client.get("/sessions")
    assert r.status_code == 401


async def test_list_sessions_with_garbage_token_returns_401(client: AsyncClient) -> None:
    r = await client.get("/sessions", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_list_sessions_with_refresh_token_returns_401(client: AsyncClient) -> None:
    refresh = security.create_refresh_token(
        user_id=str(_USER_A), tenant_id=str(_TENANT_X)
    )
    r = await client.get("/sessions", headers=_bearer(refresh))
    assert r.status_code == 401


# ---- list ----


async def test_list_sessions_empty(client: AsyncClient) -> None:
    r = await client.get("/sessions", headers=_bearer(_token_alice()))
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 20
    assert body["offset"] == 0


async def test_list_sessions_returns_only_owned(client: AsyncClient) -> None:
    # alice 在 tenant X 创 2 条
    await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "A1"}
    )
    await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "A2"}
    )
    # bob 在 tenant X 创 1 条
    await client.post(
        "/sessions", headers=_bearer(_token_bob()), json={"title": "B1"}
    )
    # carol 在 tenant Y 创 1 条
    await client.post(
        "/sessions", headers=_bearer(_token_carol()), json={"title": "C1"}
    )

    r = await client.get("/sessions", headers=_bearer(_token_alice()))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    titles = sorted(s["title"] for s in body["items"])
    assert titles == ["A1", "A2"]


async def test_list_sessions_pagination(client: AsyncClient) -> None:
    for i in range(5):
        await client.post(
            "/sessions", headers=_bearer(_token_alice()), json={"title": f"S{i}"}
        )
    r = await client.get(
        "/sessions?limit=2&offset=1", headers=_bearer(_token_alice())
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


# ---- create ----


async def test_create_session_returns_full_object(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "Hello"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Hello"
    assert uuid.UUID(body["id"])
    assert body["tenant_id"] == str(_TENANT_X)
    assert body["user_id"] == str(_USER_A)
    assert body["created_at"]
    assert body["updated_at"]


async def test_create_session_without_title(client: AsyncClient) -> None:
    r = await client.post("/sessions", headers=_bearer(_token_alice()), json={})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] is None


# ---- get one ----


async def test_get_session_owner(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "X"}
    )
    sid = r.json()["id"]
    r2 = await client.get(f"/sessions/{sid}", headers=_bearer(_token_alice()))
    assert r2.status_code == 200
    assert r2.json()["title"] == "X"


async def test_get_session_unknown_id_returns_404(client: AsyncClient) -> None:
    fake = uuid.uuid4()
    r = await client.get(f"/sessions/{fake}", headers=_bearer(_token_alice()))
    assert r.status_code == 404


async def test_get_session_cross_user_returns_404(client: AsyncClient) -> None:
    """同租户跨用户访问 → 404，不暴露存在性。"""
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "A"}
    )
    sid = r.json()["id"]
    r2 = await client.get(f"/sessions/{sid}", headers=_bearer(_token_bob()))
    assert r2.status_code == 404


async def test_get_session_cross_tenant_returns_404(client: AsyncClient) -> None:
    """跨租户访问 → 404（验收强制要求）。"""
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "A"}
    )
    sid = r.json()["id"]
    r2 = await client.get(f"/sessions/{sid}", headers=_bearer(_token_carol()))
    assert r2.status_code == 404


# ---- patch ----


async def test_patch_rename_session(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "Old"}
    )
    sid = r.json()["id"]
    r2 = await client.patch(
        f"/sessions/{sid}", headers=_bearer(_token_alice()), json={"title": "New"}
    )
    assert r2.status_code == 200
    assert r2.json()["title"] == "New"


async def test_patch_session_cross_user_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "Old"}
    )
    sid = r.json()["id"]
    r2 = await client.patch(
        f"/sessions/{sid}",
        headers=_bearer(_token_bob()),
        json={"title": "Hacked"},
    )
    assert r2.status_code == 404


async def test_patch_session_cross_tenant_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "Old"}
    )
    sid = r.json()["id"]
    r2 = await client.patch(
        f"/sessions/{sid}",
        headers=_bearer(_token_carol()),
        json={"title": "Hacked"},
    )
    assert r2.status_code == 404


# ---- delete ----


async def test_delete_session_owner(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "Bye"}
    )
    sid = r.json()["id"]
    r2 = await client.delete(f"/sessions/{sid}", headers=_bearer(_token_alice()))
    assert r2.status_code == 204
    # 二次访问应 404
    r3 = await client.get(f"/sessions/{sid}", headers=_bearer(_token_alice()))
    assert r3.status_code == 404


async def test_delete_session_cross_user_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "Old"}
    )
    sid = r.json()["id"]
    r2 = await client.delete(f"/sessions/{sid}", headers=_bearer(_token_bob()))
    assert r2.status_code == 404


async def test_delete_session_cross_tenant_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "Old"}
    )
    sid = r.json()["id"]
    r2 = await client.delete(f"/sessions/{sid}", headers=_bearer(_token_carol()))
    assert r2.status_code == 404


# ---- messages ----


async def test_list_messages_owner_returns_in_created_order(
    client: AsyncClient, store: _SessionStore
) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "M"}
    )
    sid = uuid.UUID(r.json()["id"])
    store.seed_message(
        session_id=sid,
        tenant_id=_TENANT_X,
        user_id=_USER_A,
        role="user",
        content="hi",
        offset_ms=0,
    )
    store.seed_message(
        session_id=sid,
        tenant_id=_TENANT_X,
        user_id=_USER_A,
        role="assistant",
        content="hello",
        offset_ms=10,
    )
    r2 = await client.get(
        f"/sessions/{sid}/messages", headers=_bearer(_token_alice())
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["total"] == 2
    assert [m["role"] for m in body["items"]] == ["user", "assistant"]
    assert [m["content"] for m in body["items"]] == ["hi", "hello"]


async def test_list_messages_cross_user_returns_404(
    client: AsyncClient, store: _SessionStore
) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "M"}
    )
    sid = uuid.UUID(r.json()["id"])
    store.seed_message(
        session_id=sid,
        tenant_id=_TENANT_X,
        user_id=_USER_A,
        role="user",
        content="hi",
    )
    r2 = await client.get(
        f"/sessions/{sid}/messages", headers=_bearer(_token_bob())
    )
    assert r2.status_code == 404


async def test_list_messages_cross_tenant_returns_404(
    client: AsyncClient, store: _SessionStore
) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "M"}
    )
    sid = uuid.UUID(r.json()["id"])
    store.seed_message(
        session_id=sid,
        tenant_id=_TENANT_X,
        user_id=_USER_A,
        role="user",
        content="hi",
    )
    r2 = await client.get(
        f"/sessions/{sid}/messages", headers=_bearer(_token_carol())
    )
    assert r2.status_code == 404


async def test_list_messages_unknown_session_returns_404(client: AsyncClient) -> None:
    fake = uuid.uuid4()
    r = await client.get(
        f"/sessions/{fake}/messages", headers=_bearer(_token_alice())
    )
    assert r.status_code == 404


async def test_list_messages_pagination(
    client: AsyncClient, store: _SessionStore
) -> None:
    r = await client.post(
        "/sessions", headers=_bearer(_token_alice()), json={"title": "M"}
    )
    sid = uuid.UUID(r.json()["id"])
    for i in range(10):
        store.seed_message(
            session_id=sid,
            tenant_id=_TENANT_X,
            user_id=_USER_A,
            role="user",
            content=f"msg {i}",
            offset_ms=i,
        )
    r2 = await client.get(
        f"/sessions/{sid}/messages?limit=3&offset=2",
        headers=_bearer(_token_alice()),
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["total"] == 10
    assert body["limit"] == 3
    assert body["offset"] == 2
    assert [m["content"] for m in body["items"]] == ["msg 2", "msg 3", "msg 4"]
