"""STE-22：sql_safety.schema_whitelist 单测。

策略：
- 准备 known_tables / known_columns 两个 fixture 集合（小写）。
- 每条用例构造一段已 parse 过的 AST，断言 check_table_columns 行为。
"""

from __future__ import annotations

import pytest

from app.sql_safety import UnregisteredTableError, schema_whitelist
from app.sql_safety import validator


@pytest.fixture()
def known_tables() -> set[tuple[str, str]]:
    return {
        ("public", "orders"),
        ("public", "products"),
        ("public", "users"),
    }


@pytest.fixture()
def known_columns() -> dict[tuple[str, str], set[str]]:
    return {
        ("public", "orders"): {"id", "amount", "tenant_id", "product_id", "created_at"},
        ("public", "products"): {"id", "name", "tenant_id"},
        ("public", "users"): {"id", "email", "tenant_id"},
    }


# ---- table 白名单 ----


def test_known_table_passes(known_tables, known_columns) -> None:
    ast = validator.parse_safe("SELECT id FROM public.orders")
    schema_whitelist.check_table_columns(
        ast, known_tables=known_tables, known_columns=known_columns
    )


def test_unknown_table_rejected(known_tables, known_columns) -> None:
    ast = validator.parse_safe("SELECT * FROM public.evil_table")
    with pytest.raises(UnregisteredTableError):
        schema_whitelist.check_table_columns(
            ast, known_tables=known_tables, known_columns=known_columns
        )


def test_default_schema_is_public(known_tables, known_columns) -> None:
    """没写 schema 限定时按 `public` 兜底。"""
    ast = validator.parse_safe("SELECT id FROM orders")
    schema_whitelist.check_table_columns(
        ast, known_tables=known_tables, known_columns=known_columns
    )


def test_other_schema_rejected(known_tables, known_columns) -> None:
    ast = validator.parse_safe("SELECT * FROM secret.internal_table")
    with pytest.raises(UnregisteredTableError):
        schema_whitelist.check_table_columns(
            ast, known_tables=known_tables, known_columns=known_columns
        )


def test_join_with_one_unknown_table_rejected(
    known_tables, known_columns
) -> None:
    sql = "SELECT * FROM orders o JOIN evil_table e ON o.id = e.x"
    ast = validator.parse_safe(sql)
    with pytest.raises(UnregisteredTableError):
        schema_whitelist.check_table_columns(
            ast, known_tables=known_tables, known_columns=known_columns
        )


def test_subquery_with_unknown_table_rejected(known_tables, known_columns) -> None:
    sql = "SELECT * FROM orders WHERE id IN (SELECT id FROM secret_table)"
    ast = validator.parse_safe(sql)
    with pytest.raises(UnregisteredTableError):
        schema_whitelist.check_table_columns(
            ast, known_tables=known_tables, known_columns=known_columns
        )


def test_cte_with_unknown_table_rejected(known_tables, known_columns) -> None:
    sql = "WITH t AS (SELECT * FROM secret) SELECT * FROM t"
    ast = validator.parse_safe(sql)
    with pytest.raises(UnregisteredTableError):
        schema_whitelist.check_table_columns(
            ast, known_tables=known_tables, known_columns=known_columns
        )


# ---- 列宽松校验 ----


def test_unknown_column_rejected(known_tables, known_columns) -> None:
    """所有登记表都没有这一列名 → 拒绝。"""
    ast = validator.parse_safe("SELECT bogus_secret_field FROM orders")
    with pytest.raises(UnregisteredTableError):
        schema_whitelist.check_table_columns(
            ast, known_tables=known_tables, known_columns=known_columns
        )


def test_column_known_in_some_registered_table_passes(
    known_tables, known_columns
) -> None:
    """`amount` 出现在 orders 列表里 → 即使 SQL 里没限定 o.amount，也允许。"""
    ast = validator.parse_safe("SELECT amount FROM orders")
    schema_whitelist.check_table_columns(
        ast, known_tables=known_tables, known_columns=known_columns
    )


def test_column_with_table_prefix_passes(known_tables, known_columns) -> None:
    ast = validator.parse_safe("SELECT o.amount FROM orders o")
    schema_whitelist.check_table_columns(
        ast, known_tables=known_tables, known_columns=known_columns
    )


def test_star_column_allowed(known_tables, known_columns) -> None:
    """`*` 不应被当作未登记列；具体列由 PG 执行时决定。"""
    ast = validator.parse_safe("SELECT * FROM orders")
    schema_whitelist.check_table_columns(
        ast, known_tables=known_tables, known_columns=known_columns
    )
