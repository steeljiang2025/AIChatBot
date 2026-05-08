"""STE-22：schema 白名单检查。

策略（用户决策：未登记表/列直接拒绝）：
- 表：`(schema or 'public', name)` 必须在 known_tables 内（小写）。
  CTE 别名通过「`SELECT` 节点的 `with` 字段中声明的 alias 集」豁免。
- 列：宽松版列名级检查 — 只要列名出现在「所有登记表的列集合并集 + CTE 列集合」内即放行。
  完全严格的列归属判断需要 `sqlglot.optimizer.qualify_columns`，留给 STE-23 集成。
- `*`（star）不被视为列引用，跳过。
"""

from __future__ import annotations

from sqlglot import expressions as exp

from app.sql_safety.errors import UnregisteredTableError


def _collect_cte_aliases(ast: exp.Expression) -> set[str]:
    """收集所有 CTE 别名（小写）。

    sqlglot 会把 `WITH a AS (...), b AS (...) SELECT ...` 中的 a/b
    作为 `Select.args['with'].expressions` 中的 CTE 节点。
    """
    aliases: set[str] = set()
    for cte in ast.find_all(exp.CTE):
        alias = cte.alias_or_name
        if alias:
            aliases.add(alias.lower())
    return aliases


def check_table_columns(
    ast: exp.Expression,
    *,
    known_tables: set[tuple[str, str]],
    known_columns: dict[tuple[str, str], set[str]],
) -> None:
    """白名单校验。

    Raises:
        UnregisteredTableError: 任何引用了未登记的表 / 列。
    """
    cte_aliases = _collect_cte_aliases(ast)

    # 1) 表
    for table in ast.find_all(exp.Table):
        schema = (table.db or "public").lower()
        name = (table.name or "").lower()
        if not name:
            continue
        # CTE 别名（仅当未指定 schema 时）
        if not table.db and name in cte_aliases:
            continue
        if (schema, name) not in known_tables:
            raise UnregisteredTableError(
                f"Table not registered: {schema}.{name}"
            )

    # 2) 列（宽松：列名出现在已登记列集并集即可）
    all_known_cols: set[str] = set()
    for cols in known_columns.values():
        all_known_cols.update(c.lower() for c in cols)

    for col in ast.find_all(exp.Column):
        col_name = (col.name or "").lower()
        if not col_name or col_name == "*":
            continue
        # 仅当该列没限定到 CTE alias 时才检查；CTE 内部列由 CTE 内的 select 自身递归校验
        if col.table:
            t_alias = col.table.lower()
            if t_alias in cte_aliases:
                continue
        if col_name not in all_known_cols:
            raise UnregisteredTableError(
                f"Column not registered: {col_name}"
            )
