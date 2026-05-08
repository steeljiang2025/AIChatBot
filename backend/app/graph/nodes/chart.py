"""STE-23：chart 节点。

渲染 STE-20 `chart_recommend.j2` prompt，让 LLM 推荐 ECharts 图表配置。
- rows 为空 → chart_spec=None，跳过 LLM 调用
- 非空 → 解析 LLM 返回的 JSON（兼容 markdown ```json ... ``` 包裹）
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from app.graph.state import AgentState


_FENCE_RE = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE
)


async def chart(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    rows = state.get("rows") or []
    if not rows:
        return {"chart_spec": None}

    from app.llm import prompts
    from app.llm.qwen import get_chat_llm

    cfg: dict[str, Any] = config.get("configurable", {}) or {}
    llm = cfg.get("chat_llm") or get_chat_llm()

    prompt_text = prompts.render_prompt(
        "chart_recommend",
        user_query=state.get("user_query", ""),
        columns=_infer_columns(rows),
        rows_preview=rows[:5],
    )

    msg = await llm.ainvoke(prompt_text)
    spec = _parse_json(_extract_text(msg))
    return {"chart_spec": spec}


def _extract_text(msg: Any) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c)
            for c in content
        )
    return str(content)


def _parse_json(text: str) -> dict[str, Any] | None:
    s = text.strip()
    m = _FENCE_RE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None


def _infer_columns(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """从首行推断列结构，给 prompt 提供 column 信息。"""
    if not rows:
        return []
    first = rows[0]
    return [
        {"name": k, "type": type(v).__name__} for k, v in first.items()
    ]
