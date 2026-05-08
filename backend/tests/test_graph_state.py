"""STE-23：AgentState TypedDict + reducer 行为单测。

目标：验证 plan §3.7.1 (5) 的 reducer 选择不被静默改坏：
- messages 用 add_messages（消息累加）
- retries 用 Annotated[int, add]（计数器累加）
- 业务字段（rows / chart_spec / error）默认覆盖
"""

from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from app.graph.state import AgentState


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


def _identity_node(_state: AgentState) -> dict:
    return {}


# ---- TypedDict 字段 ----


def test_agent_state_has_required_fields() -> None:
    """关键字段必须出现在 __annotations__ 中（IDE 补全 + reducer 推断）。"""
    fields = set(AgentState.__annotations__.keys())
    assert {
        "messages",
        "tenant_id",
        "user_query",
        "retrieved_schema",
        "candidate_sql",
        "validated_sql",
        "rows",
        "chart_spec",
        "retries",
        "error",
    } <= fields


# ---- reducer 行为：通过最小图验证 ----


def _build_minimal_graph_with_node(node_fn) -> object:
    builder = StateGraph(AgentState)
    builder.add_node("step", node_fn)
    builder.add_edge(START, "step")
    builder.add_edge("step", END)
    return builder.compile()


@pytest.mark.asyncio
async def test_messages_reducer_appends(tenant_id: uuid.UUID) -> None:
    """messages 字段用 add_messages reducer，节点 return 的 list 应被追加而非覆盖。"""

    async def push_ai(_state: AgentState) -> dict:
        return {"messages": [AIMessage(content="hi")]}

    graph = _build_minimal_graph_with_node(push_ai)
    out = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="ping")],
            "tenant_id": tenant_id,
            "user_query": "ping",
        }
    )
    assert len(out["messages"]) == 2
    assert isinstance(out["messages"][0], HumanMessage)
    assert isinstance(out["messages"][1], AIMessage)


@pytest.mark.asyncio
async def test_retries_reducer_adds(tenant_id: uuid.UUID) -> None:
    """retries 字段用 add reducer，节点 return {'retries': 1} 应累加。"""

    async def bump(_state: AgentState) -> dict:
        return {"retries": 1}

    graph = _build_minimal_graph_with_node(bump)
    out = await graph.ainvoke(
        {
            "messages": [],
            "tenant_id": tenant_id,
            "user_query": "x",
            "retries": 2,
        }
    )
    assert out["retries"] == 3


@pytest.mark.asyncio
async def test_error_field_overwrites(tenant_id: uuid.UUID) -> None:
    """error 是默认 reducer（覆盖），节点回写应替换原值。"""

    async def set_err(_state: AgentState) -> dict:
        return {"error": "boom"}

    graph = _build_minimal_graph_with_node(set_err)
    out = await graph.ainvoke(
        {
            "messages": [],
            "tenant_id": tenant_id,
            "user_query": "x",
            "error": "old",
        }
    )
    assert out["error"] == "boom"


@pytest.mark.asyncio
async def test_rows_field_overwrites(tenant_id: uuid.UUID) -> None:
    """rows 默认覆盖；节点 return 的 list 替换原值，而非追加。"""

    async def set_rows(_state: AgentState) -> dict:
        return {"rows": [{"a": 1}]}

    graph = _build_minimal_graph_with_node(set_rows)
    out = await graph.ainvoke(
        {
            "messages": [],
            "tenant_id": tenant_id,
            "user_query": "x",
            "rows": [{"a": 0}, {"a": 0}],
        }
    )
    assert out["rows"] == [{"a": 1}]
