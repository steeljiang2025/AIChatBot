"""STE-24：从 SemanticTable / SemanticColumn 反查 SQL 安全白名单（占位）。

`load_schema_whitelist(session, tenant_id)` 返回 STE-22 sanitize_sql 需要的
三个集合：
- known_tables: set[(schema_lower, table_lower)]
- known_columns: dict[(schema_lower, table_lower) → set[col_lower]]
- tenant_scoped_tables: set[(schema_lower, table_lower)]
  规则：含 `tenant_id` 列的表自动视为多租户表；STE-22 tenant_guard 会
  对这些表注入 `:tid` 谓词。

性能注意：当前实现 per-request 拉一次（用户决策）；后续可在 lifespan
预加载到 app.state.schema_index。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SchemaWhitelist:
    """STE-22 sanitize_sql 需要的 3 个白名单。"""

    known_tables: set[tuple[str, str]]
    known_columns: dict[tuple[str, str], set[str]]
    tenant_scoped_tables: set[tuple[str, str]]


async def load_schema_whitelist(
    session: "AsyncSession", *, tenant_id: uuid.UUID
) -> SchemaWhitelist:
    """从 RAG meta 加载本租户的 schema 白名单。"""
    raise NotImplementedError
