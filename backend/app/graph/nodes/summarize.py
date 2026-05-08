"""STE-23：summarize 节点（占位）。

渲染 STE-20 `summarize.j2` prompt，让 LLM 给出 ≤ 3 句业务总结。
失败兜底（state.error 存在 + retries 达上限）→ 把错误信息以友好语言告知用户。

输入：state.user_query / state.rows / state.error
输出：state.messages 追加一条 AIMessage（由 add_messages reducer 拼到历史）
     **不要** 同时回写其它业务字段，避免前端重复展示。

config.configurable：
- chat_llm（同 sql_gen / chart）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from app.graph.state import AgentState


async def summarize(
    state: "AgentState", config: "RunnableConfig"
) -> dict[str, Any]:
    raise NotImplementedError
