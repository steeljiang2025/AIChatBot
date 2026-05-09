"""STE-23：summarize 节点。

渲染 STE-20 `summarize.j2` prompt，让 LLM 给出 ≤ 3 句业务总结。
失败兜底（state.error 存在）→ 用同一个 prompt（`summarize.j2` 已支持 error
分支），由 LLM 用友好语言告知用户失败。

只回写 messages（追加 AIMessage），不污染其它业务字段。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.sql_string import sanitize_assistant_summary_text

if TYPE_CHECKING:
    from app.graph.state import AgentState

_SAMPLE_ROWS_MAX = 8

# 模型在仍有 sample_rows 时仍可能编造「缺月份」等，与 SQL/事实矛盾时用确定性结果覆盖
_MISSING_FIELD_HALLUCINATION_RE = re.compile(
    r"(数据表.*缺少.*月份|缺少月份字段|缺月份字段|无法按月|无月份字段|没有月份)"
    r"|(缺少.*字段.*按月)",
    re.IGNORECASE,
)


def _dedupe_halved_repeat(text: str) -> str:
    """整段内容被模型原样粘贴两遍（A+B 与 A+B 相同）时，保留一半。"""
    t = text.strip()
    if len(t) < 4:
        return text
    n = len(t)
    half = n // 2
    if n % 2 == 0 and t[:half] == t[half:]:
        return t[:half].rstrip()
    return text


def _dedupe_sentences(text: str) -> str:
    """去掉「同一句复制两遍」之类的重复。"""
    parts = [p.strip() for p in re.split(r"[。．!！?？]", text) if p.strip()]
    if not parts:
        return text.strip()
    seen: set[str] = set()
    kept: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            kept.append(p)
    return "。".join(kept) + "。"


def _deterministic_summary_from_rows(rows: list[dict[str, Any]]) -> str:
    """仅用查询结果拼成短结论，不依赖模型发挥（金额等已为字符串）。"""
    month_key = _first_key_like(rows[0], {"month", "月份", "月"}) if rows else None
    value_key = (
        _first_numericish_key(rows[0], exclude={month_key} if month_key else set())
        if rows
        else None
    )
    if month_key and value_key:
        parts = [
            f"{_format_month(r.get(month_key))}销售额为 {r.get(value_key)}"
            for r in rows[:_SAMPLE_ROWS_MAX]
        ]
        suffix = "；".join(parts)
        return f"共 {len(rows)} 个月份汇总：{suffix}。"

    segs: list[str] = []
    for r in rows[:_SAMPLE_ROWS_MAX]:
        pairs = "，".join(f"{k} 为 {v}" for k, v in r.items())
        segs.append(pairs)
    n = len(rows)
    body = "；".join(segs)
    return f"共 {n} 条汇总：{body}。"


def _first_key_like(row: dict[str, Any], candidates: set[str]) -> str | None:
    for key in row:
        k = str(key).lower()
        if k in candidates or k.endswith("_month") or "month" in k:
            return key
    return None


def _first_numericish_key(row: dict[str, Any], *, exclude: set[str]) -> str | None:
    preferred = ("sales", "amount", "total", "sum", "gmv", "revenue", "销售", "金额")
    keys = [k for k in row if k not in exclude]
    for key in keys:
        lk = str(key).lower()
        if any(p in lk for p in preferred):
            return key
    return keys[0] if keys else None


def _format_month(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return "该月"
    if text.endswith("月"):
        return text
    try:
        n = int(float(text))
    except ValueError:
        return text
    return f"{n} 月"


def _maybe_replace_hallucinated_summary(
    content: str, rows: list[dict[str, Any]]
) -> str:
    if not rows or not content.strip():
        return content
    if _MISSING_FIELD_HALLUCINATION_RE.search(content):
        return _deterministic_summary_from_rows(rows)
    return content


def _cell_for_prompt(v: Any) -> Any:
    """与 sql_exec 返回一起：日期/UUID/Decimal 在 Jinja 里可读、且不误导模型。"""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).decode("utf-8", errors="replace")
    return v


def _row_for_prompt(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _cell_for_prompt(v) for k, v in row.items()}


def _stats_from_state(state: AgentState) -> dict[str, Any]:
    rows = state.get("rows") or []
    stats: dict[str, Any] = {"total_rows": len(rows)}
    err = state.get("error")
    if err:
        stats["workflow_error"] = err
    if rows:
        stats["columns"] = ", ".join(rows[0].keys())
        stats["sample_rows"] = [
            _row_for_prompt(r) for r in rows[:_SAMPLE_ROWS_MAX]
        ]
    return stats


async def summarize(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    from app.llm import prompts
    from app.llm.qwen import get_chat_llm

    cfg: dict[str, Any] = config.get("configurable", {}) or {}
    llm = cfg.get("chat_llm") or get_chat_llm()

    rows = state.get("rows") or []
    # 查询成功但 0 行：固定话术，避免模型编造「缺字段」等原因
    if not state.get("error") and len(rows) == 0:
        return {
            "messages": [AIMessage(content="未查到符合条件的数据。")],
            "error": None,
        }
    if state.get("error") and not rows:
        return {
            "messages": [
                AIMessage(content="这次查询未能通过安全校验，未执行数据库查询。")
            ],
            "error": None,
        }

    prompt_text = prompts.render_prompt(
        "summarize",
        question=state.get("user_query", ""),
        stats=_stats_from_state(state),
    )

    msg = await llm.ainvoke(prompt_text)
    content = _extract_text(msg)
    content = sanitize_assistant_summary_text(content)
    content = _dedupe_halved_repeat(content)
    content = _dedupe_sentences(content)
    content = _maybe_replace_hallucinated_summary(content, rows)
    # 收尾总结后清掉 workflow error，避免 chat_service final `aget_state`
    # 仍带旧 error 误判为 workflow_failed（用户已拿到自然语言兜底）。
    return {"messages": [AIMessage(content=content)], "error": None}


def _extract_text(msg: Any) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c)
            for c in content
        )
    return str(content)
