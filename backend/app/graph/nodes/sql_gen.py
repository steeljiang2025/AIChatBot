"""STE-23：sql_gen 节点。

渲染 STE-20 `sql_gen.j2` prompt，调 ChatOpenAI 生成 SQL。
LLM 经常返回 markdown ```sql ... ``` 包裹，本节点剥掉外壳后再交给 sql_validate。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from app.graph.state import AgentState


_FENCE_RE = re.compile(r"^```(?:sql)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


async def sql_gen(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    from app.llm import prompts
    from app.llm.qwen import get_chat_llm

    cfg: dict[str, Any] = config.get("configurable", {}) or {}
    llm = cfg.get("chat_llm") or get_chat_llm()
    max_rows = cfg.get("max_rows", 5000)

    prompt_text = prompts.render_prompt(
        "sql_gen",
        user_query=state["user_query"],
        semantic_cards=state.get("retrieved_schema") or [],
        max_rows=max_rows,
        prior_error=state.get("error"),
    )

    msg = await llm.ainvoke(prompt_text)
    sql = _strip_fence(_extract_text(msg))

    return {"candidate_sql": sql, "error": None}


def _extract_text(msg: Any) -> str:
    """兼容 AIMessage / AIMessageChunk / 纯字符串。"""
    content = getattr(msg, "content", msg)
    if isinstance(content, list):
        # 某些 provider 会返回 [{'type':'text','text':...}, ...]
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif isinstance(c, str):
                parts.append(c)
        return "".join(parts)
    return str(content)


def _strip_fence(text: str) -> str:
    """剥 ```sql ... ``` / ``` ... ``` 外壳；无 fence 时原样返回（仅 strip）。"""
    s = text.strip()
    m = _FENCE_RE.match(s)
    if m:
        return m.group(1).strip()
    return s
