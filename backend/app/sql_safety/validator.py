"""STE-22：SQL AST 校验器。

模块职责：
- `parse_safe`：sqlglot 解析；多语句、空 SQL、解析错误 → SqlSafetyError 子类。
- `validate_select_only`：顶层只能是 SELECT / Union（含 WITH ... SELECT，因 sqlglot
  会把 WITH 子句作为 Select 的 args，不会单独成顶层 With 节点）。
- `check_system_schemas`：禁用 `pg_catalog` / `pg_toast` / `information_schema`
  以及 `pg_*` 系统表前缀。
- `check_forbidden_functions`：危险函数全部走 sqlglot 的 `Anonymous`
  （内置 PG 函数会被解析成具体子类，因此遍历 Anonymous 即可命中外部/可疑函数）。
- `enforce_limit`：无 LIMIT 注入；超限截断；保留小于上限的用户值。

设计要点：
- 只接受 PG 方言（postgres）。其它方言的攻击面会变。
- 所有检查器接受同一棵 AST（不重复 parse），由 service 一次性 parse 后串接。
- 旁路修改（enforce_limit）原地改 AST 并返回，便于链式调用。
"""

from __future__ import annotations

from typing import Final

import sqlglot
from sqlglot import expressions as exp
from sqlglot.errors import ParseError

from app.sql_safety.errors import (
    ForbiddenFunctionError,
    ForbiddenStatementError,
    MultiStatementError,
    SqlSyntaxError,
    SystemSchemaError,
)

_DIALECT: Final[str] = "postgres"

_SYSTEM_SCHEMAS: Final[frozenset[str]] = frozenset(
    {"pg_catalog", "pg_toast", "information_schema"}
)
_SYSTEM_TABLE_PREFIXES: Final[tuple[str, ...]] = ("pg_",)

# 危险函数黑名单（小写）。所有非内置 PG 函数会被 sqlglot 解析成 Anonymous，
# 因此只要遍历 Anonymous 节点的 name 与此集合比对即可。
_FORBIDDEN_FUNCS: Final[frozenset[str]] = frozenset(
    {
        # 文件 / 系统访问
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_stat_file",
        # 大对象写入
        "lo_import",
        "lo_export",
        # 跨库连接
        "dblink",
        "dblink_exec",
        "dblink_connect",
        # 任意命令
        "pg_terminate_backend",
        "pg_cancel_backend",
        # 配置读写（避免读敏感配置）
        "current_setting",
        "set_config",
    }
)


def parse_safe(sql: str) -> exp.Expression:
    """解析单条 SQL；多语句、空 SQL、语法错误一律抛 SqlSafetyError 子类。

    注意：sqlglot 在 PG 方言下会把 trailing `;` 当作单语句分隔符忽略，
    因此 `SELECT 1;` 仍是单条；`SELECT 1; SELECT 2` 才是多条。
    """
    if not sql or not sql.strip():
        raise SqlSyntaxError("Empty SQL")

    try:
        statements = sqlglot.parse(sql, dialect=_DIALECT)
    except ParseError as e:
        raise SqlSyntaxError(f"SQL 解析失败: {e}") from e

    non_empty = [s for s in statements if s is not None]
    if not non_empty:
        raise SqlSyntaxError("Empty SQL after parsing")
    if len(non_empty) > 1:
        raise MultiStatementError(
            f"Multiple statements detected: {len(non_empty)}"
        )

    return non_empty[0]


def validate_select_only(ast: exp.Expression) -> None:
    """顶层只允许：
    - exp.Select（含 WITH ... SELECT，因为 sqlglot 把 WITH 子句作为 Select 的 args）
    - exp.Union（UNION / EXCEPT / INTERSECT）
    """
    if isinstance(ast, (exp.Select, exp.Union)):
        return
    raise ForbiddenStatementError(
        f"Only SELECT / CTE / UNION allowed; got {type(ast).__name__}"
    )


def check_system_schemas(ast: exp.Expression) -> None:
    """禁用系统 schema 与 pg_* 系统表。"""
    for table in ast.find_all(exp.Table):
        schema = (table.db or "").lower()
        name = (table.name or "").lower()
        if schema in _SYSTEM_SCHEMAS:
            raise SystemSchemaError(f"System schema not allowed: {schema}")
        if not schema and name.startswith(_SYSTEM_TABLE_PREFIXES):
            raise SystemSchemaError(f"System table not allowed: {name}")


def check_forbidden_functions(ast: exp.Expression) -> None:
    """禁用危险函数调用（基于 Anonymous 节点）。

    注意：内置 PG 函数（count/sum/avg/...）在 sqlglot 中是具体子类，
    本检查只命中 Anonymous，因此白名单等价于「PG 内置函数全允许」。
    """
    for node in ast.find_all(exp.Anonymous):
        name = (node.name or "").lower() if isinstance(node.name, str) else ""
        if name in _FORBIDDEN_FUNCS:
            raise ForbiddenFunctionError(f"Forbidden function: {name}")


def enforce_limit(ast: exp.Expression, *, max_rows: int) -> exp.Expression:
    """约束 LIMIT 上限。

    - 无 LIMIT → 注入 `LIMIT max_rows`
    - 有 LIMIT 但 `n > max_rows` → 截断到 `max_rows`
    - 有 LIMIT 且 `n <= max_rows` → 保留
    - LIMIT 不是整数字面量（如 `LIMIT $1`）→ 保守保留，不改写
    """
    if max_rows <= 0:
        raise ValueError("max_rows must be positive")

    limit = ast.args.get("limit")
    if limit is None:
        ast.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
        return ast

    n_node = limit.expression
    if isinstance(n_node, exp.Literal) and not n_node.is_string:
        try:
            n = int(n_node.this)
        except (TypeError, ValueError):
            return ast
        if n > max_rows:
            limit.set("expression", exp.Literal.number(max_rows))

    return ast
