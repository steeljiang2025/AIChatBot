"""STE-23：sql_validate 节点（占位）。

调用 STE-22 `sanitize_sql` 走完整安全流水线（含 tenant_guard）。

输入：state.candidate_sql / state.tenant_id
输出：
- 成功：state.validated_sql（含 :tid 占位符），state.error = None
- 失败：state.error = 类名 + 消息；state.retries += 1（reducer add 累加）

config.configurable：
- known_tables / known_columns / tenant_scoped_tables: SQL 白名单
- max_rows: enforce_limit 的上限
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from app.graph.state import AgentState


async def sql_validate(
    state: "AgentState", config: "RunnableConfig"
) -> dict[str, Any]:
    raise NotImplementedError
