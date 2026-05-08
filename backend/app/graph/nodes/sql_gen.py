"""STE-23：sql_gen 节点（占位）。

渲染 STE-20 `sql_gen.j2` prompt，调 ChatOpenAI 生成 SQL。

输入：state.user_query / state.retrieved_schema / state.error（可选，重试时回写）
输出：state.candidate_sql；`error` 重置为 None

config.configurable：
- chat_llm（测试可注入 mock）；生产 None → 节点取 `get_chat_llm()` 单例
- max_rows: prompt 里告诉 LLM 的 LIMIT 上限（与 STE-22 enforce_limit 一致）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from app.graph.state import AgentState


async def sql_gen(
    state: "AgentState", config: "RunnableConfig"
) -> dict[str, Any]:
    raise NotImplementedError
