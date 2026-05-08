"""STE-24：SSE 工具集。

- `encode_sse(event, data)`：把 event/data 编码为 SSE wire 格式
  `event: <type>\\ndata: <json>\\n\\n`，data 为 dict/list 自动 JSON 序列化。
- `translate_chunk(chunk)`：把 LangGraph `astream(stream_mode=['messages','updates'])`
  返回的 tuple `(mode, data)` 翻译成 0..N 个 SSE 字节帧。
  覆盖 plan §3.8.1 协议：
  * mode='messages' → token 事件（含 delta/node/step/model）
  * mode='updates' → node 事件 + 业务派生事件（sql/rows/chart）

零依赖纯函数模块；所有「事件协议」语义都集中在此处便于测试与演进。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


def encode_sse(event: str, data: Any) -> bytes:
    """SSE 帧编码。

    Args:
        event: 事件名（token / node / sql / rows / chart / error / done）
        data: dict / list / 字符串 / None；非字符串走 json.dumps，UUID/datetime
              等通过 default=str 兜底。

    Returns: bytes，已含末尾 `\\n\\n` 帧分隔符。
    """
    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode()


def translate_chunk(chunk: tuple[str, Any]) -> Iterable[bytes]:
    """LangGraph chunk → 0..N 个 SSE 帧。

    输入：`(mode, data)`，mode ∈ {'messages', 'updates', 'custom'}
    输出：bytes 序列；每条帧已 SSE-encoded。

    设计要点：
    - messages chunk 缺 langgraph_node 视为非法（plan §3.8.1）→ 跳过
    - messages chunk content 为空也跳过，避免空 token 帧打扰前端
    - rows 空数组仍 emit（columns=[] data=[]），便于前端区分「没数据」与「未查询」
    - sql_validate 节点返回的 error 是中间错误（被路由器消费再重试），SSE 层不
      emit，最终错误判定交给 chat_service 在 stream 结束后查 final state
    """
    mode, data = chunk

    if mode == "messages":
        if not isinstance(data, tuple) or len(data) != 2:
            return
        ai_chunk, meta = data
        node = meta.get("langgraph_node") if isinstance(meta, dict) else None
        if not node:
            return
        content = _extract_text(getattr(ai_chunk, "content", None))
        if not content:
            return
        payload: dict[str, Any] = {"delta": content, "node": node}
        if "langgraph_step" in meta:
            payload["step"] = meta["langgraph_step"]
        if "ls_model_name" in meta:
            payload["model"] = meta["ls_model_name"]
        yield encode_sse("token", payload)
        return

    if mode == "updates":
        if not isinstance(data, dict):
            return
        for node_name, delta in data.items():
            yield encode_sse("node", {"name": node_name, "status": "ok"})
            if not isinstance(delta, dict):
                continue
            if delta.get("validated_sql"):
                yield encode_sse("sql", {"sql": delta["validated_sql"]})
            if "rows" in delta and delta["rows"] is not None:
                rows = delta["rows"]
                cols = list(rows[0].keys()) if rows else []
                yield encode_sse("rows", {"columns": cols, "data": rows})
            if delta.get("chart_spec"):
                yield encode_sse("chart", {"option": delta["chart_spec"]})
        return

    # custom / values / debug / checkpoints / tasks 等暂不消费


def _extract_text(content: Any) -> str:
    """从 AIMessage(Chunk).content 取出纯文本：
    - str → 直接返回
    - list[dict|str]（multi-modal 形式）→ 拼接 text 字段
    - None / 其它 → 空串
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""
