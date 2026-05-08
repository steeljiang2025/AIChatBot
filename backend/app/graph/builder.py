"""STE-23：StateGraph 装配（占位）。

`build_graph(checkpointer)` 装出工作流编译产物：

    retrieve → sql_gen → sql_validate
                              │
                ┌─ ok ───────►│──► sql_exec → chart → summarize → END
                │             │
                └─ retry < N ─┴──► sql_gen
                              │
                              └─ retry >= N ──► summarize（带 error）

（plan §3.7 校验失败回写错误重试，最多 N 次后降级返回错误事件）

调用方传入 RunnableConfig.configurable：
- meta_session_factory: callable() → AsyncSession 上下文管理器
- biz_engine: SQLAlchemy AsyncEngine
- known_tables / known_columns / tenant_scoped_tables: SQL 白名单
- max_rows / max_retries / sql_exec_timeout_ms: 数值参数
- chat_llm（可选）: 测试时注入 mock；生产为 None → 节点取 lru_cache 单例
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph


_NODES: Final[tuple[str, ...]] = (
    "retrieve",
    "sql_gen",
    "sql_validate",
    "sql_exec",
    "chart",
    "summarize",
)


def build_graph(
    checkpointer: "BaseCheckpointSaver | None" = None,
) -> "CompiledStateGraph":
    """组装并编译 StateGraph。

    Args:
        checkpointer: AsyncPostgresSaver / InMemorySaver；None 表示无持久化。

    Returns: CompiledStateGraph，可 .ainvoke / .astream。
    """
    raise NotImplementedError


__all__ = ["build_graph"]
