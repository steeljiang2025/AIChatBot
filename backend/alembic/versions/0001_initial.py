"""initial: meta(tenants/users/chat_sessions/messages) + rag(semantic_*)

Revision ID: 0001
Revises:
Create Date: 2026-05-07

要点：
- schema (`meta`/`rag`/`biz`/`checkpoint`) 已由 `infra/postgres/init.sql` 在数据库
  首次启动时建好，alembic **不重复创建 schema**。
- `vector` 扩展同样由 init.sql 启用；这里用 `IF NOT EXISTS` 兜底，确保迁移可在干净
  数据库直接 `upgrade head`。
- `checkpoint` schema 4 张表归 langgraph 自管，本迁移完全不碰（env.py 的
  `include_object` 钩子也会拒绝任何 autogenerate diff）。
- HNSW 与 GIN 索引手动声明，因为 alembic autogenerate 不能可靠生成
  `postgresql_using='hnsw'` + ops + storage 参数。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


EMBEDDING_DIM = 1024


# ---------------------------------------------------------------------------
# 生成列：与 ORM 模型保持一致
# ---------------------------------------------------------------------------
TSV_TABLE_EXPR = (
    "to_tsvector('simple', "
    "coalesce(display_name, '') || ' ' || "
    "coalesce(table_name, '')   || ' ' || "
    "coalesce(description, ''))"
)
TSV_COLUMN_EXPR = (
    "to_tsvector('simple', "
    "coalesce(display_name, '')      || ' ' || "
    "coalesce(column_name, '')       || ' ' || "
    "coalesce(business_meaning, '')  || ' ' || "
    "coalesce(description, ''))"
)
TSV_TERM_EXPR = (
    "to_tsvector('simple', "
    "coalesce(term, '')       || ' ' || "
    "coalesce(definition, ''))"
)


def upgrade() -> None:
    # 注意：依赖的 PG 扩展（vector / pgcrypto / pg_trgm）由 infra/postgres/init.sql
    # 以 superuser 身份创建。app_user 没有 CREATE EXTENSION 权限，迁移层 **不**
    # 直接 `CREATE EXTENSION`，否则会 `permission denied`。
    # 干净环境部署：先 `make up`（让 init.sql 跑过）再 `make be-migrate`。

    # ---- 1. meta.tenants -------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_tenants_code"),
        schema="meta",
    )

    # ---- 2. meta.users ---------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column(
            "roles",
            postgresql.ARRAY(sa.String(length=32)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        schema="meta",
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"], schema="meta")

    # ---- 3. meta.chat_sessions ------------------------------------------
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="meta",
    )
    op.create_index(
        "ix_chat_sessions_tenant_user",
        "chat_sessions",
        ["tenant_id", "user_id"],
        schema="meta",
    )
    op.create_index(
        "ix_chat_sessions_updated_at",
        "chat_sessions",
        ["updated_at"],
        schema="meta",
    )

    # ---- 4. meta.messages ------------------------------------------------
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="meta",
    )
    op.create_index(
        "ix_messages_session_created",
        "messages",
        ["session_id", "created_at"],
        schema="meta",
    )
    op.create_index("ix_messages_tenant", "messages", ["tenant_id"], schema="meta")

    # ---- 5. rag.semantic_tables -----------------------------------------
    op.create_table(
        "semantic_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schema_name", sa.String(length=63), nullable=False),
        sa.Column("table_name", sa.String(length=63), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(TSV_TABLE_EXPR, persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "schema_name",
            "table_name",
            name="uq_semantic_tables_tenant_full_name",
        ),
        schema="rag",
    )
    op.create_index(
        "ix_semantic_tables_tenant_id",
        "semantic_tables",
        ["tenant_id"],
        schema="rag",
    )
    op.create_index(
        "ix_semantic_tables_embedding_hnsw",
        "semantic_tables",
        ["embedding"],
        schema="rag",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_semantic_tables_tsv_gin",
        "semantic_tables",
        ["tsv"],
        schema="rag",
        postgresql_using="gin",
    )
    op.create_index(
        "ix_semantic_tables_tags_gin",
        "semantic_tables",
        ["tags"],
        schema="rag",
        postgresql_using="gin",
    )

    # ---- 6. rag.semantic_columns ----------------------------------------
    op.create_table(
        "semantic_columns",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag.semantic_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("column_name", sa.String(length=63), nullable=False),
        sa.Column("data_type", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("business_meaning", sa.Text(), nullable=True),
        sa.Column(
            "is_pii",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(TSV_COLUMN_EXPR, persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("table_id", "column_name", name="uq_semantic_columns_table_col"),
        schema="rag",
    )
    op.create_index(
        "ix_semantic_columns_tenant",
        "semantic_columns",
        ["tenant_id"],
        schema="rag",
    )
    op.create_index(
        "ix_semantic_columns_embedding_hnsw",
        "semantic_columns",
        ["embedding"],
        schema="rag",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_semantic_columns_tsv_gin",
        "semantic_columns",
        ["tsv"],
        schema="rag",
        postgresql_using="gin",
    )

    # ---- 7. rag.semantic_terms ------------------------------------------
    op.create_table(
        "semantic_terms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("term", sa.String(length=128), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("synonyms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("related_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(TSV_TERM_EXPR, persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "term", name="uq_semantic_terms_tenant_term"),
        schema="rag",
    )
    op.create_index(
        "ix_semantic_terms_tenant_id",
        "semantic_terms",
        ["tenant_id"],
        schema="rag",
    )
    op.create_index(
        "ix_semantic_terms_embedding_hnsw",
        "semantic_terms",
        ["embedding"],
        schema="rag",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_semantic_terms_tsv_gin",
        "semantic_terms",
        ["tsv"],
        schema="rag",
        postgresql_using="gin",
    )

    # ---- 8. rag.semantic_relations --------------------------------------
    op.create_table(
        "semantic_relations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag.semantic_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_column_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag.semantic_columns.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "to_table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag.semantic_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_column_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag.semantic_columns.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="rag",
    )
    op.create_index(
        "ix_semantic_relations_tenant_from",
        "semantic_relations",
        ["tenant_id", "from_table_id"],
        schema="rag",
    )
    op.create_index(
        "ix_semantic_relations_tenant_to",
        "semantic_relations",
        ["tenant_id", "to_table_id"],
        schema="rag",
    )


def downgrade() -> None:
    # 反向逐张 drop（依赖外键的孩子表先删）
    for idx in (
        "ix_semantic_relations_tenant_to",
        "ix_semantic_relations_tenant_from",
    ):
        op.drop_index(idx, table_name="semantic_relations", schema="rag")
    op.drop_table("semantic_relations", schema="rag")

    for idx in (
        "ix_semantic_terms_tsv_gin",
        "ix_semantic_terms_embedding_hnsw",
        "ix_semantic_terms_tenant_id",
    ):
        op.drop_index(idx, table_name="semantic_terms", schema="rag")
    op.drop_table("semantic_terms", schema="rag")

    for idx in (
        "ix_semantic_columns_tsv_gin",
        "ix_semantic_columns_embedding_hnsw",
        "ix_semantic_columns_tenant",
    ):
        op.drop_index(idx, table_name="semantic_columns", schema="rag")
    op.drop_table("semantic_columns", schema="rag")

    for idx in (
        "ix_semantic_tables_tags_gin",
        "ix_semantic_tables_tsv_gin",
        "ix_semantic_tables_embedding_hnsw",
        "ix_semantic_tables_tenant_id",
    ):
        op.drop_index(idx, table_name="semantic_tables", schema="rag")
    op.drop_table("semantic_tables", schema="rag")

    for idx in ("ix_messages_tenant", "ix_messages_session_created"):
        op.drop_index(idx, table_name="messages", schema="meta")
    op.drop_table("messages", schema="meta")

    for idx in ("ix_chat_sessions_updated_at", "ix_chat_sessions_tenant_user"):
        op.drop_index(idx, table_name="chat_sessions", schema="meta")
    op.drop_table("chat_sessions", schema="meta")

    op.drop_index("ix_users_tenant_id", table_name="users", schema="meta")
    op.drop_table("users", schema="meta")

    op.drop_table("tenants", schema="meta")
    # 故意 **不** drop 扩展（vector / pgcrypto），避免影响 init.sql 创建的演示数据。
