"""SQL 字符串实用函数（与驱动/RAG 无关）。

用于折叠模型/流式把同一条 SELECT 复述两遍且仅用分号粘连的情况：
`SELECT ... LIMIT 5000;SELECT ... LIMIT 5000`
"""

from __future__ import annotations

import re

_STRIP_LEADING_SELECT = re.compile(
    r"\bSELECT\s+[\s\S]*?LIMIT\s+\d+\b\s*;?",
    re.IGNORECASE,
)


def dedupe_semicolon_sql_clauses(text: str) -> str:
    """折叠「仅由分号拼接」的连续重复 SELECT 片段（空白归一化后比较）。

    不影响单条 SQL 内子查询分号（本场景单条为整段 SELECT…LIMIT）。
    """
    if "SELECT" not in text.upper() or ";" not in text:
        return text.strip()
    parts = text.split(";")
    out: list[str] = []
    prev_norm: str | None = None
    for raw in parts:
        seg = raw.strip()
        if not seg:
            continue
        upper = seg.upper()
        if upper.startswith("SELECT"):
            key = " ".join(seg.split())
            if key == prev_norm:
                continue
            prev_norm = key
            out.append(seg)
        else:
            prev_norm = None
            out.append(seg)
    return ";".join(out) if out else text.strip()


def strip_select_echoes(text: str) -> str:
    """去掉正文里复述的整段 SELECT…LIMIT（可多段；模型常把 SQL 抄进总结）。"""
    t = text.strip()
    if "SELECT" not in t.upper():
        return t
    while True:
        nxt = _STRIP_LEADING_SELECT.sub("", t, count=1).strip().lstrip(";").strip()
        if nxt == t or (not nxt and not t):
            break
        if not nxt:
            return ""
        t = nxt
    return t


def dedupe_duplicate_sentences(text: str) -> str:
    """去掉完全相同的分句重复（模型常把同一句说两遍）。"""
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


def sanitize_assistant_summary_text(text: str) -> str:
    """总结气泡：去重粘连 SQL + 去掉复述的 SELECT 块 + 去重中文句。"""
    t = dedupe_semicolon_sql_clauses(text)
    t = strip_select_echoes(t)
    t = dedupe_duplicate_sentences(t)
    return t
