"""STE-23：6 个节点的纯单测（mock service / LLM / engine）。

每个节点用 monkeypatch 把外部依赖替换成可控 stub：
- retrieve：mock semantic_service.hybrid_search
- sql_gen：mock chat_llm.ainvoke + render_prompt
- sql_validate：mock sql_safety_service.sanitize_sql
- sql_exec：mock biz_engine.connect → 一个 fake connection
- chart：mock chat_llm.ainvoke
- summarize：mock chat_llm.ainvoke
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.nodes import (
    chart,
    retrieve,
    sql_exec,
    sql_gen,
    sql_validate,
    summarize,
)


# ---- 公共 fixture ----


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture()
def base_state(tenant_id: uuid.UUID) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content="上个月各产品销售额")],
        "tenant_id": tenant_id,
        "user_query": "上个月各产品销售额",
    }


def _config(**configurable: Any) -> dict[str, Any]:
    return {"configurable": configurable}


# ============ retrieve ============


@pytest.mark.asyncio
async def test_retrieve_calls_hybrid_search(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    captured: dict[str, Any] = {}

    async def fake_hybrid_search(session, *, tenant_id, query, top_k, alpha, types=None):
        captured.update(
            {"tenant_id": tenant_id, "query": query, "top_k": top_k, "alpha": alpha}
        )
        # mock：返回最小 hit
        return [_FakeHit("orders", "table", "订单流水")]

    monkeypatch.setattr(
        "app.services.semantic_service.hybrid_search", fake_hybrid_search
    )

    factory = _AsyncSessionFactoryStub()
    cfg = _config(meta_session_factory=factory, top_k=5, alpha=0.4)
    out = await retrieve(base_state, cfg)

    assert isinstance(out["retrieved_schema"], list)
    assert len(out["retrieved_schema"]) == 1
    assert captured["tenant_id"] == base_state["tenant_id"]
    assert captured["query"] == base_state["user_query"]
    assert captured["top_k"] == 5
    assert captured["alpha"] == 0.4


@pytest.mark.asyncio
async def test_retrieve_uses_default_top_k_alpha(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    captured: dict[str, Any] = {}

    async def fake_hybrid_search(session, *, tenant_id, query, top_k, alpha, types=None):
        captured.update({"top_k": top_k, "alpha": alpha})
        return []

    monkeypatch.setattr(
        "app.services.semantic_service.hybrid_search", fake_hybrid_search
    )

    factory = _AsyncSessionFactoryStub()
    cfg = _config(meta_session_factory=factory)
    await retrieve(base_state, cfg)
    # 默认 top_k=10, alpha=0.3（与 STE-21 retriever 默认值对齐）
    assert captured["top_k"] == 10
    assert captured["alpha"] == 0.3


# ============ sql_gen ============


@pytest.mark.asyncio
async def test_sql_gen_invokes_llm_with_rendered_prompt(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    rendered_text: dict[str, Any] = {}

    def fake_render(name: str, **ctx: Any) -> str:
        rendered_text["name"] = name
        rendered_text["ctx"] = ctx
        return f"PROMPT[{name}]"

    monkeypatch.setattr("app.llm.prompts.render_prompt", fake_render)

    fake_llm = AsyncMock()
    fake_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="SELECT id FROM orders LIMIT 10")
    )

    state = {
        **base_state,
        "retrieved_schema": [{"type": "table", "title": "orders"}],
    }
    out = await sql_gen(state, _config(chat_llm=fake_llm, max_rows=200))

    assert rendered_text["name"] == "sql_gen"
    assert rendered_text["ctx"]["user_query"] == base_state["user_query"]
    assert rendered_text["ctx"]["max_rows"] == 200
    assert "semantic_cards" in rendered_text["ctx"]
    fake_llm.ainvoke.assert_awaited_once()
    assert out["candidate_sql"].startswith("SELECT")
    assert out["error"] is None


@pytest.mark.asyncio
async def test_sql_gen_strips_markdown_fences(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    """LLM 经常返回 ```sql ... ``` 包裹，节点应剥掉。"""
    monkeypatch.setattr("app.llm.prompts.render_prompt", lambda *a, **k: "P")
    fake_llm = AsyncMock()
    fake_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="```sql\nSELECT 1\n```")
    )
    state = {**base_state, "retrieved_schema": []}
    out = await sql_gen(state, _config(chat_llm=fake_llm, max_rows=100))
    assert out["candidate_sql"].strip() == "SELECT 1"


@pytest.mark.asyncio
async def test_sql_gen_passes_prior_error_for_retry(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    """重试场景：state.error 应作为 prior_error 传给 prompt。"""
    captured: dict[str, Any] = {}

    def fake_render(name: str, **ctx: Any) -> str:
        captured.update(ctx)
        return "P"

    monkeypatch.setattr("app.llm.prompts.render_prompt", fake_render)
    fake_llm = AsyncMock()
    fake_llm.ainvoke = AsyncMock(return_value=AIMessage(content="SELECT 2"))
    state = {
        **base_state,
        "retrieved_schema": [],
        "error": "UnregisteredTableError: foo",
    }
    await sql_gen(state, _config(chat_llm=fake_llm, max_rows=100))
    assert captured.get("prior_error") == "UnregisteredTableError: foo"


# ============ sql_validate ============


@pytest.mark.asyncio
async def test_sql_validate_success(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    def fake_sanitize(sql, **kw):
        return sql.replace("FROM orders", "FROM orders WHERE tenant_id = :tid") + " LIMIT 100"

    monkeypatch.setattr(
        "app.services.sql_safety_service.sanitize_sql", fake_sanitize
    )
    state = {**base_state, "candidate_sql": "SELECT id FROM orders"}
    cfg = _config(
        known_tables={("public", "orders")},
        known_columns={("public", "orders"): {"id", "tenant_id"}},
        tenant_scoped_tables={("public", "orders")},
        max_rows=100,
    )
    out = await sql_validate(state, cfg)
    assert ":tid" in out["validated_sql"]
    assert "LIMIT 100" in out["validated_sql"]
    assert out["error"] is None


@pytest.mark.asyncio
async def test_sql_validate_failure_returns_error_and_retry(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    from app.sql_safety import UnregisteredTableError

    def fake_sanitize(sql, **kw):
        raise UnregisteredTableError("Table not registered: public.evil")

    monkeypatch.setattr(
        "app.services.sql_safety_service.sanitize_sql", fake_sanitize
    )
    state = {**base_state, "candidate_sql": "SELECT * FROM evil"}
    out = await sql_validate(state, _config(
        known_tables=set(), known_columns={}, tenant_scoped_tables=set(),
        max_rows=100,
    ))
    assert "UnregisteredTableError" in out["error"]
    assert out["retries"] == 1


# ============ sql_exec ============


@pytest.mark.asyncio
async def test_sql_exec_calls_engine_with_tid_param(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    captured: dict[str, Any] = {}

    fake_engine = _FakeEngine(
        result_rows=[{"product": "A", "amount": 100}],
        captured=captured,
    )
    state = {
        **base_state,
        "validated_sql": "SELECT product, amount FROM orders WHERE tenant_id = :tid LIMIT 100",
    }
    out = await sql_exec(state, _config(biz_engine=fake_engine, sql_exec_timeout_ms=15000))
    assert out["rows"] == [{"product": "A", "amount": 100}]
    assert captured["params"] == {"tid": str(base_state["tenant_id"])}
    assert captured["timeout_ms"] == 15000


# ============ chart ============


@pytest.mark.asyncio
async def test_chart_skips_when_rows_empty(base_state: dict) -> None:
    state = {**base_state, "rows": []}
    out = await chart(state, _config())
    assert out["chart_spec"] is None


@pytest.mark.asyncio
async def test_chart_calls_llm_and_parses_json(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    monkeypatch.setattr(
        "app.llm.prompts.render_prompt", lambda *a, **k: "PROMPT"
    )
    fake_llm = AsyncMock()
    spec = {"chart_type": "bar", "option": {"xAxis": {}, "series": []}}
    fake_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content=json.dumps(spec))
    )
    state = {**base_state, "rows": [{"product": "A", "amount": 1}]}
    out = await chart(state, _config(chat_llm=fake_llm))
    assert out["chart_spec"] == spec


@pytest.mark.asyncio
async def test_chart_handles_markdown_json_fence(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    monkeypatch.setattr(
        "app.llm.prompts.render_prompt", lambda *a, **k: "PROMPT"
    )
    fake_llm = AsyncMock()
    spec = {"chart_type": "line"}
    fake_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content=f"```json\n{json.dumps(spec)}\n```")
    )
    state = {**base_state, "rows": [{"x": 1}]}
    out = await chart(state, _config(chat_llm=fake_llm))
    assert out["chart_spec"] == spec


# ============ summarize ============


@pytest.mark.asyncio
async def test_summarize_appends_ai_message(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    monkeypatch.setattr("app.llm.prompts.render_prompt", lambda *a, **k: "P")
    fake_llm = AsyncMock()
    fake_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="上月销售额：A=100、B=80、C=60。")
    )
    state = {**base_state, "rows": [{"product": "A", "amount": 100}]}
    out = await summarize(state, _config(chat_llm=fake_llm))
    assert "messages" in out
    assert len(out["messages"]) == 1
    assert isinstance(out["messages"][0], AIMessage)


@pytest.mark.asyncio
async def test_summarize_handles_error_state(
    monkeypatch: pytest.MonkeyPatch, base_state: dict
) -> None:
    """state.error 已设 + 重试上限 → 友好告知用户失败，不调 LLM 也不强制要求。"""
    monkeypatch.setattr("app.llm.prompts.render_prompt", lambda *a, **k: "P")
    fake_llm = AsyncMock()
    fake_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="抱歉，无法回答你的问题。")
    )
    state = {
        **base_state,
        "rows": [],
        "error": "UnregisteredTableError",
    }
    out = await summarize(state, _config(chat_llm=fake_llm))
    assert "messages" in out
    assert len(out["messages"]) == 1


# ============ Stubs ============


class _FakeHit:
    """模拟 STE-21 的 Hit（dataclass 风格）。"""

    def __init__(self, title: str, type_: str, snippet: str) -> None:
        self.type = type_
        self.id = uuid.uuid4()
        self.title = title
        self.snippet = snippet
        self.score = 0.8


class _AsyncSessionFactoryStub:
    """`async with factory() as session:` 的最小实现。"""

    def __call__(self) -> "_AsyncSessionFactoryStub":
        return self

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: Any) -> None:
        return None


class _FakeEngine:
    """模拟 SQLAlchemy AsyncEngine.connect()。"""

    def __init__(self, result_rows: list[dict], captured: dict) -> None:
        self._rows = result_rows
        self._captured = captured

    def connect(self) -> "_FakeConn":
        return _FakeConn(self._rows, self._captured)


class _FakeConn:
    def __init__(self, rows: list[dict], captured: dict) -> None:
        self._rows = rows
        self._captured = captured

    async def __aenter__(self) -> "_FakeConn":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(self, stmt: Any, params: dict | None = None):
        # 第一次调用是 SET LOCAL statement_timeout
        if hasattr(stmt, "text") and "statement_timeout" in str(stmt.text).lower():
            # 解析参数中的毫秒数
            import re

            m = re.search(r"statement_timeout\s*=\s*(\d+)", str(stmt.text))
            if m:
                self._captured["timeout_ms"] = int(m.group(1))
            return _FakeResult([])
        # 第二次调用是真业务 SQL
        self._captured["params"] = params
        self._captured["sql"] = str(stmt)
        return _FakeResult(self._rows)


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(_FakeRow(r) for r in self._rows)


class _FakeRow:
    """模拟 SQLAlchemy Row：r._mapping → dict。"""

    def __init__(self, d: dict) -> None:
        self._mapping = d
