"""STE-24：/chat/stream 编排服务（占位）。

模块职责（commit 2 实现）：
- `stream_chat(...)` AsyncIterator[bytes]：
  1) 校验会话归属（404 if not）
  2) 用户消息立即落库（即使 stream 中途出错也保留用户原话）
  3) 加载 schema 白名单（per-request from SemanticTable）
  4) graph.astream(stream_mode=['messages','updates']) 翻译为 SSE 帧
     同时累积助手文本 / sql / rows / chart_spec / error
  5) astream 结束后查 final state；state.error 兜底 → emit error 事件
  6) 助手消息落库（content + extra={sql, rows_preview, chart, error}）
  7) 总是 emit `event: done {message_id}` 收尾
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from app.core.config import Settings


async def stream_chat(
    *,
    graph: "CompiledStateGraph",
    meta_session: "AsyncSession",
    meta_session_factory: "async_sessionmaker",
    biz_engine: "AsyncEngine",
    settings: "Settings",
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    user_content: str,
) -> AsyncIterator[bytes]:
    """编排 /chat/stream 全流程，逐帧 yield SSE bytes。

    调用方（api/chat.py）只负责把 yielded bytes 包成 StreamingResponse。
    异常的兜底：内部 catch 所有 Exception，emit error 事件后仍 emit done，
    保证前端 onclose 永远能收到结束事件。
    """
    raise NotImplementedError
    yield  # pragma: no cover
