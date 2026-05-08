"""STE-22：sql_safety.validator 单测。

策略：
- 直接 parse SQL → 调对应检查器；纯字符串/AST 操作，零外部依赖。
- 每条恶意 SQL 都覆盖一个具体异常子类。
"""

from __future__ import annotations

import pytest
import sqlglot
from sqlglot import expressions as exp

from app.sql_safety import (
    ForbiddenFunctionError,
    ForbiddenStatementError,
    MultiStatementError,
    SqlSyntaxError,
    SystemSchemaError,
)
from app.sql_safety import validator


# ---- parse_safe ----


def test_parse_safe_returns_single_expression() -> None:
    ast = validator.parse_safe("SELECT 1")
    assert isinstance(ast, exp.Expression)


def test_parse_safe_rejects_multiple_statements() -> None:
    with pytest.raises(MultiStatementError):
        validator.parse_safe("SELECT 1; SELECT 2")


def test_parse_safe_rejects_select_then_drop() -> None:
    with pytest.raises(MultiStatementError):
        validator.parse_safe("SELECT 1; DROP TABLE users")


def test_parse_safe_handles_trailing_semicolon() -> None:
    """单条语句末尾有 `;` 应被视为单条，而不是多条。"""
    ast = validator.parse_safe("SELECT 1;")
    assert isinstance(ast, exp.Expression)


def test_parse_safe_rejects_empty_sql() -> None:
    with pytest.raises(SqlSyntaxError):
        validator.parse_safe("   ")


def test_parse_safe_rejects_garbage() -> None:
    with pytest.raises(SqlSyntaxError):
        validator.parse_safe("not a valid SQL at all !@#$%^")


# ---- validate_select_only ----


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT * FROM orders WHERE amount > 0",
        "SELECT a FROM x UNION SELECT a FROM y",
        "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
        "WITH a AS (SELECT 1), b AS (SELECT 2) SELECT * FROM a, b",
    ],
)
def test_validate_select_only_allows_read(sql: str) -> None:
    ast = validator.parse_safe(sql)
    validator.validate_select_only(ast)  # not raises


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO orders (id) VALUES (1)",
        "UPDATE orders SET amount = 0",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "TRUNCATE orders",
        "ALTER TABLE orders DROP COLUMN amount",
        "CREATE TABLE evil (id int)",
        "GRANT ALL ON orders TO public",
    ],
)
def test_validate_select_only_rejects_writes(sql: str) -> None:
    ast = validator.parse_safe(sql)
    with pytest.raises(ForbiddenStatementError):
        validator.validate_select_only(ast)


# ---- check_system_schemas ----


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM information_schema.columns",
        "SELECT * FROM pg_tables",
        "SELECT * FROM pg_user",
    ],
)
def test_check_system_schemas_rejects_system(sql: str) -> None:
    ast = validator.parse_safe(sql)
    with pytest.raises(SystemSchemaError):
        validator.check_system_schemas(ast)


def test_check_system_schemas_allows_user_table() -> None:
    ast = validator.parse_safe("SELECT * FROM public.orders")
    validator.check_system_schemas(ast)


# ---- check_forbidden_functions ----


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT lo_import('/etc/passwd')",
        "SELECT pg_ls_dir('/')",
        "SELECT * FROM dblink('host=evil.com', 'SELECT 1') AS t(x int)",
    ],
)
def test_check_forbidden_functions_rejects(sql: str) -> None:
    ast = validator.parse_safe(sql)
    with pytest.raises(ForbiddenFunctionError):
        validator.check_forbidden_functions(ast)


def test_check_forbidden_functions_allows_safe() -> None:
    ast = validator.parse_safe(
        "SELECT count(*), sum(amount), avg(amount) FROM public.orders"
    )
    validator.check_forbidden_functions(ast)


# ---- enforce_limit ----


def test_enforce_limit_injects_when_missing() -> None:
    ast = validator.parse_safe("SELECT * FROM public.orders")
    out = validator.enforce_limit(ast, max_rows=200)
    rendered = out.sql(dialect="postgres")
    assert "LIMIT 200" in rendered.upper()


def test_enforce_limit_truncates_when_too_large() -> None:
    ast = validator.parse_safe("SELECT * FROM public.orders LIMIT 99999")
    out = validator.enforce_limit(ast, max_rows=200)
    rendered = out.sql(dialect="postgres")
    assert "LIMIT 200" in rendered.upper()
    assert "99999" not in rendered


def test_enforce_limit_keeps_smaller_user_limit() -> None:
    ast = validator.parse_safe("SELECT * FROM public.orders LIMIT 50")
    out = validator.enforce_limit(ast, max_rows=200)
    rendered = out.sql(dialect="postgres")
    assert "LIMIT 50" in rendered.upper()


def test_enforce_limit_idempotent() -> None:
    """同一 AST 多次注入应稳定（不重复加 LIMIT）。"""
    ast = validator.parse_safe("SELECT * FROM public.orders")
    once = validator.enforce_limit(ast, max_rows=200)
    twice = validator.enforce_limit(once, max_rows=200)
    rendered = twice.sql(dialect="postgres")
    # 只能出现一次 LIMIT
    assert rendered.upper().count("LIMIT") == 1


def test_parse_safe_uses_postgres_dialect() -> None:
    """显式确认 PG 方言：`::int` cast 形式应被解析。"""
    ast = validator.parse_safe("SELECT '1'::int")
    # 不抛异常即可；确认确实是 PG 方言而不是 default mysql
    rendered = ast.sql(dialect="postgres")
    assert "CAST" in rendered.upper() or "::" in rendered


def test_check_system_schemas_via_sqlglot_parsed_directly() -> None:
    """直接用 sqlglot 解析过的 AST 也能被 check 函数处理（不强制依赖 parse_safe）。"""
    ast = sqlglot.parse_one("SELECT 1", dialect="postgres")
    validator.check_system_schemas(ast)
    validator.check_forbidden_functions(ast)
