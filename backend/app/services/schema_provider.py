"""STE-24：从 SemanticTable / SemanticColumn 反查 SQL 安全白名单。

`load_schema_whitelist(session, tenant_id)` 返回 STE-22 sanitize_sql 需要的
三个集合：
- known_tables: set[(schema_lower, table_lower)]
- known_columns: dict[(schema_lower, table_lower) → set[col_lower]]
- tenant_scoped_tables: set[(schema_lower, table_lower)]
  规则：含 `tenant_id` 列的表自动视为多租户表；STE-22 tenant_guard 会
  对这些表注入 `:tid` 谓词。

性能：当前实现 per-request 拉一次（用户决策）；后续可在 lifespan 预加载到
app.state.schema_index。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models import SemanticColumn, SemanticTable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SchemaWhitelist:
    """STE-22 sanitize_sql 需要的 3 个白名单。"""

    known_tables: set[tuple[str, str]]
    known_columns: dict[tuple[str, str], set[str]]
    tenant_scoped_tables: set[tuple[str, str]]


_TENANT_COL: str = "tenant_id"


async def load_schema_whitelist(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> SchemaWhitelist:
    """从 RAG meta 加载本租户的 schema 白名单。

    先取 SemanticTable，再取该租户的 SemanticColumn，按 table_id 分组聚合。
    所有名字一律小写归一，与 STE-22 的 schema_whitelist 检查保持一致。
    """
    tables_stmt = select(SemanticTable).where(SemanticTable.tenant_id == tenant_id)
    tables = list((await session.execute(tables_stmt)).scalars().all())

    cols_stmt = select(SemanticColumn).where(SemanticColumn.tenant_id == tenant_id)
    cols = list((await session.execute(cols_stmt)).scalars().all())

    table_key_by_id: dict[uuid.UUID, tuple[str, str]] = {}
    known_tables: set[tuple[str, str]] = set()
    known_columns: dict[tuple[str, str], set[str]] = {}

    for t in tables:
        key = (t.schema_name.lower(), t.table_name.lower())
        table_key_by_id[t.id] = key
        known_tables.add(key)
        known_columns.setdefault(key, set())

    tenant_scoped: set[tuple[str, str]] = set()
    for c in cols:
        key = table_key_by_id.get(c.table_id)
        if key is None:
            continue
        col_lower = c.column_name.lower()
        known_columns.setdefault(key, set()).add(col_lower)
        if col_lower == _TENANT_COL:
            tenant_scoped.add(key)

    return SchemaWhitelist(
        known_tables=known_tables,
        known_columns=known_columns,
        tenant_scoped_tables=tenant_scoped,
    )
