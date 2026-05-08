"""STE-23：LangGraph 节点集合。

每个节点是 `async def fn(state, config) -> dict[str, Any]` 形态，
返回的 dict 由 LangGraph 按 reducer 合并到 state。
"""

from app.graph.nodes.chart import chart
from app.graph.nodes.retrieve import retrieve
from app.graph.nodes.sql_exec import sql_exec
from app.graph.nodes.sql_gen import sql_gen
from app.graph.nodes.sql_validate import sql_validate
from app.graph.nodes.summarize import summarize

__all__ = [
    "chart",
    "retrieve",
    "sql_exec",
    "sql_gen",
    "sql_validate",
    "summarize",
]
