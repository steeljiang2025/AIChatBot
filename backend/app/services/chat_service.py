"""STE-24：/chat/stream 编排服务。

`stream_chat(...)` 是 AsyncIterator[bytes]：
1) 用户消息立即落库（即使 stream 中途出错也保留用户原话）
2) 加载 schema 白名单（per-request from SemanticTable）
3) graph.astream(stream_mode=['messages','updates']) 翻译为 SSE 帧；
   同时累积助手文本 / sql / rows / chart_spec / error
4) astream 结束后查 final state；state.error 兜底 → emit error 事件
5) 助手消息落库（content + extra={sql, rows_preview, chart, error}）
6) 总是 emit `event: done {message_id}` 收尾

调用方（api/chat.py）只负责：鉴权 + 校验 session 归属 + 把 yielded bytes
包成 StreamingResponse。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage

from app.services import session_repo
from app.services.schema_provider import load_schema_whitelist
from app.sql_string import dedupe_semicolon_sql_clauses
from app.services.sse import encode_sse, translate_chunk

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from app.core.config import Settings


logger = logging.getLogger(__name__)


_ROWS_PREVIEW_LIMIT = 20  # extra.rows_preview 最多保留前 N 行，防止 JSONB 过大


async def stream_chat(
    *,
    graph: CompiledStateGraph,
    meta_session: AsyncSession,
    meta_session_factory: async_sessionmaker,
    biz_engine: AsyncEngine,
    settings: Settings,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    user_content: str,
) -> AsyncIterator[bytes]:
    """编排 /chat/stream 全流程，逐帧 yield SSE bytes。"""
    # 1) 用户消息立即落库（不等工作流，保证原话不丢）
    await session_repo.add_message(
        meta_session,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        role="user",
        content=user_content,
    )
    await meta_session.commit()

    # 2) 加载 schema 白名单（per-request）
    whitelist = await load_schema_whitelist(meta_session, tenant_id=tenant_id)

    # 3) 构造 graph 配置（thread_id = session_id 以接入 PostgresSaver 多轮记忆）
    config: dict[str, Any] = {
        "configurable": {
            "thread_id": str(session_id),
            "biz_engine": biz_engine,
            "meta_session_factory": meta_session_factory,
            "known_tables": whitelist.known_tables,
            "known_columns": whitelist.known_columns,
            "tenant_scoped_tables": whitelist.tenant_scoped_tables,
            "max_rows": settings.sql_max_rows,
            "max_retries": settings.graph_max_retries,
            "sql_exec_timeout_ms": settings.sql_exec_timeout_ms,
        }
    }
    initial_state: dict[str, Any] = {
        "messages": [HumanMessage(content=user_content)],
        "tenant_id": tenant_id,
        "user_query": user_content,
    }

    accumulated_assistant: list[str] = []
    final_sql: str | None = None
    final_rows: list[dict[str, Any]] | None = None
    final_chart: dict[str, Any] | None = None
    final_error: str | None = None
    stream_failed = False

    try:
        async for chunk in graph.astream(
            initial_state, config=config, stream_mode=["messages", "updates"]
        ):
            mode, data = chunk
            if mode == "messages" and isinstance(data, tuple) and len(data) == 2:
                ai_chunk, meta = data
                node = meta.get("langgraph_node") if isinstance(meta, dict) else None
                if node == "summarize":
                    text = _content_text(getattr(ai_chunk, "content", None))
                    if text:
                        accumulated_assistant.append(text)
            elif mode == "updates" and isinstance(data, dict):
                for _node_name, delta in data.items():
                    if not isinstance(delta, dict):
                        continue
                    if delta.get("validated_sql"):
                        final_sql = delta["validated_sql"]
                        # 一旦拿到通过校验的 SQL，说明重试阶段已过，清掉流式错误缓存
                        final_error = None
                    if "rows" in delta and delta["rows"] is not None:
                        final_rows = delta["rows"]
                    if delta.get("chart_spec"):
                        final_chart = delta["chart_spec"]
                    # 必须用「包含 error 键」判断：校验重试会先写 error，成功后同节点带回
                    # error=None；若只用 truthy assign，会持续保留中间错误导致 done 误判失败。
                    if "error" in delta:
                        final_error = delta["error"]
            for frame in translate_chunk(chunk):
                yield frame

        # 4) 检查 final state.error（重试用尽 + summarize 兜底场景）
        try:
            snapshot = await graph.aget_state(config)
            state_values = getattr(snapshot, "values", None) or {}
            if state_values.get("error"):
                final_error = state_values["error"]
                yield encode_sse(
                    "error",
                    {"code": "workflow_failed", "message": final_error},
                )
        except Exception as exc:
            logger.warning("aget_state 读取最终状态失败：%s", exc)

    except Exception as exc:
        # graph 内部抛 Python 异常（如 DB 断连）→ emit error 后仍走 done 落库
        stream_failed = True
        final_error = str(exc)
        logger.exception("graph.astream 抛出未捕获异常")
        yield encode_sse(
            "error",
            {"code": "internal_error", "message": final_error},
        )

    # 5) 助手消息落库（哪怕失败也要落，便于审计 / 用户回看）
    assistant_content = "".join(accumulated_assistant) or (
        f"[error] {final_error}" if final_error else ""
    )
    extra: dict[str, Any] = {}
    if final_sql:
        extra["sql"] = dedupe_semicolon_sql_clauses(final_sql)
    if final_rows is not None:
        extra["rows_preview"] = final_rows[:_ROWS_PREVIEW_LIMIT]
    if final_chart:
        extra["chart"] = final_chart
    if final_error:
        extra["error"] = final_error

    asst_msg = await session_repo.add_message(
        meta_session,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        role="assistant",
        content=assistant_content,
        extra=extra or None,
    )
    await meta_session.commit()

    # 6) done 帧（永远是最后一条；流即使失败也保证有 done）
    yield encode_sse(
        "done",
        {"message_id": str(asst_msg.id), "ok": not stream_failed and not final_error},
    )


def _content_text(content: Any) -> str:
    """从 AIMessage(Chunk).content 取出纯文本（与 sse._extract_text 同样逻辑，
    在 chat_service 里独立实现避免循环依赖）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text") or item.get("content")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""
