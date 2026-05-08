"""STE-22：SQL 安全编排（占位）。

`sanitize_sql` 是对外的唯一入口，把 5 个子模块串成一条流水线：

    parse_safe
      → validate_select_only
      → check_system_schemas
      → check_forbidden_functions
      → schema_whitelist.check_table_columns
      → tenant_guard.inject_tenant_guard
      → validator.enforce_limit
      → 复检：sql() → parse → tenant_guard.reverify

输出：可直接被 sql_exec 执行的 SQL 字符串（含 `:tid` 占位符），
调用方负责 `bind(tid=tenant_id)` 注入实际 UUID。
"""

from __future__ import annotations


def sanitize_sql(
    sql: str,
    *,
    known_tables: set[tuple[str, str]],
    known_columns: dict[tuple[str, str], set[str]],
    tenant_scoped_tables: set[tuple[str, str]],
    max_rows: int,
) -> str:
    """SQL 安全净化流水线。

    Args:
        sql: LLM 生成的原始 SQL。
        known_tables: 已登记表集合（schema 小写 + table 小写）。
        known_columns: 已登记列映射 `(schema, table) → {col, ...}`。
        tenant_scoped_tables: 必须强制 tenant_id 隔离的表子集，⊆ known_tables。
        max_rows: 自动 LIMIT 上限（来自 settings.sql_max_rows）。

    Returns:
        可执行的 PG SQL，含 `:tid` 占位符。

    Raises:
        SqlSafetyError 子类之一。
    """
    raise NotImplementedError
