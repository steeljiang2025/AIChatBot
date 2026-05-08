"""STE-23：chart 节点（占位）。

渲染 STE-20 `chart_recommend.j2` prompt，让 LLM 推荐 ECharts 图表配置。
若 rows 为空 → chart_spec=None，跳过 LLM 调用。

输入：state.rows / state.user_query
输出：state.chart_spec（dict | None）

config.configurable：
- chat_llm（同 sql_gen）

prompt 实验规则：
- 单维度数值 → bar
- 时间序列 → line
- 占比 → pie
- 散点关系 → scatter
- 太多维度 → table
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from app.graph.state import AgentState


async def chart(
    state: "AgentState", config: "RunnableConfig"
) -> dict[str, Any]:
    raise NotImplementedError
