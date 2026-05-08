"""STE-21：业务库 schema 抽取（占位）。

设计要点（实现见 commit 2）：
- 接受任意 `AsyncEngine`（用户决策：function-level engine 注入），
  使得未来加业务库时只需在调用方传入新 engine，本模块不感知。
- 默认从 `information_schema.tables` + `information_schema.columns` 抽，
  跳过系统 schema（pg_*, information_schema）+ 我们的内部 schema
  （meta / rag / checkpoint）。

返回值仅是「发现到的字面信息」，不直接入库——是否登记到 SemanticTable
由上层 API 决定（典型流程：调 `/semantics/discover` → 用户在 UI 上勾选
要登记的表 → 调 `/semantics/tables` 创建）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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


async def _fetch_information_schema_rows(
    engine: AsyncEngine,
    *,
    include_schemas: list[str] | None,
    include_views: bool,
) -> list[_FetchedRow]:
    """从 `information_schema.tables` × `information_schema.columns` LEFT JOIN
    抽取行。SQL 在 commit 2 实现；本占位让 monkeypatch 能在测试里替换它。
    """
    raise NotImplementedError


async def load_schema(
    engine: AsyncEngine | None = None,
    *,
    include_schemas: list[str] | None = None,
    include_views: bool = False,
) -> list[TableInfo]:
    """从给定 engine 上抽取业务库 schema。

    Args:
        engine: 业务库的 `AsyncEngine`。本模块不创建 engine，
            由调用方负责生命周期。
        include_schemas: 仅抽取这些 schema；None 表示「除 `_INTERNAL_SCHEMAS` 之外
            所有非系统 schema」。
        include_views: 是否包含 VIEW / MATERIALIZED VIEW，默认 False。

    Returns:
        发现到的 `TableInfo` 列表，按 (schema_name, table_name) 字典序。
    """
    raise NotImplementedError
