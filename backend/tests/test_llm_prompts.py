"""STE-20：Prompt 模板渲染单测。

只验「契约级」断言：
- 模板存在且可加载
- 关键变量被注入到输出
- 未知模板报错（jinja2.TemplateNotFound）

不固化具体 prompt 文案，避免 prompt 文案微调时测试一起改。
"""

from __future__ import annotations

import pytest

from app.llm import render_prompt

# ---- sql_gen ----


def test_render_sql_gen_includes_question() -> None:
    out = render_prompt(
        "sql_gen",
        question="2024 年华东大区销售额前 10 的产品",
        schema_cards=[
            {
                "table": "orders",
                "columns": ["id", "amount", "region", "created_at"],
                "description": "订单事实表（每行一笔订单）",
            },
        ],
        tenant_id="tenant-x",
        max_rows=200,
    )
    assert "2024 年华东大区销售额前 10 的产品" in out
    assert "orders" in out


def test_render_sql_gen_emphasizes_tenant_isolation() -> None:
    """生成的 prompt 必须把租户隔离作为硬约束传给模型。"""
    out = render_prompt(
        "sql_gen",
        question="任意",
        schema_cards=[],
        tenant_id="tenant-x",
        max_rows=200,
    )
    assert "tenant-x" in out


# ---- chart_recommend ----


def test_render_chart_recommend_includes_question_and_columns() -> None:
    out = render_prompt(
        "chart_recommend",
        question="按月统计销售额趋势",
        sql="SELECT month, sum(amount) AS total FROM orders GROUP BY month",
        columns=["month", "total"],
        sample_rows=[
            {"month": "2024-01", "total": 12345},
            {"month": "2024-02", "total": 23456},
        ],
    )
    assert "按月统计销售额趋势" in out
    assert "month" in out
    assert "total" in out


# ---- summarize ----


def test_render_summarize_includes_question() -> None:
    out = render_prompt(
        "summarize",
        question="哪些产品最畅销？",
        stats={"total_rows": 10, "top_value": 5000, "top_label": "Widget A"},
    )
    assert "哪些产品最畅销" in out


# ---- 错误路径 ----


def test_render_unknown_template_raises() -> None:
    """未知模板名应抛 jinja2.TemplateNotFound（让上层能区分配置错误 vs 业务错）。"""
    import jinja2  # 局部 import 避免污染顶部 import 排序

    with pytest.raises(jinja2.TemplateNotFound):
        render_prompt("nonexistent_template_xyz", foo="bar")
