"""app.sql_string：分号粘连的重复 SQL 折叠与正文去 SQL 复述。"""

from __future__ import annotations

from app.sql_string import (
    dedupe_semicolon_sql_clauses,
    sanitize_assistant_summary_text,
)


def test_dedupe_duplicate_select_pair() -> None:
    one = (
        "SELECT EXTRACT(MONTH FROM order_date) AS month, SUM(amount) AS x "
        "FROM biz.demo_orders WHERE tenant_id = :tid LIMIT 5000"
    )
    doubled = f"{one};{one}"
    assert dedupe_semicolon_sql_clauses(doubled) == one


def test_sanitize_user_reported_blob() -> None:
    """模型把两条相同 SQL + 两段中文粘在一起时的收口效果。"""
    q = (
        "SELECT a FROM t WHERE x LIMIT 5000;"
        "SELECT a FROM t WHERE x LIMIT 5000;"
        "数据表中缺少月份字段，无法按月汇总。"
        "数据表中缺少月份字段，无法按月汇总。"
    )
    out = sanitize_assistant_summary_text(q)
    assert "SELECT" not in out.upper()
    assert "缺少月份字段" in out
    assert out.count("缺少月份字段") == 1


def test_sanitize_keeps_decimal_points() -> None:
    out = sanitize_assistant_summary_text(
        "1月销售额为299.00元。1月销售额为299.00元。"
    )
    assert out == "1月销售额为299.00元。"
