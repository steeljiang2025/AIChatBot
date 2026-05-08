"""STE-21：语义层业务编排。

职责：
- 把 repo 层的越权访问（None / False）转译为 service 层的 None / False，
  由 API 层统一映射成 404。
- 提供 `discover_business_schema` / `reindex` / `hybrid_search` 三个高层操作。

约束：
- 所有方法都接收明确的 `tenant_id`，不依赖 ContextVar 隐式传递。
- 不直接 import HTTP 异常，由 API 层根据返回值映射状态码。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from app.semantic import indexer, retriever, schema_loader
from app.services import semantic_repo

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
    return await semantic_repo.list_tables(
        session, tenant_id=tenant_id, limit=limit, offset=offset
    )


async def get_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticTable | None:
    return await semantic_repo.get_table(
        session, table_id=table_id, tenant_id=tenant_id
    )


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
    return await semantic_repo.create_table(
        session,
        tenant_id=tenant_id,
        schema_name=schema_name,
        table_name=table_name,
        display_name=display_name,
        description=description,
        tags=tags,
    )


async def patch_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticTable | None:
    obj = await semantic_repo.get_table(
        session, table_id=table_id, tenant_id=tenant_id
    )
    if obj is None:
        return None
    return await semantic_repo.update_table(session, obj=obj, changes=changes)


async def remove_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    obj = await semantic_repo.get_table(
        session, table_id=table_id, tenant_id=tenant_id
    )
    if obj is None:
        return False
    await semantic_repo.delete_table(session, obj=obj)
    return True


# ============ columns ============


async def list_columns(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[SemanticColumn] | None:
    parent = await semantic_repo.get_table(
        session, table_id=table_id, tenant_id=tenant_id
    )
    if parent is None:
        return None
    return await semantic_repo.list_columns_of_table(
        session, table_id=table_id, tenant_id=tenant_id
    )


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
    parent = await semantic_repo.get_table(
        session, table_id=table_id, tenant_id=tenant_id
    )
    if parent is None:
        return None
    return await semantic_repo.create_column(
        session,
        tenant_id=tenant_id,
        table_id=table_id,
        column_name=column_name,
        data_type=data_type,
        display_name=display_name,
        description=description,
        business_meaning=business_meaning,
        is_pii=is_pii,
    )


async def patch_column(
    session: AsyncSession,
    *,
    column_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticColumn | None:
    obj = await semantic_repo.get_column(
        session, column_id=column_id, tenant_id=tenant_id
    )
    if obj is None:
        return None
    return await semantic_repo.update_column(session, obj=obj, changes=changes)


async def remove_column(
    session: AsyncSession,
    *,
    column_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    obj = await semantic_repo.get_column(
        session, column_id=column_id, tenant_id=tenant_id
    )
    if obj is None:
        return False
    await semantic_repo.delete_column(session, obj=obj)
    return True


# ============ terms ============


async def list_terms(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticTerm], int]:
    return await semantic_repo.list_terms(
        session, tenant_id=tenant_id, limit=limit, offset=offset
    )


async def get_term(
    session: AsyncSession,
    *,
    term_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticTerm | None:
    return await semantic_repo.get_term(
        session, term_id=term_id, tenant_id=tenant_id
    )


async def create_term(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    term: str,
    definition: str | None,
    synonyms: dict[str, Any] | None,
    related_refs: dict[str, Any] | None,
) -> SemanticTerm:
    return await semantic_repo.create_term(
        session,
        tenant_id=tenant_id,
        term=term,
        definition=definition,
        synonyms=synonyms,
        related_refs=related_refs,
    )


async def patch_term(
    session: AsyncSession,
    *,
    term_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticTerm | None:
    obj = await semantic_repo.get_term(
        session, term_id=term_id, tenant_id=tenant_id
    )
    if obj is None:
        return None
    return await semantic_repo.update_term(session, obj=obj, changes=changes)


async def remove_term(
    session: AsyncSession,
    *,
    term_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    obj = await semantic_repo.get_term(
        session, term_id=term_id, tenant_id=tenant_id
    )
    if obj is None:
        return False
    await semantic_repo.delete_term(session, obj=obj)
    return True


# ============ relations ============


async def list_relations(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticRelation], int]:
    return await semantic_repo.list_relations(
        session, tenant_id=tenant_id, limit=limit, offset=offset
    )


async def get_relation(
    session: AsyncSession,
    *,
    relation_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticRelation | None:
    return await semantic_repo.get_relation(
        session, relation_id=relation_id, tenant_id=tenant_id
    )


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
    """from_table_id / to_table_id 必须都属于本租户，否则返回 None。"""
    if not await semantic_repo.get_table(
        session, table_id=from_table_id, tenant_id=tenant_id
    ):
        return None
    if not await semantic_repo.get_table(
        session, table_id=to_table_id, tenant_id=tenant_id
    ):
        return None
    return await semantic_repo.create_relation(
        session,
        tenant_id=tenant_id,
        from_table_id=from_table_id,
        to_table_id=to_table_id,
        relation_type=relation_type,
        from_column_id=from_column_id,
        to_column_id=to_column_id,
        description=description,
    )


async def patch_relation(
    session: AsyncSession,
    *,
    relation_id: uuid.UUID,
    tenant_id: uuid.UUID,
    changes: dict[str, Any],
) -> SemanticRelation | None:
    obj = await semantic_repo.get_relation(
        session, relation_id=relation_id, tenant_id=tenant_id
    )
    if obj is None:
        return None
    return await semantic_repo.update_relation(session, obj=obj, changes=changes)


async def remove_relation(
    session: AsyncSession,
    *,
    relation_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    obj = await semantic_repo.get_relation(
        session, relation_id=relation_id, tenant_id=tenant_id
    )
    if obj is None:
        return False
    await semantic_repo.delete_relation(session, obj=obj)
    return True


# ============ 高层操作 ============


async def discover_business_schema(
    *,
    engine: AsyncEngine,
    include_schemas: list[str] | None = None,
    include_views: bool = False,
) -> list[TableInfo]:
    """调 schema_loader 抽取业务库 schema（dry-run，不入库）。"""
    return await schema_loader.load_schema(
        engine,
        include_schemas=include_schemas,
        include_views=include_views,
    )


async def reindex(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> ReindexReport:
    """调 indexer.reindex_tenant 全量重建本租户 embedding。"""
    return await indexer.reindex_tenant(session, tenant_id=tenant_id)


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
    return await retriever.search(
        session,
        tenant_id=tenant_id,
        query=query,
        top_k=top_k,
        alpha=alpha,
        types=types,
    )
