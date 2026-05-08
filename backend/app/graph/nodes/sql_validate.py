"""STE-23：sql_validate 节点。

调用 STE-22 `sanitize_sql` 走完整安全流水线（含 tenant_guard）。
- 成功：写 validated_sql，error 重置为 None
- 失败：写 error，retries += 1（reducer add 累加）
  路由层依据 retries < max_retries 决定回 sql_gen 重试或走失败分支
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from app.graph.state import AgentState


async def sql_validate(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    from app.services import sql_safety_service
    from app.sql_safety import SqlSafetyError

    cfg: dict[str, Any] = config.get("configurable", {}) or {}

    try:
        validated = sql_safety_service.sanitize_sql(
            state["candidate_sql"],
            known_tables=cfg["known_tables"],
            known_columns=cfg["known_columns"],
            tenant_scoped_tables=cfg["tenant_scoped_tables"],
            max_rows=cfg.get("max_rows", 5000),
        )
    except SqlSafetyError as e:
        return {"error": f"{type(e).__name__}: {e}", "retries": 1}

    return {"validated_sql": validated, "error": None}
