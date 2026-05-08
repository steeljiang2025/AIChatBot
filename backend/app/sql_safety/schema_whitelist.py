"""STE-22：schema 白名单检查（占位）。

策略（用户决策：未登记表/列 → 直接拒绝）：
- 接受一份「已登记表」(schema, table) 集合 + 「已登记列」(schema, table) → set[col] 的映射。
- 遍历 AST 中所有 Table / Column，校验：
  - Table 的 `(db or 'public', name)` 必须在 known_tables。
  - Column 的 `name` 必须在某个已知表的列集合内（宽松版：不依赖 qualify）。

注：完全严格的列归属判断依赖 `sqlglot.optimizer.qualify_columns`，
该步骤集成留给 STE-23 SQL 生成节点完成（届时已知执行计划）。
本模块的列检查只做「列名至少是某个登记表的列」的宽松校验，
足以防御「LLM 幻觉出 `secret_field` 这类完全虚构列」。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlglot.expressions as exp


def check_table_columns(
    ast: exp.Expression,
    *,
    known_tables: set[tuple[str, str]],
    known_columns: dict[tuple[str, str], set[str]],
) -> None:
    """白名单校验。

    Args:
        ast: 已通过 validator 的 AST。
        known_tables: `{(schema_lower, table_lower), ...}`，所有登记的业务表。
        known_columns: `{(schema_lower, table_lower): {col_lower, ...}}`，
            供宽松列检查使用。

    Raises:
        UnregisteredTableError: 引用了未登记的表 / 列。
    """
    raise NotImplementedError
