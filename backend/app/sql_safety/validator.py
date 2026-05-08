"""STE-22：SQL AST 校验器（占位）。

职责（commit 2 实现）：
- `parse_safe(sql)`：sqlglot 解析；多语句、空 SQL、解析错误一律拒绝。
- `validate_select_only(ast)`：顶层只能是 SELECT / Union / WITH (CTE) 包 SELECT。
- `check_system_schemas(ast)`：禁用 pg_catalog / pg_toast / information_schema 引用，
  以及 `pg_*` 系统表前缀。
- `check_forbidden_functions(ast)`：禁用 `pg_read_file` / `lo_import` / `dblink` 等。
- `enforce_limit(ast, max_rows)`：无 LIMIT 时注入；有 LIMIT 但超过 `max_rows` 时截断。

约束：
- 所有 API 接受 `sqlglot.exp.Expression` 而不是 SQL 字符串，让 service 层保持
  「只 parse 一次 + 多次 visit」的高效模式；service 层负责 parse_safe 一次后
  把 AST 串到各检查器。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlglot.expressions as exp


def parse_safe(sql: str):
    """sqlglot.parse(sql, dialect='postgres') 包装。

    Returns: 单条 `exp.Expression` 树。
    Raises:
        SqlSyntaxError: 语法错误 / 空 SQL。
        MultiStatementError: 多语句。
    """
    raise NotImplementedError


def validate_select_only(ast: exp.Expression) -> None:
    """顶层必须是 SELECT / Union / WITH (CTE)；其它一律拒绝。

    Raises: ForbiddenStatementError
    """
    raise NotImplementedError


def check_system_schemas(ast: exp.Expression) -> None:
    """禁用系统 schema / pg_* 系统表。

    Raises: SystemSchemaError
    """
    raise NotImplementedError


def check_forbidden_functions(ast: exp.Expression) -> None:
    """禁用危险函数调用。

    Raises: ForbiddenFunctionError
    """
    raise NotImplementedError


def enforce_limit(ast: exp.Expression, *, max_rows: int) -> exp.Expression:
    """约束 LIMIT：

    - 无 LIMIT 子句 → 注入 `LIMIT max_rows`。
    - 有 LIMIT 但 `n > max_rows` → 截断到 `max_rows`。
    - 有 LIMIT 且 `n <= max_rows` → 保留原值。

    Returns: 可能被修改过的同一棵 AST（原地修改）。
    """
    raise NotImplementedError
