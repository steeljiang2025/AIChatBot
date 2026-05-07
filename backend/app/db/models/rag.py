"""RAG 语义元数据（落 rag schema）+ 向量列 + 全文检索列。

向量列使用 `pgvector.sqlalchemy.Vector(1024)`（与 text-embedding-v4 对齐，已在 STE-16 探针验证）。
HNSW + GIN 索引在迁移脚本里手写（autogenerate 不擅长 vector / generated tsvector）。

`tsv` 是 `tsvector` 的 PostgreSQL 生成列（GENERATED ALWAYS ... STORED），
免去触发器维护，直接 `to_tsvector('simple', coalesce(...))`。
中文分词如要升级到 zhparser，仅需在迁移层替换字典，不必改 ORM。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Computed, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.declarative import Base

from ._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


# 与 QWEN_EMBEDDING_DIM 保持一致；改维度同步改这里 + 迁移
EMBEDDING_DIM = 1024


class SemanticTable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """业务表的语义元数据。

    `(tenant_id, schema_name, table_name)` 唯一；同表名可被不同租户独立登记。
    """

    __tablename__ = "semantic_tables"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "schema_name",
            "table_name",
            name="uq_semantic_tables_tenant_full_name",
        ),
        {"schema": "rag"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_name: Mapped[str] = mapped_column(String(63), nullable=False)
    table_name: Mapped[str] = mapped_column(String(63), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[dict | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', "
            "coalesce(display_name, '') || ' ' || "
            "coalesce(table_name, '')   || ' ' || "
            "coalesce(description, ''))",
            persisted=True,
        ),
    )

    columns: Mapped[list[SemanticColumn]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SemanticColumn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """业务表中某一列的语义元数据。"""

    __tablename__ = "semantic_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "column_name", name="uq_semantic_columns_table_col"),
        Index("ix_semantic_columns_tenant", "tenant_id"),
        {"schema": "rag"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag.semantic_tables.id", ondelete="CASCADE"),
        nullable=False,
    )
    column_name: Mapped[str] = mapped_column(String(63), nullable=False)
    data_type: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    business_meaning: Mapped[str | None] = mapped_column(Text)
    is_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', "
            "coalesce(display_name, '')      || ' ' || "
            "coalesce(column_name, '')       || ' ' || "
            "coalesce(business_meaning, '')  || ' ' || "
            "coalesce(description, ''))",
            persisted=True,
        ),
    )

    table: Mapped[SemanticTable] = relationship(back_populates="columns")


class SemanticTerm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """业务术语 → 字段映射（含同义词）。

    用于解决"客户活跃度"这类业务口径词到具体表/列的映射。
    """

    __tablename__ = "semantic_terms"
    __table_args__ = (
        UniqueConstraint("tenant_id", "term", name="uq_semantic_terms_tenant_term"),
        {"schema": "rag"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term: Mapped[str] = mapped_column(String(128), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)
    synonyms: Mapped[dict | None] = mapped_column(JSONB)
    related_refs: Mapped[dict | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', "
            "coalesce(term, '')       || ' ' || "
            "coalesce(definition, ''))",
            persisted=True,
        ),
    )


class SemanticRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """语义层的表/列关系（FK / 派生 / 同义等）。

    `relation_type` 自由字符串，常见取值：fk、derived、synonym、aggregate_of。
    `from_column_id` / `to_column_id` 可空 → 表级关系也能表达。
    """

    __tablename__ = "semantic_relations"
    __table_args__ = (
        Index("ix_semantic_relations_tenant_from", "tenant_id", "from_table_id"),
        Index("ix_semantic_relations_tenant_to", "tenant_id", "to_table_id"),
        {"schema": "rag"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag.semantic_tables.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_column_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag.semantic_columns.id", ondelete="CASCADE"),
        nullable=True,
    )
    to_table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag.semantic_tables.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_column_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag.semantic_columns.id", ondelete="CASCADE"),
        nullable=True,
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
