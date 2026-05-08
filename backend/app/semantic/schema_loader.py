"""STE-21：业务库 schema 抽取。

设计要点：
- 接受任意 `AsyncEngine`（用户决策：function-level engine 注入），
  使得未来加业务库时只需在调用方传入新 engine，本模块不感知。
- 从 `information_schema.tables` LEFT JOIN `information_schema.columns` 抽，
  跳过系统 schema（pg_*, information_schema）+ 我们的内部 schema
  （meta / rag / checkpoint）。
- 返回值仅是「发现到的字面信息」，不直接入库——是否登记到 SemanticTable
  由上层 API 决定（典型流程：调 `/semantics/discover` → 用户在 UI 上勾选
  要登记的表 → 调 `/semantics/tables` 创建）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    """`information_schema.columns` 的一行投影。"""

    column_name: str
    data_type: str
    is_nullable: bool
    column_default: str | None = None


@dataclass(frozen=True, slots=True)
class TableInfo:
    """`information_schema.tables` 的一行投影 + 该表的列列表。"""

    schema_name: str
    table_name: str
    table_type: str  # BASE TABLE / VIEW / MATERIALIZED VIEW
    columns: tuple[ColumnInfo, ...] = field(default_factory=tuple)


# 内部 schema 黑名单：自身的元数据 schema 不应被业务库抽取流程「重新发现」。
_INTERNAL_SCHEMAS: frozenset[str] = frozenset(
    {
        "meta",
        "rag",
        "checkpoint",
        "pg_catalog",
        "pg_toast",
        "information_schema",
    }
)


# 行 schema：(schema, table, table_type, column, data_type, is_nullable, default)
_FetchedRow = tuple[str, str, str, str, str, bool, str | None]


# information_schema 抽取 SQL：JOIN tables × columns，只取 BASE TABLE 时
# 在 SQL 层加 t.table_type 过滤；include_schemas=None 时 SQL 里只过滤
# 内部 schema 黑名单。
# `:internal_schemas` 用 expanding bind 传 tuple，psycopg / asyncpg 都支持。
_BASE_SQL = """
SELECT
    t.table_schema,
    t.table_name,
    t.table_type,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.column_default
FROM information_schema.tables AS t
JOIN information_schema.columns AS c
  ON c.table_schema = t.table_schema
 AND c.table_name   = t.table_name
WHERE t.table_schema NOT IN :internal_schemas
"""


async def _fetch_information_schema_rows(
    engine: AsyncEngine,
    *,
    include_schemas: list[str] | None,
    include_views: bool,
) -> list[_FetchedRow]:
    """对接 PG 的 `information_schema`，按 `(schema, table, ordinal_position)` 排序返回行。"""
    from sqlalchemy import bindparam

    sql = _BASE_SQL
    params: dict[str, Any] = {"internal_schemas": tuple(_INTERNAL_SCHEMAS)}
    if not include_views:
        sql += "  AND t.table_type = 'BASE TABLE'\n"
    if include_schemas is not None:
        sql += "  AND t.table_schema IN :included\n"
        params["included"] = tuple(include_schemas)
    sql += "ORDER BY t.table_schema, t.table_name, c.ordinal_position\n"

    bind_specs = [bindparam("internal_schemas", expanding=True)]
    if include_schemas is not None:
        bind_specs.append(bindparam("included", expanding=True))
    stmt = text(sql).bindparams(*bind_specs)

    async with engine.connect() as conn:
        result = await conn.execute(stmt, params)
        rows = result.all()

    return [
        (
            r[0],
            r[1],
            r[2],
            r[3],
            r[4],
            (r[5] == "YES") if isinstance(r[5], str) else bool(r[5]),
            r[6],
        )
        for r in rows
    ]


async def load_schema(
    engine: AsyncEngine | None = None,
    *,
    include_schemas: list[str] | None = None,
    include_views: bool = False,
) -> list[TableInfo]:
    """从给定 engine 上抽取业务库 schema。

    聚合策略：
    1. 调 `_fetch_information_schema_rows` 拿 7 元组行（已按 SQL 层过滤）。
    2. 在 Python 兜底再过滤一次内部 schema（防御性，避免实现 bug）。
    3. 若 `include_views=False`，只保留 `table_type == "BASE TABLE"`。
    4. 按 `(schema_name, table_name)` 分组，每组的列按 SQL 层 `ordinal_position` 已排好序。
    5. 输出按 `(schema_name, table_name)` 字典序。
    """
    rows = await _fetch_information_schema_rows(
        engine,
        include_schemas=include_schemas,
        include_views=include_views,
    )

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for schema, table, table_type, col, dt, nullable, default in rows:
        if schema in _INTERNAL_SCHEMAS:
            continue
        if not include_views and table_type != "BASE TABLE":
            continue
        key = (schema, table)
        if key not in grouped:
            grouped[key] = {"table_type": table_type, "cols": []}
        grouped[key]["cols"].append(
            ColumnInfo(
                column_name=col,
                data_type=dt,
                is_nullable=nullable,
                column_default=default,
            )
        )

    return [
        TableInfo(
            schema_name=k[0],
            table_name=k[1],
            table_type=v["table_type"],
            columns=tuple(v["cols"]),
        )
        for k, v in sorted(grouped.items())
    ]
