"""STE-23：summarize 节点。

渲染 STE-20 `summarize.j2` prompt，让 LLM 给出 ≤ 3 句业务总结。
失败兜底（state.error 存在）→ 用同一个 prompt（`summarize.j2` 已支持 error
分支），由 LLM 用友好语言告知用户失败。

只回写 messages（追加 AIMessage），不污染其它业务字段。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from app.graph.state import AgentState


async def summarize(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    from app.llm import prompts
    from app.llm.qwen import get_chat_llm

    cfg: dict[str, Any] = config.get("configurable", {}) or {}
    llm = cfg.get("chat_llm") or get_chat_llm()

    prompt_text = prompts.render_prompt(
        "summarize",
        user_query=state.get("user_query", ""),
        rows=(state.get("rows") or [])[:20],
        error=state.get("error"),
    )

    msg = await llm.ainvoke(prompt_text)
    content = _extract_text(msg)
    return {"messages": [AIMessage(content=content)]}


def _extract_text(msg: Any) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c)
            for c in content
        )
    return str(content)
