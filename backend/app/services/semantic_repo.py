"""STE-21：语义层 ORM 数据访问（占位）。

设计：
- 4 类资源（tables / columns / terms / relations）共用一个 repo 文件，
  避免 4 个微小文件管理负担。
- 每个资源只暴露最小的 CRUD：list / get / create / update / delete。
- 所有查询强制按 `tenant_id` 过滤，与 STE-19 sessions_repo 同模式。
- 越权访问（资源属于别的 tenant）一律返回 None / False，由 service 层
  转 404 让 API 不暴露存在性。
- update 用 `changes: dict[str, Any]` 部分更新风格：只覆盖 dict 里出现的
  属性，避免 sentinel 类型注解的复杂度。

实现见 commit 2。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import (
        SemanticColumn,
        SemanticRelation,
        SemanticTable,
        SemanticTerm,
    )


# ============ SemanticTable ============


async def list_tables(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticTable], int]:
    raise NotImplementedError


async def get_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticTable | None:
    raise NotImplementedError


async def create_table(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    schema_name: str,
    table_name: str,
    display_name: str | None,
    description: str | None,
    tags: dict[str, Any] | None,
) -> SemanticTable:
    raise NotImplementedError


async def update_table(
    session: AsyncSession,
    *,
    obj: SemanticTable,
    changes: dict[str, Any],
) -> SemanticTable:
    """部分更新。`changes` 中允许的 key：
    `display_name` / `description` / `tags`。其它 key 应被上层拒绝。
    """
    raise NotImplementedError


async def delete_table(session: AsyncSession, *, obj: SemanticTable) -> None:
    raise NotImplementedError


# ============ SemanticColumn ============


async def list_columns_of_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[SemanticColumn]:
    raise NotImplementedError


async def get_column(
    session: AsyncSession,
    *,
    column_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticColumn | None:
    raise NotImplementedError


async def create_column(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    table_id: uuid.UUID,
    column_name: str,
    data_type: str,
    display_name: str | None,
    description: str | None,
    business_meaning: str | None,
    is_pii: bool,
) -> SemanticColumn:
    raise NotImplementedError


async def update_column(
    session: AsyncSession,
    *,
    obj: SemanticColumn,
    changes: dict[str, Any],
) -> SemanticColumn:
    """部分更新。`changes` 允许的 key：
    `display_name` / `description` / `business_meaning` / `is_pii`。
    """
    raise NotImplementedError


async def delete_column(session: AsyncSession, *, obj: SemanticColumn) -> None:
    raise NotImplementedError


# ============ SemanticTerm ============


async def list_terms(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticTerm], int]:
    raise NotImplementedError


async def get_term(
    session: AsyncSession,
    *,
    term_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticTerm | None:
    raise NotImplementedError


async def create_term(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    term: str,
    definition: str | None,
    synonyms: dict[str, Any] | None,
    related_refs: dict[str, Any] | None,
) -> SemanticTerm:
    raise NotImplementedError


async def update_term(
    session: AsyncSession,
    *,
    obj: SemanticTerm,
    changes: dict[str, Any],
) -> SemanticTerm:
    """部分更新。`changes` 允许的 key：
    `definition` / `synonyms` / `related_refs`。
    """
    raise NotImplementedError


async def delete_term(session: AsyncSession, *, obj: SemanticTerm) -> None:
    raise NotImplementedError


# ============ SemanticRelation ============


async def list_relations(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticRelation], int]:
    raise NotImplementedError


async def get_relation(
    session: AsyncSession,
    *,
    relation_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticRelation | None:
    raise NotImplementedError


async def create_relation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    from_table_id: uuid.UUID,
    to_table_id: uuid.UUID,
    relation_type: str,
    from_column_id: uuid.UUID | None,
    to_column_id: uuid.UUID | None,
    description: str | None,
) -> SemanticRelation:
    raise NotImplementedError


async def update_relation(
    session: AsyncSession,
    *,
    obj: SemanticRelation,
    changes: dict[str, Any],
) -> SemanticRelation:
    """部分更新。`changes` 允许的 key：`description`。"""
    raise NotImplementedError


async def delete_relation(session: AsyncSession, *, obj: SemanticRelation) -> None:
    raise NotImplementedError
