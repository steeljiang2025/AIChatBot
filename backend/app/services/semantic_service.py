"""STE-21：语义层业务编排（占位）。

职责：
- 把 repo 层的越权访问（None / False）转译为 404 信号。
- 提供 `discover` / `reindex` / `search` 三个高层操作（实现见 commit 2）。

约束：
- 所有方法都接收明确的 `tenant_id`，不依赖 ContextVar 隐式传递。
- 不直接 import HTTP 异常，由 API 层根据返回值映射状态码。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from app.db.models import (
        SemanticColumn,
        SemanticRelation,
        SemanticTable,
        SemanticTerm,
    )
    from app.semantic.indexer import ReindexReport
    from app.semantic.retriever import Hit, HitType
    from app.semantic.schema_loader import TableInfo


# ============ tables ============


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


async def patch_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticTable | None:
    raise NotImplementedError


async def remove_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    raise NotImplementedError


# ============ columns ============


async def list_columns(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[SemanticColumn] | None:
    """父表不存在 / 越权返回 None。"""
    raise NotImplementedError


async def create_column(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
    column_name: str,
    data_type: str,
    display_name: str | None,
    description: str | None,
    business_meaning: str | None,
    is_pii: bool,
) -> SemanticColumn | None:
    """父表不存在 / 越权返回 None。"""
    raise NotImplementedError


async def patch_column(
    session: AsyncSession,
    *,
    column_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticColumn | None:
    raise NotImplementedError


async def remove_column(
    session: AsyncSession,
    *,
    column_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    raise NotImplementedError


# ============ terms ============


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


async def patch_term(
    session: AsyncSession,
    *,
    term_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticTerm | None:
    raise NotImplementedError


async def remove_term(
    session: AsyncSession,
    *,
    term_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    raise NotImplementedError


# ============ relations ============


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
) -> SemanticRelation | None:
    """from_table_id / to_table_id 不存在或越权返回 None。"""
    raise NotImplementedError


async def patch_relation(
    session: AsyncSession,
    *,
    relation_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticRelation | None:
    raise NotImplementedError


async def remove_relation(
    session: AsyncSession,
    *,
    relation_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    raise NotImplementedError


# ============ 高层操作 ============


async def discover_business_schema(
    *,
    engine: AsyncEngine,
    include_schemas: list[str] | None = None,
    include_views: bool = False,
) -> list[TableInfo]:
    """调 schema_loader 抽取业务库 schema（dry-run，不入库）。"""
    raise NotImplementedError


async def reindex(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> ReindexReport:
    """调 indexer.reindex_tenant 全量重建本租户 embedding。"""
    raise NotImplementedError


async def hybrid_search(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int,
    alpha: float,
    types: tuple[HitType, ...] | None = None,
) -> list[Hit]:
    """调 retriever.search 做混合检索。"""
    raise NotImplementedError
