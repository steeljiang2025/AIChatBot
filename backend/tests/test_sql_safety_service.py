"""STE-22：sql_safety_service.sanitize_sql 端到端单测。

策略：把 sanitize_sql 当一个 black-box，覆盖：
- 合法 SQL → 返回净化后 SQL（含 LIMIT + tenant_id = :tid）
- 多语句 / 写操作 / 系统 schema / 危险函数 / 未登记表 / 未登记列 → 抛对应异常
- 多租户表自动注入 tenant_id；非多租户表不注入
- 已含 tenant_id 谓词时不重复注入
- 自动 LIMIT 上限对齐 max_rows
"""

from __future__ import annotations

import pytest

from app.services.sql_safety_service import sanitize_sql
from app.sql_safety import (
    ForbiddenFunctionError,
    ForbiddenStatementError,
    MultiStatementError,
    SqlSafetyError,
    SystemSchemaError,
    UnregisteredTableError,
)


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
        ("public", "orders"): {
            "id",
            "amount",
            "tenant_id",
            "product_id",
            "created_at",
            "user_id",
        },
        ("public", "products"): {"id", "name", "price"},
        ("public", "users"): {"id", "email", "tenant_id"},
    }


@pytest.fixture()
def scoped() -> set[tuple[str, str]]:
    """orders / users 多租户；products 不是。"""
    return {("public", "orders"), ("public", "users")}


def _kwargs(known_tables, known_columns, scoped):
    return {
        "known_tables": known_tables,
        "known_columns": known_columns,
        "tenant_scoped_tables": scoped,
        "max_rows": 200,
    }


# ============ 合法 SQL ============


def test_basic_select_gets_tenant_and_limit(
    known_tables, known_columns, scoped
) -> None:
    out = sanitize_sql(
        "SELECT id, amount FROM orders WHERE amount > 0",
        **_kwargs(known_tables, known_columns, scoped),
    )
    upper = out.upper()
    assert "TENANT_ID = :TID" in upper
    assert "LIMIT 200" in upper


def test_already_safe_query_idempotent(
    known_tables, known_columns, scoped
) -> None:
    out = sanitize_sql(
        "SELECT id FROM orders WHERE tenant_id = :tid LIMIT 50",
        **_kwargs(known_tables, known_columns, scoped),
    )
    upper = out.upper()
    assert upper.count("TENANT_ID = :TID") == 1
    assert "LIMIT 50" in upper


def test_non_scoped_table_no_tenant_inject(
    known_tables, known_columns, scoped
) -> None:
    """products 不是多租户表，不应注入 tenant_id。"""
    out = sanitize_sql(
        "SELECT id, name FROM products",
        **_kwargs(known_tables, known_columns, scoped),
    )
    assert "tenant_id" not in out.lower()
    assert "LIMIT 200" in out.upper()


def test_join_inject_tenant(known_tables, known_columns, scoped) -> None:
    """JOIN 多租户表：tenant_id 应至少注入一次。"""
    out = sanitize_sql(
        "SELECT o.id FROM orders o JOIN users u ON o.user_id = u.id",
        **_kwargs(known_tables, known_columns, scoped),
    )
    assert "tenant_id = :tid" in out.lower()


def test_union_inject_both_sides(known_tables, known_columns, scoped) -> None:
    out = sanitize_sql(
        "SELECT id FROM orders UNION ALL SELECT id FROM users",
        **_kwargs(known_tables, known_columns, scoped),
    )
    assert out.lower().count("tenant_id = :tid") == 2


def test_cte_inject(known_tables, known_columns, scoped) -> None:
    out = sanitize_sql(
        "WITH t AS (SELECT id FROM orders) SELECT * FROM t",
        **_kwargs(known_tables, known_columns, scoped),
    )
    assert "tenant_id = :tid" in out.lower()


# ============ 恶意拦截 ============


def test_multiple_statements_blocked(
    known_tables, known_columns, scoped
) -> None:
    with pytest.raises(MultiStatementError):
        sanitize_sql(
            "SELECT 1; DROP TABLE orders",
            **_kwargs(known_tables, known_columns, scoped),
        )


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO orders (id) VALUES (1)",
        "UPDATE orders SET amount = 0",
        "DELETE FROM orders",
        "TRUNCATE orders",
        "DROP TABLE orders",
    ],
)
def test_writes_blocked(sql, known_tables, known_columns, scoped) -> None:
    with pytest.raises(ForbiddenStatementError):
        sanitize_sql(sql, **_kwargs(known_tables, known_columns, scoped))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM pg_tables",
        "SELECT * FROM pg_catalog.pg_user",
    ],
)
def test_system_schema_blocked(
    sql, known_tables, known_columns, scoped
) -> None:
    with pytest.raises(SystemSchemaError):
        sanitize_sql(sql, **_kwargs(known_tables, known_columns, scoped))


def test_forbidden_function_blocked(
    known_tables, known_columns, scoped
) -> None:
    with pytest.raises(ForbiddenFunctionError):
        sanitize_sql(
            "SELECT pg_read_file('/etc/passwd')",
            **_kwargs(known_tables, known_columns, scoped),
        )


def test_unregistered_table_blocked(
    known_tables, known_columns, scoped
) -> None:
    with pytest.raises(UnregisteredTableError):
        sanitize_sql(
            "SELECT * FROM secret_audit_log",
            **_kwargs(known_tables, known_columns, scoped),
        )


def test_unregistered_column_blocked(
    known_tables, known_columns, scoped
) -> None:
    with pytest.raises(UnregisteredTableError):
        sanitize_sql(
            "SELECT bogus_column FROM orders",
            **_kwargs(known_tables, known_columns, scoped),
        )


def test_subquery_unknown_table_blocked(
    known_tables, known_columns, scoped
) -> None:
    with pytest.raises(UnregisteredTableError):
        sanitize_sql(
            "SELECT id FROM orders WHERE id IN (SELECT id FROM secrets)",
            **_kwargs(known_tables, known_columns, scoped),
        )


# ============ 异常树根类 ============


def test_all_errors_inherit_sql_safety_error(
    known_tables, known_columns, scoped
) -> None:
    """业务侧 except SqlSafetyError 应能捕获所有子类。"""
    with pytest.raises(SqlSafetyError):
        sanitize_sql(
            "DROP TABLE orders",
            **_kwargs(known_tables, known_columns, scoped),
        )


# ============ LIMIT 行为 ============


def test_user_limit_kept_when_smaller(
    known_tables, known_columns, scoped
) -> None:
    out = sanitize_sql(
        "SELECT id FROM orders LIMIT 10",
        **_kwargs(known_tables, known_columns, scoped),
    )
    assert "LIMIT 10" in out.upper()


def test_user_limit_truncated_when_too_large(
    known_tables, known_columns, scoped
) -> None:
    out = sanitize_sql(
        "SELECT id FROM orders LIMIT 99999",
        **_kwargs(known_tables, known_columns, scoped),
    )
    assert "LIMIT 200" in out.upper()
    assert "99999" not in out
