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


def _physical_fqn(hit: dict[str, Any]) -> str | None:
    s = str(hit.get("schema_name") or "").strip().lower()
    t = str(hit.get("table_name") or "").strip().lower()
    if not s or not t:
        return None
    return f"{s}.{t}"


def _schema_cards_from_whitelist(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """本请求 SQL 安全白名单中的全部物理表及其英文列清单（truth source）。"""
    kt = cfg.get("known_tables") or set()
    kc = cfg.get("known_columns") or {}
    out: dict[str, dict[str, Any]] = {}
    for schema_n, tbl_n in kt:
        s_lc = schema_n.lower() if isinstance(schema_n, str) else str(schema_n).lower()
        t_lc = tbl_n.lower() if isinstance(tbl_n, str) else str(tbl_n).lower()
        raw = kc.get((s_lc, t_lc)) or kc.get((schema_n, tbl_n)) or set()
        cols = sorted({str(c).lower() for c in raw})
        fqn = f"{s_lc}.{t_lc}"
        out[fqn] = {
            "table": fqn,
            "display_name": "",
            "columns": cols,
            "description": "",
        }
    return out


def merge_whitelist_with_rag_schema_cards(
    cfg: dict[str, Any],
    rag_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """白名单列为完整英文字段集合；检索结果只做展示名 / 语义补充。「无白名单」时退回纯检索卡片（兼容单测 stub）。"""
    wl = _schema_cards_from_whitelist(cfg)
    rag_by_physical: dict[str, dict[str, Any]] = {}
    extras: list[dict[str, Any]] = []
    for c in rag_cards:
        tk = str(c.get("table") or "")
        if tk.startswith("（"):
            extras.append(c)
            continue
        rag_by_physical[tk.lower()] = c

    if not wl:
        return rag_cards

    merged: list[dict[str, Any]] = []
    for fqn in sorted(wl.keys()):
        base = dict(wl[fqn])
        rag = rag_by_physical.get(fqn)
        if rag:
            if rag.get("display_name"):
                base["display_name"] = rag["display_name"]
            rd = str(rag.get("description") or "").strip()
            if rd:
                base["description"] = (base["description"] + " " + rd).strip()
        merged.append(base)

    # 检索命中但未登记白名单（少见）：仍可提示模型，但后续 validate 会变严
    for fqn, rag in rag_by_physical.items():
        if fqn not in wl:
            merged.append(dict(rag))

    merged.extend(extras)
    return merged


def _retrieved_hits_to_schema_cards(
    hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """把 hybrid_search hits 合并为 `sql_gen.j2` 的 schema_cards（物理表维度）。"""
    buckets: dict[str, dict[str, Any]] = {}
    extras: list[dict[str, Any]] = []

    for h in hits:
        tp = h.get("type")
        title = (h.get("title") or "").strip()
        snippet = (h.get("snippet") or "").strip()
        fqn = _physical_fqn(h)

        if tp in ("table", "column") and fqn:
            b = buckets.setdefault(
                fqn,
                {
                    "table": fqn,
                    "display_name": "",
                    "columns": [],
                    "description": "",
                },
            )
            if tp == "table":
                if title:
                    b["display_name"] = title
                if snippet:
                    b["description"] = (b["description"] + " " + snippet).strip()
            else:
                col = (h.get("physical_column") or "").strip().lower()
                if col and col not in b["columns"]:
                    b["columns"].append(col)
                if title or snippet:
                    b["description"] = (
                        b["description"]
                        + f" 列 `{col}`（{title}）：{snippet}".strip()
                    ).strip()
            continue

        if not title:
            continue
        label = {"term": "术语", "relation": "关联"}.get(str(tp), str(tp))
        extras.append(
            {
                "table": f"（{label}，非物理表）{title}",
                "display_name": title,
                "columns": [],
                "description": snippet,
            }
        )

    merged = list(buckets.values())
    merged.sort(key=lambda x: x["table"])
    for m in merged:
        m["columns"] = sorted(set(m["columns"]))
    return merged + extras


async def sql_gen(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    from app.llm import prompts
    from app.llm.qwen import get_chat_llm

    cfg: dict[str, Any] = config.get("configurable", {}) or {}
    llm = cfg.get("chat_llm") or get_chat_llm()
    max_rows = cfg.get("max_rows", 5000)

    rag_cards = _retrieved_hits_to_schema_cards(state.get("retrieved_schema") or [])
    schema_cards = merge_whitelist_with_rag_schema_cards(cfg, rag_cards)

    prompt_text = prompts.render_prompt(
        "sql_gen",
        question=state["user_query"],
        schema_cards=schema_cards,
        tenant_id=str(state["tenant_id"]),
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
