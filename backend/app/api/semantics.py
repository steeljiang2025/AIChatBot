"""STE-21：语义层管理 API。

22 个端点，全部需要 JWT（不在 _PUBLIC_PATHS 白名单）。

设计：
- 4 类资源 + 嵌套 columns 在 tables 下
- 高层操作：discover / reindex / search
- 越权 / 不存在 → 404，不暴露存在性（与 STE-19 sessions 一致）
- discover 接 settings.business_engine（lifespan 时挂在 app.state）；
  STE-21 阶段允许 engine 为 None，会回 503，让 UI 给"业务库未配置"提示。
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import CurrentTenantId, CurrentUserId, MetaSession
from app.semantic.indexer import ReindexReport
from app.semantic.retriever import DEFAULT_ALPHA, DEFAULT_TOP_K, HitType
from app.services import semantic_service

router = APIRouter(prefix="/semantics", tags=["semantics"])


# ========== Pydantic ==========


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TableCreate(BaseModel):
    schema_name: str = Field(..., min_length=1, max_length=63)
    table_name: str = Field(..., min_length=1, max_length=63)
    display_name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    tags: dict[str, Any] | None = None


class TablePatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    tags: dict[str, Any] | None = None


class TableResponse(_OrmBase):
    id: uuid.UUID
    schema_name: str
    table_name: str
    display_name: str | None
    description: str | None
    tags: dict[str, Any] | None


class TableListResponse(BaseModel):
    items: list[TableResponse]
    total: int
    limit: int
    offset: int


class ColumnCreate(BaseModel):
    column_name: str = Field(..., min_length=1, max_length=63)
    data_type: str = Field(..., min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    business_meaning: str | None = None
    is_pii: bool = False


class ColumnPatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    business_meaning: str | None = None
    is_pii: bool | None = None


class ColumnResponse(_OrmBase):
    id: uuid.UUID
    table_id: uuid.UUID
    column_name: str
    data_type: str
    display_name: str | None
    description: str | None
    business_meaning: str | None
    is_pii: bool


class ColumnListResponse(BaseModel):
    items: list[ColumnResponse]


class TermCreate(BaseModel):
    term: str = Field(..., min_length=1, max_length=128)
    definition: str | None = None
    synonyms: dict[str, Any] | None = None
    related_refs: dict[str, Any] | None = None


class TermPatch(BaseModel):
    definition: str | None = None
    synonyms: dict[str, Any] | None = None
    related_refs: dict[str, Any] | None = None


class TermResponse(_OrmBase):
    id: uuid.UUID
    term: str
    definition: str | None
    synonyms: dict[str, Any] | None
    related_refs: dict[str, Any] | None


class TermListResponse(BaseModel):
    items: list[TermResponse]
    total: int
    limit: int
    offset: int


class RelationCreate(BaseModel):
    from_table_id: uuid.UUID
    to_table_id: uuid.UUID
    relation_type: str = Field(..., min_length=1, max_length=32)
    from_column_id: uuid.UUID | None = None
    to_column_id: uuid.UUID | None = None
    description: str | None = None


class RelationPatch(BaseModel):
    description: str | None = None


class RelationResponse(_OrmBase):
    id: uuid.UUID
    from_table_id: uuid.UUID
    to_table_id: uuid.UUID
    from_column_id: uuid.UUID | None
    to_column_id: uuid.UUID | None
    relation_type: str
    description: str | None


class RelationListResponse(BaseModel):
    items: list[RelationResponse]
    total: int
    limit: int
    offset: int


# ---- 高层操作 Pydantic ----


class DiscoverRequest(BaseModel):
    include_schemas: list[str] | None = None
    include_views: bool = False


class DiscoveredColumn(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    column_default: str | None = None


class DiscoveredTable(BaseModel):
    schema_name: str
    table_name: str
    table_type: str
    columns: list[DiscoveredColumn]


class DiscoverResponse(BaseModel):
    tables: list[DiscoveredTable]


class ReindexResponse(BaseModel):
    tables_reindexed: int
    columns_reindexed: int
    terms_reindexed: int
    relations_reindexed: int
    embeddings_called: int
    total: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=50)
    alpha: float = Field(default=DEFAULT_ALPHA, ge=0.0, le=1.0)
    types: list[Literal["table", "column", "term", "relation"]] | None = None


class HitResponse(BaseModel):
    type: HitType
    id: uuid.UUID
    title: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    hits: list[HitResponse]


# ========== Helpers ==========


def _not_found(detail: str = "Not found") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=detail)


# ============================================================
# tables CRUD
# ============================================================


@router.get("/tables", response_model=TableListResponse, summary="列出已登记的业务表")
async def list_tables(
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TableListResponse:
    items, total = await semantic_service.list_tables(
        db, tenant_id=tenant_id, limit=limit, offset=offset
    )
    return TableListResponse(
        items=[TableResponse.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/tables",
    response_model=TableResponse,
    status_code=status.HTTP_201_CREATED,
    summary="登记一张业务表",
)
async def create_table(
    body: TableCreate,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> TableResponse:
    obj = await semantic_service.create_table(
        db,
        tenant_id=tenant_id,
        schema_name=body.schema_name,
        table_name=body.table_name,
        display_name=body.display_name,
        description=body.description,
        tags=body.tags,
    )
    return TableResponse.model_validate(obj)


@router.get("/tables/{table_id}", response_model=TableResponse, summary="表详情")
async def get_table(
    table_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> TableResponse:
    obj = await semantic_service.get_table(db, table_id=table_id, tenant_id=tenant_id)
    if obj is None:
        raise _not_found("Table not found")
    return TableResponse.model_validate(obj)


@router.patch("/tables/{table_id}", response_model=TableResponse, summary="部分更新表")
async def patch_table(
    table_id: uuid.UUID,
    body: TablePatch,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> TableResponse:
    changes = body.model_dump(exclude_unset=True)
    obj = await semantic_service.patch_table(
        db, table_id=table_id, tenant_id=tenant_id, changes=changes
    )
    if obj is None:
        raise _not_found("Table not found")
    return TableResponse.model_validate(obj)


@router.delete(
    "/tables/{table_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除表（cascade 列）",
)
async def delete_table(
    table_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> Response:
    ok = await semantic_service.remove_table(
        db, table_id=table_id, tenant_id=tenant_id
    )
    if not ok:
        raise _not_found("Table not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# columns CRUD（嵌套在 tables 下）
# ============================================================


@router.get(
    "/tables/{table_id}/columns",
    response_model=ColumnListResponse,
    summary="列出某表的字段",
)
async def list_columns(
    table_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> ColumnListResponse:
    cols = await semantic_service.list_columns(
        db, table_id=table_id, tenant_id=tenant_id
    )
    if cols is None:
        raise _not_found("Table not found")
    return ColumnListResponse(items=[ColumnResponse.model_validate(c) for c in cols])


@router.post(
    "/tables/{table_id}/columns",
    response_model=ColumnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="登记字段",
)
async def create_column(
    table_id: uuid.UUID,
    body: ColumnCreate,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> ColumnResponse:
    obj = await semantic_service.create_column(
        db,
        table_id=table_id,
        tenant_id=tenant_id,
        column_name=body.column_name,
        data_type=body.data_type,
        display_name=body.display_name,
        description=body.description,
        business_meaning=body.business_meaning,
        is_pii=body.is_pii,
    )
    if obj is None:
        raise _not_found("Table not found")
    return ColumnResponse.model_validate(obj)


@router.patch(
    "/columns/{column_id}",
    response_model=ColumnResponse,
    summary="部分更新字段",
)
async def patch_column(
    column_id: uuid.UUID,
    body: ColumnPatch,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> ColumnResponse:
    changes = body.model_dump(exclude_unset=True)
    obj = await semantic_service.patch_column(
        db, column_id=column_id, tenant_id=tenant_id, changes=changes
    )
    if obj is None:
        raise _not_found("Column not found")
    return ColumnResponse.model_validate(obj)


@router.delete(
    "/columns/{column_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除字段",
)
async def delete_column(
    column_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> Response:
    ok = await semantic_service.remove_column(
        db, column_id=column_id, tenant_id=tenant_id
    )
    if not ok:
        raise _not_found("Column not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# terms CRUD
# ============================================================


@router.get("/terms", response_model=TermListResponse, summary="列出业务术语")
async def list_terms(
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TermListResponse:
    items, total = await semantic_service.list_terms(
        db, tenant_id=tenant_id, limit=limit, offset=offset
    )
    return TermListResponse(
        items=[TermResponse.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/terms",
    response_model=TermResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建业务术语",
)
async def create_term(
    body: TermCreate,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> TermResponse:
    obj = await semantic_service.create_term(
        db,
        tenant_id=tenant_id,
        term=body.term,
        definition=body.definition,
        synonyms=body.synonyms,
        related_refs=body.related_refs,
    )
    return TermResponse.model_validate(obj)


@router.get("/terms/{term_id}", response_model=TermResponse, summary="术语详情")
async def get_term(
    term_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> TermResponse:
    obj = await semantic_service.get_term(db, term_id=term_id, tenant_id=tenant_id)
    if obj is None:
        raise _not_found("Term not found")
    return TermResponse.model_validate(obj)


@router.patch(
    "/terms/{term_id}",
    response_model=TermResponse,
    summary="部分更新术语",
)
async def patch_term(
    term_id: uuid.UUID,
    body: TermPatch,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> TermResponse:
    changes = body.model_dump(exclude_unset=True)
    obj = await semantic_service.patch_term(
        db, term_id=term_id, tenant_id=tenant_id, changes=changes
    )
    if obj is None:
        raise _not_found("Term not found")
    return TermResponse.model_validate(obj)


@router.delete(
    "/terms/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除术语",
)
async def delete_term(
    term_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> Response:
    ok = await semantic_service.remove_term(
        db, term_id=term_id, tenant_id=tenant_id
    )
    if not ok:
        raise _not_found("Term not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# relations CRUD
# ============================================================


@router.get(
    "/relations", response_model=RelationListResponse, summary="列出语义关联"
)
async def list_relations(
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RelationListResponse:
    items, total = await semantic_service.list_relations(
        db, tenant_id=tenant_id, limit=limit, offset=offset
    )
    return RelationListResponse(
        items=[RelationResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/relations",
    response_model=RelationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建语义关联",
)
async def create_relation(
    body: RelationCreate,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> RelationResponse:
    obj = await semantic_service.create_relation(
        db,
        tenant_id=tenant_id,
        from_table_id=body.from_table_id,
        to_table_id=body.to_table_id,
        relation_type=body.relation_type,
        from_column_id=body.from_column_id,
        to_column_id=body.to_column_id,
        description=body.description,
    )
    if obj is None:
        # from / to 表至少有一边不存在或越权
        raise _not_found("Endpoint table not found")
    return RelationResponse.model_validate(obj)


@router.get(
    "/relations/{relation_id}",
    response_model=RelationResponse,
    summary="关联详情",
)
async def get_relation(
    relation_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> RelationResponse:
    obj = await semantic_service.get_relation(
        db, relation_id=relation_id, tenant_id=tenant_id
    )
    if obj is None:
        raise _not_found("Relation not found")
    return RelationResponse.model_validate(obj)


@router.patch(
    "/relations/{relation_id}",
    response_model=RelationResponse,
    summary="部分更新关联",
)
async def patch_relation(
    relation_id: uuid.UUID,
    body: RelationPatch,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> RelationResponse:
    changes = body.model_dump(exclude_unset=True)
    obj = await semantic_service.patch_relation(
        db, relation_id=relation_id, tenant_id=tenant_id, changes=changes
    )
    if obj is None:
        raise _not_found("Relation not found")
    return RelationResponse.model_validate(obj)


@router.delete(
    "/relations/{relation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除关联",
)
async def delete_relation(
    relation_id: uuid.UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> Response:
    ok = await semantic_service.remove_relation(
        db, relation_id=relation_id, tenant_id=tenant_id
    )
    if not ok:
        raise _not_found("Relation not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# 高层操作
# ============================================================


@router.post(
    "/discover",
    response_model=DiscoverResponse,
    summary="发现业务库 schema（dry-run，不入库）",
)
async def discover(
    request: Request,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    body: DiscoverRequest | None = None,
) -> DiscoverResponse:
    """从业务库 information_schema 抽取表/列；不写入 rag.semantic_*，
    由调用方根据需要决定登记哪些。

    业务库 engine 通过 `app.state.business_engine` 提供（lifespan 启动时
    构建）。STE-21 阶段也允许业务库不存在，此时回 503 让前端提示。
    """
    body = body or DiscoverRequest()
    engine = getattr(request.app.state, "business_engine", None)
    if engine is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business database not configured",
        )
    tables = await semantic_service.discover_business_schema(
        engine=engine,
        include_schemas=body.include_schemas,
        include_views=body.include_views,
    )
    return DiscoverResponse(
        tables=[
            DiscoveredTable(
                schema_name=t.schema_name,
                table_name=t.table_name,
                table_type=t.table_type,
                columns=[
                    DiscoveredColumn(
                        column_name=c.column_name,
                        data_type=c.data_type,
                        is_nullable=c.is_nullable,
                        column_default=c.column_default,
                    )
                    for c in t.columns
                ],
            )
            for t in tables
        ]
    )


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    summary="全量重建本租户语义对象的 embedding",
)
async def reindex(
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> ReindexResponse:
    report: ReindexReport = await semantic_service.reindex(db, tenant_id=tenant_id)
    return ReindexResponse(
        tables_reindexed=report.tables_reindexed,
        columns_reindexed=report.columns_reindexed,
        terms_reindexed=report.terms_reindexed,
        relations_reindexed=report.relations_reindexed,
        embeddings_called=report.embeddings_called,
        total=report.total,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="混合检索（tsvector + vector，加权融合）",
)
async def search(
    body: SearchRequest,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: MetaSession,
) -> SearchResponse:
    types_tup: tuple[HitType, ...] | None = (
        tuple(body.types) if body.types else None  # type: ignore[arg-type]
    )
    hits = await semantic_service.hybrid_search(
        db,
        tenant_id=tenant_id,
        query=body.query,
        top_k=body.top_k,
        alpha=body.alpha,
        types=types_tup,
    )
    return SearchResponse(
        hits=[
            HitResponse(
                type=h.type,
                id=h.id,
                title=h.title,
                snippet=h.snippet,
                score=h.score,
            )
            for h in hits
        ]
    )


__all__ = ["router"]
