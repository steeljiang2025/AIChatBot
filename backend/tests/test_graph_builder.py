"""STE-23：StateGraph 装配端到端单测（用 InMemorySaver）。

策略：
- 不连真 PG；用 langgraph 内置 InMemorySaver
- monkeypatch 6 个节点的外部依赖（service / LLM / engine）
- 端到端跑一次「上个月各产品销售额」全流程，验证：
  1. 节点执行顺序
  2. 校验失败重试 → 达上限走失败分支
  3. checkpoint 复用（同 thread_id 二次调用）
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.graph.builder import build_graph


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture()
def thread_id() -> str:
    return "thread-aaaa-bbbb"


def _make_chat_llm(responses: list[str]) -> AsyncMock:
    """生成一个按调用顺序返回 responses 的 fake llm。"""
    llm = AsyncMock()
    iter_resp = iter(responses)

    async def _ainvoke(_prompt, **_kw):
        return AIMessage(content=next(iter_resp))

    llm.ainvoke = _ainvoke
    return llm


def _patch_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sanitize_returns: list[Any] | None = None,
    rows: list[dict] | None = None,
) -> None:
    """统一 mock：semantic_service / sql_safety / prompts。"""

    async def _hybrid_search(*a: Any, **kw: Any):
        return [_FakeHit("orders", "table", "订单流水")]

    monkeypatch.setattr(
        "app.services.semantic_service.hybrid_search", _hybrid_search
    )

    if sanitize_returns is None:
        sanitize_returns = [
            "SELECT product, sum(amount) FROM orders "
            "WHERE tenant_id = :tid GROUP BY product LIMIT 100"
        ]
    sanitize_iter = iter(sanitize_returns)

    def _sanitize(sql, **kw):
        nxt = next(sanitize_iter)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    monkeypatch.setattr(
        "app.services.sql_safety_service.sanitize_sql", _sanitize
    )

    monkeypatch.setattr(
        "app.llm.prompts.render_prompt", lambda *a, **k: "PROMPT"
    )


# ---- 端到端：成功路径 ----


@pytest.mark.asyncio
async def test_happy_path_runs_all_nodes(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: uuid.UUID,
    thread_id: str,
) -> None:
    rows = [
        {"product": "A", "amount": 100},
        {"product": "B", "amount": 80},
    ]
    _patch_dependencies(monkeypatch)

    chat_llm = _make_chat_llm(
        [
            "SELECT product, sum(amount) FROM orders GROUP BY product",  # sql_gen
            json.dumps({"chart_type": "bar", "option": {"xAxis": {}}}),  # chart
            "上月销售额：A=100、B=80。",  # summarize
        ]
    )
    biz_engine = _FakeEngine(rows)
    saver = InMemorySaver()
    graph = build_graph(saver)

    out = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="上个月各产品销售额")],
            "tenant_id": tenant_id,
            "user_query": "上个月各产品销售额",
        },
        config={
            "configurable": {
                "thread_id": thread_id,
                "chat_llm": chat_llm,
                "biz_engine": biz_engine,
                "meta_session_factory": _AsyncSessionFactoryStub(),
                "known_tables": {("public", "orders")},
                "known_columns": {("public", "orders"): {"product", "amount", "tenant_id"}},
                "tenant_scoped_tables": {("public", "orders")},
                "max_rows": 100,
                "max_retries": 2,
                "sql_exec_timeout_ms": 30000,
            }
        },
    )

    # 端到端：messages 至少含原 HumanMessage + summarize 产出的 AIMessage
    msgs = out["messages"]
    assert any(isinstance(m, HumanMessage) for m in msgs)
    assert any(isinstance(m, AIMessage) for m in msgs)
    # 业务字段
    assert out["validated_sql"]
    assert ":tid" in out["validated_sql"]
    assert out["rows"] == rows
    assert out["chart_spec"]["xAxis"]["data"] == ["A", "B"]
    assert out["chart_spec"]["series"][0]["type"] == "bar"
    assert out["chart_spec"]["grid"]["top"] == 120
    assert out["chart_spec"]["legend"]["top"] == 64
    assert out.get("error") is None


@pytest.mark.asyncio
async def test_validate_failure_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: uuid.UUID,
) -> None:
    """sql_validate 第一次失败 → 路由回 sql_gen → 第二次成功。"""
    from app.sql_safety import UnregisteredTableError

    rows = [{"a": 1}]
    _patch_dependencies(
        monkeypatch,
        sanitize_returns=[
            UnregisteredTableError("evil"),
            "SELECT a FROM orders WHERE tenant_id = :tid LIMIT 100",
        ],
    )
    chat_llm = _make_chat_llm(
        [
            "SELECT a FROM evil",          # 第一次 sql_gen（被拒）
            "SELECT a FROM orders",        # 重试的 sql_gen
            json.dumps({"chart_type": "table"}),  # chart
            "结果如上。",                     # summarize
        ]
    )
    biz_engine = _FakeEngine(rows)
    graph = build_graph(InMemorySaver())

    out = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="x")],
            "tenant_id": tenant_id,
            "user_query": "x",
        },
        config={
            "configurable": {
                "thread_id": "t-retry",
                "chat_llm": chat_llm,
                "biz_engine": biz_engine,
                "meta_session_factory": _AsyncSessionFactoryStub(),
                "known_tables": {("public", "orders")},
                "known_columns": {("public", "orders"): {"a", "tenant_id"}},
                "tenant_scoped_tables": {("public", "orders")},
                "max_rows": 100,
                "max_retries": 2,
                "sql_exec_timeout_ms": 30000,
            }
        },
    )
    assert out.get("rows") == rows
    assert out.get("retries", 0) >= 1
    assert out.get("error") is None  # sql_gen 重置；最终成功


@pytest.mark.asyncio
async def test_validate_failure_exhausts_retries(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: uuid.UUID,
) -> None:
    """sql_validate 持续失败到达 max_retries → 走失败分支由 summarize 报错。"""
    from app.sql_safety import UnregisteredTableError

    _patch_dependencies(
        monkeypatch,
        sanitize_returns=[
            UnregisteredTableError("e1"),
            UnregisteredTableError("e2"),
            UnregisteredTableError("e3"),
        ],
    )
    chat_llm = _make_chat_llm(
        [
            "SELECT * FROM evil1",
            "SELECT * FROM evil2",
            "SELECT * FROM evil3",
            "抱歉，无法生成有效 SQL。",  # summarize 错误兜底
        ]
    )
    biz_engine = _FakeEngine([])
    graph = build_graph(InMemorySaver())

    out = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="x")],
            "tenant_id": tenant_id,
            "user_query": "x",
        },
        config={
            "configurable": {
                "thread_id": "t-fail",
                "chat_llm": chat_llm,
                "biz_engine": biz_engine,
                "meta_session_factory": _AsyncSessionFactoryStub(),
                "known_tables": set(),
                "known_columns": {},
                "tenant_scoped_tables": set(),
                "max_rows": 100,
                "max_retries": 2,  # 最多 2 次重试
                "sql_exec_timeout_ms": 30000,
            }
        },
    )
    # summarize 收口时会清 error，避免误判 workflow_failed
    assert out.get("error") is None
    assert out.get("rows") in (None, [])
    # summarize 仍应产出 AIMessage 兜底
    assert any(isinstance(m, AIMessage) for m in out["messages"])


@pytest.mark.asyncio
async def test_checkpoint_persists_within_thread(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: uuid.UUID,
) -> None:
    """同 thread_id 二次调用 → checkpoint 应保留首轮的 messages。"""
    rows = [{"a": 1}]
    _patch_dependencies(monkeypatch, sanitize_returns=[
        "SELECT a FROM orders WHERE tenant_id = :tid LIMIT 100",
        "SELECT a FROM orders WHERE tenant_id = :tid LIMIT 100",
    ])
    chat_llm = _make_chat_llm(
        [
            "SELECT a FROM orders",                       # round 1 sql_gen
            json.dumps({"chart_type": "bar"}),            # round 1 chart
            "round1 result",                              # round 1 summarize
            "SELECT a FROM orders",                       # round 2 sql_gen
            json.dumps({"chart_type": "bar"}),            # round 2 chart
            "round2 result",                              # round 2 summarize
        ]
    )
    biz_engine = _FakeEngine(rows)
    saver = InMemorySaver()
    graph = build_graph(saver)
    cfg = {
        "configurable": {
            "thread_id": "t-shared",
            "chat_llm": chat_llm,
            "biz_engine": biz_engine,
            "meta_session_factory": _AsyncSessionFactoryStub(),
            "known_tables": {("public", "orders")},
            "known_columns": {("public", "orders"): {"a", "tenant_id"}},
            "tenant_scoped_tables": {("public", "orders")},
            "max_rows": 100,
            "max_retries": 2,
            "sql_exec_timeout_ms": 30000,
        }
    }

    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="第一次")],
            "tenant_id": tenant_id,
            "user_query": "第一次",
        },
        config=cfg,
    )
    out2 = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="第二次")],
            "tenant_id": tenant_id,
            "user_query": "第二次",
        },
        config=cfg,
    )
    # 第二次的 messages 应至少 ≥ 4（两轮 Human + 两轮 AI）
    assert len(out2["messages"]) >= 4


# ---- Stubs（与 test_graph_nodes 的 stub 同形态，复制以保持文件独立） ----


class _FakeHit:
    def __init__(self, title: str, type_: str, snippet: str) -> None:
        self.type = type_
        self.id = uuid.uuid4()
        self.title = title
        self.snippet = snippet
        self.score = 0.8


class _AsyncSessionFactoryStub:
    def __call__(self) -> _AsyncSessionFactoryStub:
        return self

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: Any) -> None:
        return None


class _FakeEngine:
    def __init__(self, result_rows: list[dict]) -> None:
        self._rows = result_rows

    def connect(self) -> _FakeConn:
        return _FakeConn(self._rows)


class _FakeConn:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(self, stmt: Any, params: dict | None = None):
        if hasattr(stmt, "text") and "statement_timeout" in str(stmt.text).lower():
            return _FakeResult([])
        return _FakeResult(self._rows)


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(_FakeRow(r) for r in self._rows)


class _FakeRow:
    def __init__(self, d: dict) -> None:
        self._mapping = d
