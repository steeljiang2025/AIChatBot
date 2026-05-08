"""STE-24：SSE 工具集（占位）。

模块职责（commit 2 实现）：
- `encode_sse(event, data)`：把 event/data 编码为 SSE wire 格式
  `event: <type>\\ndata: <json>\\n\\n`，data 为 dict/list 自动 JSON 序列化。
- `translate_chunk(chunk)`：把 LangGraph `astream(stream_mode=['messages','updates'])`
  返回的 tuple `(mode, data)` 翻译成 0..N 个 SSE 字节帧。
  覆盖 plan §3.8.1 的协议：
  * mode='messages' → token 事件（含 delta/node/step/model）
  * mode='updates' → node 事件 + 业务派生事件（sql/rows/chart）

零依赖纯函数模块；编码细节集中在此处便于测试。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def encode_sse(event: str, data: Any) -> bytes:
    """SSE 帧编码。

    Args:
        event: 事件名（token / node / sql / rows / chart / error / done）
        data: dict / list / 字符串 / None；非字符串会 JSON 序列化（ensure_ascii=False）

    Returns: bytes，已含末尾 `\\n\\n` 帧分隔符
    """
    raise NotImplementedError


def translate_chunk(chunk: tuple[str, Any]) -> Iterable[bytes]:
    """LangGraph chunk → 0..N 个 SSE 帧。

    输入：`(mode, data)`，mode ∈ {'messages', 'updates', 'custom'}
    输出：bytes 序列；每条帧已 SSE-encoded，可直接 yield 给 StreamingResponse
    """
    raise NotImplementedError
    yield  # pragma: no cover  -- 保持 generator 类型签名
