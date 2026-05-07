-- =====================================================================
-- AIChatBot PostgreSQL initialization (SQL part)
-- 该脚本由 Postgres 镜像的 entrypoint 在首次启动时以超级用户 postgres 执行
-- 业务账号(app_user / biz_ro)由配套 init-roles.sh 创建（密码取自环境变量）
-- =====================================================================

-- 1) 启用必需扩展（superuser 执行；app_user 后续无需 CREATE EXTENSION 权限）
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()，UUID 主键 server_default 用

-- 2) 划分逻辑 schema
CREATE SCHEMA IF NOT EXISTS meta;        -- 用户/租户/会话/消息
CREATE SCHEMA IF NOT EXISTS rag;         -- 语义元数据 + 向量索引
CREATE SCHEMA IF NOT EXISTS biz;         -- 业务数据（NL2SQL 查询的目标）
CREATE SCHEMA IF NOT EXISTS checkpoint;  -- LangGraph PostgresSaver

COMMENT ON SCHEMA meta IS 'application metadata: tenants/users/chat sessions/messages';
COMMENT ON SCHEMA rag IS 'semantic metadata and vector indexes for RAG';
COMMENT ON SCHEMA biz IS 'business data, target of NL2SQL queries';
COMMENT ON SCHEMA checkpoint IS 'LangGraph AsyncPostgresSaver checkpoints';

-- 3) Phase1 占位的最小业务表，用于联通验证；Phase3 之后将由 Alembic 与导入脚本接管
CREATE TABLE IF NOT EXISTS biz.sample_ping (
    id          BIGSERIAL PRIMARY KEY,
    note        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO biz.sample_ping (note)
VALUES ('hello pgvector')
ON CONFLICT DO NOTHING;
