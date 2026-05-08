"""STE-23：StateGraph 装配。

工作流拓扑：

    START → retrieve → sql_gen → sql_validate
                                       │
                                       ├─ ok ─────► sql_exec → chart → summarize → END
                                       │
                                       ├─ retry < N ─► sql_gen
                                       │
                                       └─ retry >= N ─► summarize（兜底报错） → END

校验失败时：
- sql_validate 节点把 `error` 写回 state，并 `retries += 1`
- _route_after_validate 根据 retries < max_retries 决定走重试或失败分支
- 失败分支统一进 summarize（state.error 触发 summarize.j2 的错误兜底分支）

调用方传入 RunnableConfig.configurable：
- meta_session_factory / biz_engine
- known_tables / known_columns / tenant_scoped_tables
- max_rows / max_retries / sql_exec_timeout_ms
- chat_llm（测试时注入 mock；生产为 None → 节点取 lru_cache 单例）
- thread_id（langgraph 检查点 key，调用方必传）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    chart,
    retrieve,
    sql_exec,
    sql_gen,
    sql_validate,
    summarize,
)
from app.graph.state import AgentState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph


_DEFAULT_MAX_RETRIES: Final[int] = 2


def _route_after_validate(
    state: AgentState, config: RunnableConfig
) -> str:
    """sql_validate 之后的条件路由：

    - 无 error → sql_exec
    - 有 error 且 retries < max_retries → sql_gen（重试）
    - 有 error 且 retries 达上限 → summarize（兜底报错）
    """
    if not state.get("error"):
        return "sql_exec"

    cfg = (config or {}).get("configurable", {}) or {}
    max_retries = int(cfg.get("max_retries", _DEFAULT_MAX_RETRIES))

    if state.get("retries", 0) < max_retries:
        return "sql_gen"
    return "summarize"


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """组装并编译 StateGraph。

    Args:
        checkpointer: AsyncPostgresSaver / InMemorySaver；None 表示无持久化。

    Returns: CompiledStateGraph，可 .ainvoke / .astream。
    """
    builder: StateGraph = StateGraph(AgentState)

    builder.add_node("retrieve", retrieve)
    builder.add_node("sql_gen", sql_gen)
    builder.add_node("sql_validate", sql_validate)
    builder.add_node("sql_exec", sql_exec)
    builder.add_node("chart", chart)
    builder.add_node("summarize", summarize)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "sql_gen")
    builder.add_edge("sql_gen", "sql_validate")
    builder.add_conditional_edges(
        "sql_validate",
        _route_after_validate,
        # plan §3.7.1 (6) 必坑：第三个参数（路径表）必传
        {"sql_exec": "sql_exec", "sql_gen": "sql_gen", "summarize": "summarize"},
    )
    builder.add_edge("sql_exec", "chart")
    builder.add_edge("chart", "summarize")
    builder.add_edge("summarize", END)

    return builder.compile(checkpointer=checkpointer)


__all__ = ["build_graph"]
