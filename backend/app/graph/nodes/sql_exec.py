"""STE-23：sql_exec 节点（占位）。

用 biz_engine 只读连接执行 validated_sql；用 SQLAlchemy `bindparam(:tid)`
绑定 tenant_id（与 STE-22 注入的占位符 `:tid` 对齐）。

输入：state.validated_sql / state.tenant_id
输出：state.rows（list[dict]，列名 → 值）；列序由结果集决定

config.configurable：
- biz_engine: SQLAlchemy AsyncEngine
- sql_exec_timeout_ms: 单次 SQL 的 statement_timeout（毫秒）

错误处理：DB 异常（语法/超时/网络）抛回，由 LangGraph 异常机制传播；
本节点不捕获异常以保留 stack。生产可在 builder 上下文用 retry policy 包装。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from app.graph.state import AgentState


async def sql_exec(
    state: "AgentState", config: "RunnableConfig"
) -> dict[str, Any]:
    raise NotImplementedError
