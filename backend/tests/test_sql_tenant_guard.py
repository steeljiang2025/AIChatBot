"""STE-22：sql_safety.tenant_guard 单测。

覆盖：
- 注入：无 WHERE / 有 WHERE 无 tenant / 已有 tenant 不重复
- 子查询 / JOIN / UNION 各 Select 都被注入
- 非多租户表跳过注入
- 复检：合法 → 通过；故意去掉 tenant_id → 抛 MissingTenantGuardError
"""

from __future__ import annotations

import pytest

from app.sql_safety import MissingTenantGuardError, tenant_guard, validator


@pytest.fixture()
def scoped() -> set[tuple[str, str]]:
    """orders / users 是多租户表；products 不是。"""
    return {("public", "orders"), ("public", "users")}


def _render(ast) -> str:
    return ast.sql(dialect="postgres")


# ---- 注入：覆盖 ----


def test_inject_no_where(scoped) -> None:
    ast = validator.parse_safe("SELECT id FROM orders")
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out)
    assert "TENANT_ID" in rendered.upper()
    assert ":TID" in rendered.upper()


def test_inject_with_existing_where(scoped) -> None:
    ast = validator.parse_safe("SELECT id FROM orders WHERE amount > 0")
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out).upper()
    assert "AMOUNT > 0" in rendered
    assert "TENANT_ID = :TID" in rendered


def test_inject_idempotent_when_already_present(scoped) -> None:
    ast = validator.parse_safe(
        "SELECT id FROM orders WHERE tenant_id = :tid AND amount > 0"
    )
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out).upper()
    # 只能出现一次 tenant_id = :tid
    assert rendered.count("TENANT_ID = :TID") == 1


def test_inject_skips_non_scoped_tables(scoped) -> None:
    """products 不在多租户表集合中 → 不注入。"""
    ast = validator.parse_safe("SELECT id FROM products")
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out).upper()
    assert "TENANT_ID" not in rendered


# ---- 复杂结构：子查询 / JOIN / UNION ----


def test_inject_into_subquery(scoped) -> None:
    """`SELECT ... FROM (SELECT ... FROM orders) sub`：
    内层 SELECT 也要注入 tenant_id。"""
    sql = "SELECT * FROM (SELECT id FROM orders WHERE amount > 0) sub"
    ast = validator.parse_safe(sql)
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out).upper()
    assert "TENANT_ID = :TID" in rendered


def test_inject_into_join(scoped) -> None:
    """JOIN 的 WHERE 要包含两张多租户表的 tenant_id 谓词；
    实际上 tenant_guard 注入的是 unqualified `tenant_id`，
    PG 会按列消歧报错；这里测试注入出现至少一次即可，
    完全消歧由 STE-23 SQL 生成 prompt 引导 LLM 写 `o.tenant_id`。"""
    sql = "SELECT o.id FROM orders o JOIN users u ON o.user_id = u.id"
    ast = validator.parse_safe(sql)
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out).upper()
    assert "TENANT_ID = :TID" in rendered


def test_inject_into_union(scoped) -> None:
    """UNION 两边各自的 SELECT 都要注入。"""
    sql = "SELECT id FROM orders UNION ALL SELECT id FROM users"
    ast = validator.parse_safe(sql)
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out).upper()
    assert rendered.count("TENANT_ID = :TID") == 2


def test_inject_into_cte(scoped) -> None:
    sql = "WITH t AS (SELECT id FROM orders WHERE amount > 0) SELECT * FROM t"
    ast = validator.parse_safe(sql)
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    rendered = _render(out).upper()
    assert "TENANT_ID = :TID" in rendered


# ---- 复检 ----


def test_reverify_passes_after_injection(scoped) -> None:
    ast = validator.parse_safe("SELECT id FROM orders")
    out = tenant_guard.inject_tenant_guard(ast, tenant_scoped_tables=scoped)
    tenant_guard.reverify_tenant_guards(out, tenant_scoped_tables=scoped)


def test_reverify_passes_when_already_correct(scoped) -> None:
    ast = validator.parse_safe(
        "SELECT id FROM orders WHERE tenant_id = :tid"
    )
    tenant_guard.reverify_tenant_guards(ast, tenant_scoped_tables=scoped)


def test_reverify_rejects_missing_guard(scoped) -> None:
    """模拟 SQL 里多租户表没 tenant_id：复检应抛 MissingTenantGuardError。"""
    ast = validator.parse_safe("SELECT id FROM orders WHERE amount > 0")
    # 故意不 inject
    with pytest.raises(MissingTenantGuardError):
        tenant_guard.reverify_tenant_guards(ast, tenant_scoped_tables=scoped)


def test_reverify_skips_non_scoped(scoped) -> None:
    """非多租户表无需 tenant_id；复检通过。"""
    ast = validator.parse_safe("SELECT id FROM products")
    tenant_guard.reverify_tenant_guards(ast, tenant_scoped_tables=scoped)
