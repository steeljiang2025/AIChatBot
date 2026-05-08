"""STE-23：sql_exec 节点。

用 biz_engine 只读连接执行 validated_sql；用 SQLAlchemy `bindparam(:tid)`
绑定 tenant_id（与 STE-22 注入的占位符 `:tid` 对齐）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy import text

if TYPE_CHECKING:
    from app.graph.state import AgentState


_DEFAULT_TIMEOUT_MS = 30000


async def sql_exec(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    cfg: dict[str, Any] = config.get("configurable", {}) or {}
    biz_engine = cfg["biz_engine"]
    timeout_ms = int(cfg.get("sql_exec_timeout_ms", _DEFAULT_TIMEOUT_MS))

    sql = state["validated_sql"]
    tenant_id = state["tenant_id"]

    async with biz_engine.connect() as conn:
        # 单连接级别限制：避免单条 SQL 拖死业务库
        await conn.execute(
            text(f"SET LOCAL statement_timeout = {timeout_ms}")
        )
        result = await conn.execute(text(sql), {"tid": str(tenant_id)})
        rows = [dict(r._mapping) for r in result]

    return {"rows": rows}
