"""STE-21：语义 RAG 子系统。

外部稳定接口（commit 2 落地）：
- schema_loader.load_schema(engine, schemas) → list[TableInfo]：业务库表/列发现
- indexer.reindex_tenant(session, tenant_id) → ReindexReport：全量重建本租户向量
- retriever.search(session, *, tenant_id, query, ...) → list[Hit]：混合检索
- 数据类型：TableInfo / ColumnInfo / ReindexReport / Hit
"""

from app.semantic.indexer import ReindexReport, reindex_tenant
from app.semantic.retriever import Hit, search
from app.semantic.schema_loader import ColumnInfo, TableInfo, load_schema

__all__ = [
    "ColumnInfo",
    "Hit",
    "ReindexReport",
    "TableInfo",
    "load_schema",
    "reindex_tenant",
    "search",
]
