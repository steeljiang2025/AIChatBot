"""STE-21：语义层 ORM 数据访问。

设计：
- 4 类资源（tables / columns / terms / relations）共用一个 repo 文件。
- 每个资源最小 CRUD：list / get / create / update / delete。
- 所有查询强制按 `tenant_id` 过滤；越权（资源属于别 tenant）一律返回 None /
  False，由 service 层转 404。
- update 用 `changes: dict[str, Any]` 部分更新风格：只覆盖 dict 里出现的属性。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db.models import (
    SemanticColumn,
    SemanticRelation,
    SemanticTable,
    SemanticTerm,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ============ SemanticTable ============


async def list_tables(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticTable], int]:
    base = select(SemanticTable).where(SemanticTable.tenant_id == tenant_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items_stmt = (
        base.order_by(SemanticTable.updated_at.desc()).limit(limit).offset(offset)
    )
    res = await session.execute(items_stmt)
    return list(res.scalars().all()), int(total)


async def get_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticTable | None:
    stmt = select(SemanticTable).where(
        SemanticTable.id == table_id, SemanticTable.tenant_id == tenant_id
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


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
    obj = SemanticTable(
        tenant_id=tenant_id,
        schema_name=schema_name,
        table_name=table_name,
        display_name=display_name,
        description=description,
        tags=tags,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


_TABLE_PATCHABLE: frozenset[str] = frozenset({"display_name", "description", "tags"})


async def update_table(
    session: AsyncSession,
    *,
    obj: SemanticTable,
    changes: dict[str, Any],
) -> SemanticTable:
    for k, v in changes.items():
        if k in _TABLE_PATCHABLE:
            setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_table(session: AsyncSession, *, obj: SemanticTable) -> None:
    await session.delete(obj)
    await session.commit()


# ============ SemanticColumn ============


async def list_columns_of_table(
    session: AsyncSession,
    *,
    table_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[SemanticColumn]:
    stmt = (
        select(SemanticColumn)
        .where(
            SemanticColumn.table_id == table_id,
            SemanticColumn.tenant_id == tenant_id,
        )
        .order_by(SemanticColumn.created_at.asc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_column(
    session: AsyncSession,
    *,
    column_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticColumn | None:
    stmt = select(SemanticColumn).where(
        SemanticColumn.id == column_id, SemanticColumn.tenant_id == tenant_id
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


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
    obj = SemanticColumn(
        tenant_id=tenant_id,
        table_id=table_id,
        column_name=column_name,
        data_type=data_type,
        display_name=display_name,
        description=description,
        business_meaning=business_meaning,
        is_pii=is_pii,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


_COLUMN_PATCHABLE: frozenset[str] = frozenset(
    {"display_name", "description", "business_meaning", "is_pii"}
)


async def update_column(
    session: AsyncSession,
    *,
    obj: SemanticColumn,
    changes: dict[str, Any],
) -> SemanticColumn:
    for k, v in changes.items():
        if k in _COLUMN_PATCHABLE:
            setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_column(session: AsyncSession, *, obj: SemanticColumn) -> None:
    await session.delete(obj)
    await session.commit()


# ============ SemanticTerm ============


async def list_terms(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticTerm], int]:
    base = select(SemanticTerm).where(SemanticTerm.tenant_id == tenant_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items_stmt = (
        base.order_by(SemanticTerm.updated_at.desc()).limit(limit).offset(offset)
    )
    res = await session.execute(items_stmt)
    return list(res.scalars().all()), int(total)


async def get_term(
    session: AsyncSession,
    *,
    term_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticTerm | None:
    stmt = select(SemanticTerm).where(
        SemanticTerm.id == term_id, SemanticTerm.tenant_id == tenant_id
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def create_term(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    term: str,
    definition: str | None,
    synonyms: dict[str, Any] | None,
    related_refs: dict[str, Any] | None,
) -> SemanticTerm:
    obj = SemanticTerm(
        tenant_id=tenant_id,
        term=term,
        definition=definition,
        synonyms=synonyms,
        related_refs=related_refs,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


_TERM_PATCHABLE: frozenset[str] = frozenset({"definition", "synonyms", "related_refs"})


async def update_term(
    session: AsyncSession,
    *,
    obj: SemanticTerm,
    changes: dict[str, Any],
) -> SemanticTerm:
    for k, v in changes.items():
        if k in _TERM_PATCHABLE:
            setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_term(session: AsyncSession, *, obj: SemanticTerm) -> None:
    await session.delete(obj)
    await session.commit()


# ============ SemanticRelation ============


async def list_relations(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SemanticRelation], int]:
    base = select(SemanticRelation).where(SemanticRelation.tenant_id == tenant_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items_stmt = (
        base.order_by(SemanticRelation.updated_at.desc()).limit(limit).offset(offset)
    )
    res = await session.execute(items_stmt)
    return list(res.scalars().all()), int(total)


async def get_relation(
    session: AsyncSession,
    *,
    relation_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> SemanticRelation | None:
    stmt = select(SemanticRelation).where(
        SemanticRelation.id == relation_id,
        SemanticRelation.tenant_id == tenant_id,
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


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
    obj = SemanticRelation(
        tenant_id=tenant_id,
        from_table_id=from_table_id,
        to_table_id=to_table_id,
        from_column_id=from_column_id,
        to_column_id=to_column_id,
        relation_type=relation_type,
        description=description,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


_RELATION_PATCHABLE: frozenset[str] = frozenset({"description"})


async def update_relation(
    session: AsyncSession,
    *,
    obj: SemanticRelation,
    changes: dict[str, Any],
) -> SemanticRelation:
    for k, v in changes.items():
        if k in _RELATION_PATCHABLE:
            setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_relation(session: AsyncSession, *, obj: SemanticRelation) -> None:
    await session.delete(obj)
    await session.commit()
