"""STE-23：retrieve 节点（占位）。

调用 STE-21 `semantic_service.hybrid_search`，把 user_query 转成结构化的
`retrieved_schema`（候选表/列/术语/关联的 hits 列表）。

输入：state.tenant_id / state.user_query
输出：state.retrieved_schema（list[dict]，每条含 type/id/title/snippet/score）

config.configurable 必带：
- meta_session_factory: 工厂，调用即得 `async with` 的 AsyncSession 上下文
- top_k（可选，默认 10）/ alpha（可选，默认 0.3）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from app.graph.state import AgentState


async def retrieve(
    state: "AgentState", config: "RunnableConfig"
) -> dict[str, Any]:
    raise NotImplementedError
