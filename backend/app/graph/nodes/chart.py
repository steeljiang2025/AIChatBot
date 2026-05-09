"""STE-23：chart 节点。

渲染 STE-20 `chart_recommend.j2` prompt，让 LLM 推荐图表类型与字段，
再转换为前端可直接渲染的 ECharts option。
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
        question=state.get("user_query", ""),
        sql=state.get("validated_sql") or "",
        columns=list(rows[0].keys()) if rows else [],
        sample_rows=rows[:5],
    )

    msg = await llm.ainvoke(prompt_text)
    recommendation = _parse_json(_extract_text(msg))
    spec = _build_echarts_option(recommendation, rows)
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


def _build_echarts_option(
    recommendation: dict[str, Any] | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not recommendation or not rows:
        return None

    chart_type = str(recommendation.get("chart_type") or "table").lower()
    if chart_type == "table":
        return None

    x_field = _field_name(recommendation.get("x_field"))
    y_fields = _field_names(recommendation.get("y_field"))
    title = str(recommendation.get("title") or "查询结果")
    reason = str(recommendation.get("reason") or "")

    if chart_type == "pie":
        name_field = x_field or _first_non_numeric_field(rows) or next(iter(rows[0]))
        value_field = (
            y_fields[0]
            if y_fields
            else _first_numeric_field(rows, exclude={name_field})
        )
        if not value_field:
            return None
        return {
            "title": _title_option(title, reason, left="center"),
            "tooltip": {"trigger": "item"},
            "legend": {"bottom": 4, "type": "scroll"},
            "series": [
                {
                    "type": "pie",
                    "radius": "60%",
                    "center": ["50%", "54%"],
                    "data": [
                        {
                            "name": str(row.get(name_field)),
                            "value": _number_or_raw(row.get(value_field)),
                        }
                        for row in rows
                    ],
                }
            ],
        }

    if not x_field:
        x_field = _first_non_numeric_field(rows) or next(iter(rows[0]))
    if not y_fields:
        fallback = _first_numeric_field(rows, exclude={x_field})
        if fallback:
            y_fields = [fallback]
    if not y_fields:
        return None

    series_type = (
        "scatter" if chart_type == "scatter" else ("line" if chart_type == "line" else "bar")
    )
    x_data = [row.get(x_field) for row in rows]
    series = [
        {
            "name": field,
            "type": series_type,
            "smooth": series_type == "line",
            "data": [_number_or_raw(row.get(field)) for row in rows],
        }
        for field in y_fields
    ]
    return {
        "title": _title_option(title, reason),
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 64, "left": "center", "type": "scroll", "itemGap": 20},
        "grid": {
            "left": 48,
            "right": 24,
            "top": 120,
            "bottom": 48,
            "containLabel": True,
        },
        "xAxis": {"type": "category", "data": x_data},
        "yAxis": {"type": "value"},
        "series": series,
    }


def _title_option(title: str, reason: str, *, left: str = "left") -> dict[str, Any]:
    return {
        "text": title,
        "subtext": reason,
        "left": left,
        "top": 0,
        "itemGap": 8,
        "textStyle": {"fontSize": 16, "fontWeight": 600, "color": "#1f2937"},
        "subtextStyle": {"fontSize": 12, "color": "#6b7280", "lineHeight": 18},
    }


def _field_name(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _field_names(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return []


def _number_or_raw(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _first_numeric_field(rows: list[dict[str, Any]], *, exclude: set[str]) -> str | None:
    for key in rows[0]:
        if key in exclude:
            continue
        if all(_is_numericish(row.get(key)) for row in rows):
            return key
    return None


def _first_non_numeric_field(rows: list[dict[str, Any]]) -> str | None:
    for key in rows[0]:
        if not all(_is_numericish(row.get(key)) for row in rows):
            return key
    return None


def _is_numericish(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False
