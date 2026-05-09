"""STE-23：sql_exec 节点。

用 biz_engine 只读连接执行 validated_sql；用 SQLAlchemy `bindparam(:tid)`
绑定 tenant_id（与 STE-22 注入的占位符 `:tid` 对齐）。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy import text

if TYPE_CHECKING:
    from app.graph.state import AgentState


_DEFAULT_TIMEOUT_MS = 30000


def _json_safe_scalar(value: Any) -> Any:
    """把驱动返回的标量转成 JSON / checkpoint / JSONB 可序列化的形态。

    Biz 库 NUMERIC → Python Decimal，写入 LangGraph checkpoint（psycopg json）
    时会触发「Decimal is not JSON serializable」。此处统一为 str，避免精度问题
    又不引入 float 误差。
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return value


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _json_safe_scalar(v) for k, v in row.items()}


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
        rows = [_json_safe_row(dict(r._mapping)) for r in result]

    return {"rows": rows}
