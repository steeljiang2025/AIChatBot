"""STE-24：/chat/stream 端到端 SSE 单测。

策略：
- 复用既有 test_sessions_api.py 的 in-memory 鉴权 / 会话仓储 mock 模式
- mock graph.astream 返回固定 chunk 序列
- 用 httpx.AsyncClient 发请求 + 解析返回的 SSE 流
- 断言：事件序列 + 用户/助手消息均落库 + extra 字段含 sql/rows/chart
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.messages import AIMessage, AIMessageChunk

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.models import ChatSession, Message
from app.db.models.iam import Tenant, User


# ============ in-memory store ============


@pytest.fixture()
def store() -> dict[str, Any]:
    """把 sessions / messages / users / tenants 全部放内存。"""
    tenant = Tenant(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="t1",
        code="t1",
        is_active=True,
    )
    user = User(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        tenant_id=tenant.id,
        email="u@example.com",
        password_hash="x",
        is_active=True,
        roles=[],
    )
    sess = ChatSession(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        tenant_id=tenant.id,
        user_id=user.id,
        title="t",
    )
    sess.created_at = datetime.now(UTC)
    sess.updated_at = sess.created_at
    return {
        "tenants": {tenant.id: tenant},
        "users": {user.id: user},
        "sessions": {sess.id: sess},
        "messages": [],
    }


@pytest.fixture()
def auth_token(store: dict) -> str:
    user = next(iter(store["users"].values()))
    return create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=[],
    )


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch, store: dict) -> FastAPI:
    """构造 FastAPI app + 把所有 repo / graph 替换为内存桩。"""
    # ---- mock user_repo ----
    async def fake_get_user_by_id(_session, user_id):
        return store["users"].get(user_id)

    monkeypatch.setattr("app.services.user_repo.get_user_by_id", fake_get_user_by_id)

    # ---- mock session_repo ----
    async def fake_get_session_scoped(_session, *, session_id, tenant_id, user_id):
        sess = store["sessions"].get(session_id)
        if (
            sess is None
            or sess.tenant_id != tenant_id
            or sess.user_id != user_id
        ):
            return None
        return sess

    async def fake_add_message(_session, *, session_id, tenant_id, user_id, role, content, extra=None, token_usage=None):
        m = Message(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            content=content,
            extra=extra,
            token_usage=token_usage,
        )
        m.id = uuid.uuid4()
        m.created_at = datetime.now(UTC)
        store["messages"].append(m)
        return m

    monkeypatch.setattr(
        "app.services.session_repo.get_session_scoped", fake_get_session_scoped
    )
    monkeypatch.setattr(
        "app.services.session_repo.add_message", fake_add_message
    )

    # ---- mock schema_provider ----
    from app.services.schema_provider import SchemaWhitelist

    async def fake_load_schema(_session, *, tenant_id):
        return SchemaWhitelist(
            known_tables={("public", "orders")},
            known_columns={("public", "orders"): {"product", "amount", "tenant_id"}},
            tenant_scoped_tables={("public", "orders")},
        )

    monkeypatch.setattr(
        "app.services.schema_provider.load_schema_whitelist", fake_load_schema
    )

    # ---- DB 层不真连：让 MetaSession 工厂返回一个 noop session ----
    class _NoopSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def commit(self):
            pass

        async def execute(self, *a, **kw):
            class _R:
                def scalar_one(self):
                    return 1

            return _R()

    async def _get_meta_session():
        s = _NoopSession()
        try:
            yield s
        finally:
            pass

    from app.db import base as db_base

    monkeypatch.setattr(db_base, "ping_engine", lambda *a, **kw: _async_true())
    monkeypatch.setattr(db_base, "get_meta_session", _get_meta_session)

    # ---- 构造 app（不让 lifespan 真连 PG） ----
    from app.main import create_app

    app = create_app()
    # 直接挂 mock graph 与必要状态，不依赖 lifespan
    app.state.graph = _MockGraph()
    app.state.business_engine = object()
    app.state.meta_session_factory = _NoopSession
    return app


async def _async_true():
    return True


# ============ mock graph ============


class _MockGraph:
    """固定 chunk 序列：
    updates(retrieve) → updates(sql_gen) → updates(sql_validate)
      → updates(sql_exec) → updates(chart) → messages(summarize)
      → updates(summarize)
    """

    def __init__(self) -> None:
        self._chunks: list[Any] = [
            ("updates", {"retrieve": {"retrieved_schema": [{"type": "table", "title": "orders"}]}}),
            ("updates", {"sql_gen": {"candidate_sql": "SELECT product, sum(amount) FROM orders GROUP BY product"}}),
            ("updates", {"sql_validate": {"validated_sql": "SELECT product, sum(amount) FROM orders WHERE tenant_id = :tid GROUP BY product LIMIT 100"}}),
            ("updates", {"sql_exec": {"rows": [{"product": "A", "amount": 100}, {"product": "B", "amount": 80}]}}),
            ("updates", {"chart": {"chart_spec": {"chart_type": "bar"}}}),
            ("messages", (AIMessageChunk(content="上月销售额：A=100、B=80。"), {"langgraph_node": "summarize", "langgraph_step": 6})),
            ("updates", {"summarize": {"messages": [AIMessage(content="上月销售额：A=100、B=80。")]}}),
        ]

    async def astream(self, _input, config=None, stream_mode=None):
        for ch in self._chunks:
            yield ch
            await asyncio.sleep(0)  # 让出事件循环

    async def aget_state(self, _config):
        # 模拟成功状态：error=None
        class _Snap:
            values = {"error": None}

        return _Snap()


class _FailGraph(_MockGraph):
    """模拟工作流失败：summarize 兜底 + final state.error 仍存在。"""

    def __init__(self) -> None:
        super().__init__()
        self._chunks = [
            ("updates", {"retrieve": {"retrieved_schema": []}}),
            ("updates", {"sql_gen": {"candidate_sql": "SELECT * FROM evil"}}),
            ("updates", {"sql_validate": {"error": "UnregisteredTableError: evil"}}),
            ("updates", {"sql_gen": {"candidate_sql": "SELECT * FROM evil2"}}),
            ("updates", {"sql_validate": {"error": "UnregisteredTableError: evil2"}}),
            ("messages", (AIMessageChunk(content="抱歉，无法回答。"), {"langgraph_node": "summarize", "langgraph_step": 8})),
            ("updates", {"summarize": {"messages": [AIMessage(content="抱歉，无法回答。")]}}),
        ]

    async def aget_state(self, _config):
        class _Snap:
            values = {"error": "UnregisteredTableError: evil2"}

        return _Snap()


# ============ helper：解析 SSE 流 ============


def _parse_sse_stream(payload: bytes) -> list[dict[str, Any]]:
    """把 SSE 字节流解析为 [{event, data}, ...]。"""
    import json

    events: list[dict[str, Any]] = []
    for frame in payload.split(b"\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        lines = frame.decode("utf-8").split("\n")
        ev: dict[str, Any] = {}
        for line in lines:
            if line.startswith("event: "):
                ev["event"] = line[len("event: "):]
            elif line.startswith("data: "):
                raw = line[len("data: "):]
                try:
                    ev["data"] = json.loads(raw)
                except (ValueError, json.JSONDecodeError):
                    ev["data"] = raw
        if ev:
            events.append(ev)
    return events


# ============ 端到端用例 ============


@pytest.mark.asyncio
async def test_chat_stream_happy_path(app: FastAPI, auth_token: str, store: dict) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        sess_id = next(iter(store["sessions"]))
        resp = await client.post(
            "/chat/stream",
            json={"session_id": str(sess_id), "content": "上个月各产品销售额"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse_stream(resp.content)

    event_names = [e["event"] for e in events]
    # 必须包含的事件类型
    assert "node" in event_names
    assert "sql" in event_names
    assert "rows" in event_names
    assert "chart" in event_names
    assert "token" in event_names
    assert event_names[-1] == "done"
    assert "error" not in event_names

    # done 携带 message_id
    done = events[-1]
    assert "message_id" in done["data"]

    # 落库：1 条 user + 1 条 assistant
    roles = [m.role for m in store["messages"]]
    assert roles == ["user", "assistant"]
    user_msg = store["messages"][0]
    asst_msg = store["messages"][1]
    assert user_msg.content == "上个月各产品销售额"
    assert "上月销售额" in asst_msg.content
    # extra 含 sql / rows_preview / chart
    assert asst_msg.extra is not None
    assert ":tid" in asst_msg.extra["sql"]
    assert len(asst_msg.extra["rows_preview"]) == 2
    assert asst_msg.extra["chart"] == {"chart_type": "bar"}
    assert asst_msg.extra.get("error") is None


@pytest.mark.asyncio
async def test_chat_stream_emits_error_when_final_state_error(
    app: FastAPI, auth_token: str, store: dict
) -> None:
    """重试用尽 + summarize 兜底 → SSE 中应含 error 事件。"""
    app.state.graph = _FailGraph()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        sess_id = next(iter(store["sessions"]))
        resp = await client.post(
            "/chat/stream",
            json={"session_id": str(sess_id), "content": "x"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        events = _parse_sse_stream(resp.content)

    names = [e["event"] for e in events]
    assert "error" in names
    assert names[-1] == "done"
    # 助手消息仍落库 + extra.error 不空
    asst = store["messages"][-1]
    assert asst.role == "assistant"
    assert asst.extra["error"] == "UnregisteredTableError: evil2"


@pytest.mark.asyncio
async def test_chat_stream_404_when_session_not_owned(
    app: FastAPI, auth_token: str
) -> None:
    """陌生 session_id → 404。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/chat/stream",
            json={"session_id": str(uuid.uuid4()), "content": "x"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_stream_503_when_graph_not_available(
    app: FastAPI, auth_token: str, store: dict
) -> None:
    """lifespan 装配 graph 失败时 → 503。"""
    app.state.graph = None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        sess_id = next(iter(store["sessions"]))
        resp = await client.post(
            "/chat/stream",
            json={"session_id": str(sess_id), "content": "x"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_chat_stream_401_when_no_token(app: FastAPI, store: dict) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        sess_id = next(iter(store["sessions"]))
        resp = await client.post(
            "/chat/stream",
            json={"session_id": str(sess_id), "content": "x"},
        )
        assert resp.status_code == 401


# 让 settings cache 在每次测试间清理
@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    get_settings.cache_clear()
