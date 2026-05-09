"""STE-23：retrieve 节点。

调用 STE-21 `semantic_service.hybrid_search`，把 user_query 转成结构化的
`retrieved_schema`（候选表/列/术语/关联的 hits 列表）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from app.graph.state import AgentState


_DEFAULT_TOP_K = 10
_DEFAULT_ALPHA = 0.3


async def retrieve(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    from app.services import semantic_service

    cfg: dict[str, Any] = config.get("configurable", {}) or {}
    factory = cfg["meta_session_factory"]
    top_k = cfg.get("top_k", _DEFAULT_TOP_K)
    alpha = cfg.get("alpha", _DEFAULT_ALPHA)

    async with factory() as session:
        hits = await semantic_service.hybrid_search(
            session,
            tenant_id=state["tenant_id"],
            query=state["user_query"],
            top_k=top_k,
            alpha=alpha,
        )

    return {
        "retrieved_schema": [_hit_to_dict(h) for h in hits],
    }


def _hit_to_dict(hit: Any) -> dict[str, Any]:
    """把 STE-21 Hit dataclass 序列化为 LangGraph 可 JSON 化的 dict。"""
    return {
        "type": getattr(hit, "type", None),
        "id": str(getattr(hit, "id", "")),
        "title": getattr(hit, "title", ""),
        "snippet": getattr(hit, "snippet", ""),
        "score": getattr(hit, "score", 0.0),
        "schema_name": getattr(hit, "schema_name", None),
        "table_name": getattr(hit, "table_name", None),
        "physical_column": getattr(hit, "physical_column", None),
    }
