"""STE-24：SSE 帧编码 + LangGraph chunk 翻译器单测。

策略：
- encode_sse 是纯函数，直接对比 bytes
- translate_chunk 用 (mode, data) 元组喂入，断言产出帧序列
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from app.services.sse import encode_sse, translate_chunk


# ============ encode_sse ============


def test_encode_sse_dict_data() -> None:
    out = encode_sse("token", {"delta": "hi", "node": "summarize"})
    assert out.endswith(b"\n\n")
    text = out.decode("utf-8")
    assert text.startswith("event: token\n")
    assert "data: " in text
    # 解析 data 行
    data_line = [line for line in text.split("\n") if line.startswith("data: ")][0]
    parsed = json.loads(data_line[len("data: "):])
    assert parsed == {"delta": "hi", "node": "summarize"}


def test_encode_sse_string_data_pass_through() -> None:
    out = encode_sse("done", "ok")
    text = out.decode("utf-8")
    assert text == "event: done\ndata: ok\n\n"


def test_encode_sse_unicode_not_escaped() -> None:
    out = encode_sse("token", {"delta": "上月销售额"})
    assert "上月销售额" in out.decode("utf-8")


def test_encode_sse_handles_uuid_via_default_str() -> None:
    """UUID / datetime 等非 JSON-原生类型应通过 default=str 兜底。"""
    import uuid as _uuid

    payload = {"message_id": _uuid.UUID("11111111-1111-1111-1111-111111111111")}
    out = encode_sse("done", payload).decode("utf-8")
    assert "11111111-1111-1111-1111-111111111111" in out


def test_encode_sse_frame_has_double_newline() -> None:
    """SSE 协议要求每帧以 `\\n\\n` 结尾。"""
    out = encode_sse("ping", {"a": 1})
    assert out.count(b"\n\n") == 1


# ============ translate_chunk: messages mode → token ============


def test_translate_messages_chunk_emits_token() -> None:
    chunk_meta = {
        "langgraph_node": "summarize",
        "langgraph_step": 6,
        "ls_model_name": "qwen3-max",
    }
    chunk = ("messages", (AIMessageChunk(content="hello"), chunk_meta))
    frames = list(translate_chunk(chunk))
    assert len(frames) == 1
    text = frames[0].decode("utf-8")
    assert text.startswith("event: token\n")
    payload = _parse_data(frames[0])
    assert payload["delta"] == "hello"
    assert payload["node"] == "summarize"
    assert payload["step"] == 6
    assert payload["model"] == "qwen3-max"


def test_translate_messages_skips_when_no_node_field() -> None:
    """plan §3.8.1：缺 langgraph_node 的 token 视为非法，不发送。"""
    chunk = ("messages", (AIMessageChunk(content="x"), {"langgraph_step": 1}))
    frames = list(translate_chunk(chunk))
    assert frames == []


def test_translate_messages_skips_empty_content() -> None:
    chunk = ("messages", (AIMessageChunk(content=""), {"langgraph_node": "summarize"}))
    frames = list(translate_chunk(chunk))
    assert frames == []


def test_translate_messages_handles_list_content() -> None:
    """某些 provider 返回 [{type:'text', text:'...'}] 列表形式。"""
    content = [{"type": "text", "text": "hel"}, {"type": "text", "text": "lo"}]
    chunk = ("messages", (AIMessageChunk(content=content), {"langgraph_node": "summarize"}))
    frames = list(translate_chunk(chunk))
    assert len(frames) == 1
    payload = _parse_data(frames[0])
    assert payload["delta"] == "hello"


def test_translate_messages_with_full_aimessage() -> None:
    """非流式节点（ainvoke）出来的是完整 AIMessage 而非 Chunk，也应能翻译。"""
    chunk = ("messages", (AIMessage(content="完整一段"), {"langgraph_node": "summarize"}))
    frames = list(translate_chunk(chunk))
    payload = _parse_data(frames[0])
    assert payload["delta"] == "完整一段"


# ============ translate_chunk: updates mode → node + 业务事件 ============


def test_translate_updates_emits_node_event() -> None:
    chunk = ("updates", {"retrieve": {"retrieved_schema": [{"type": "table"}]}})
    frames = list(translate_chunk(chunk))
    assert len(frames) == 1
    payload = _parse_data(frames[0])
    assert payload == {"name": "retrieve", "status": "ok"}


def test_translate_updates_emits_sql_event_when_validated_sql_present() -> None:
    chunk = ("updates", {
        "sql_validate": {"validated_sql": "SELECT 1 WHERE tenant_id = :tid"},
    })
    frames = list(translate_chunk(chunk))
    assert len(frames) == 2
    events = [f.split(b"\n")[0].decode() for f in frames]
    assert "event: node" in events
    assert "event: sql" in events
    sql_frame = next(f for f in frames if b"event: sql" in f)
    payload = _parse_data(sql_frame)
    assert payload == {"sql": "SELECT 1 WHERE tenant_id = :tid"}


def test_translate_updates_emits_rows_event_with_columns() -> None:
    chunk = ("updates", {
        "sql_exec": {"rows": [{"product": "A", "amount": 100}, {"product": "B", "amount": 80}]},
    })
    frames = list(translate_chunk(chunk))
    rows_frame = next(f for f in frames if b"event: rows" in f)
    payload = _parse_data(rows_frame)
    assert payload["columns"] == ["product", "amount"]
    assert len(payload["data"]) == 2


def test_translate_updates_rows_empty_still_emits_with_no_columns() -> None:
    """rows=[] 应 emit rows 事件（columns=[] data=[]），让前端能区分「没数据」与「未查询」。"""
    chunk = ("updates", {"sql_exec": {"rows": []}})
    frames = list(translate_chunk(chunk))
    rows_frame = next(f for f in frames if b"event: rows" in f)
    payload = _parse_data(rows_frame)
    assert payload == {"columns": [], "data": []}


def test_translate_updates_emits_chart_when_chart_spec_present() -> None:
    chunk = ("updates", {"chart": {"chart_spec": {"chart_type": "bar"}}})
    frames = list(translate_chunk(chunk))
    chart_frame = next(f for f in frames if b"event: chart" in f)
    payload = _parse_data(chart_frame)
    assert payload == {"option": {"chart_type": "bar"}}


def test_translate_updates_skips_chart_when_chart_spec_none() -> None:
    """chart 节点 rows 为空时返回 chart_spec=None；不应 emit chart 事件。"""
    chunk = ("updates", {"chart": {"chart_spec": None}})
    frames = list(translate_chunk(chunk))
    # 只有 node 事件
    assert len(frames) == 1
    assert b"event: node" in frames[0]


def test_translate_updates_does_not_emit_error_on_intermediate_state_error() -> None:
    """sql_validate 节点回写的 error 是中间错误（被路由器消费），SSE 层不 emit。
    最终错误由 chat_service 在 stream 结束后判定 final state。"""
    chunk = ("updates", {"sql_validate": {"error": "UnregisteredTableError"}})
    frames = list(translate_chunk(chunk))
    # 只有 node 事件
    assert len(frames) == 1
    assert b"event: node" in frames[0]


def test_translate_unknown_mode_yields_nothing() -> None:
    chunk = ("custom", {"any": "thing"})
    assert list(translate_chunk(chunk)) == []


# ============ helper ============


def _parse_data(frame: bytes) -> Any:
    text = frame.decode("utf-8")
    line = [line for line in text.split("\n") if line.startswith("data: ")][0]
    return json.loads(line[len("data: "):])


# 让 pytest-asyncio 不再抱怨
__all__: list[str] = []
