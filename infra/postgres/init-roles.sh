#!/usr/bin/env bash
# =====================================================================
# 创建应用账号（app_user）与业务库只读账号（biz_ro），密码取环境变量
# 该脚本由 Postgres 镜像的 entrypoint 首次启动时以超级用户身份执行
# =====================================================================
set -euo pipefail

APP_DB_PASSWORD="${APP_DB_PASSWORD:-app_pwd_change_me}"
BIZ_RO_PASSWORD="${BIZ_RO_PASSWORD:-biz_ro_pwd_change_me}"
DB_NAME="${POSTGRES_DB:-aichatbot}"

psql -v ON_ERROR_STOP=1 \
     --username "${POSTGRES_USER:-postgres}" \
     --dbname  "${DB_NAME}" <<-EOSQL
    -- 应用账号
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD '${APP_DB_PASSWORD}';
      ELSE
        ALTER ROLE app_user LOGIN PASSWORD '${APP_DB_PASSWORD}';
      END IF;

      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'biz_ro') THEN
        CREATE ROLE biz_ro LOGIN PASSWORD '${BIZ_RO_PASSWORD}';
      ELSE
        ALTER ROLE biz_ro LOGIN PASSWORD '${BIZ_RO_PASSWORD}';
      END IF;
    END\$\$;

    -- 应用账号：meta / rag / checkpoint 全部权限；biz 用于 schema 抽取与导入种子数据
    GRANT USAGE, CREATE ON SCHEMA meta, rag, checkpoint, biz TO app_user;

    GRANT ALL ON ALL TABLES    IN SCHEMA meta, rag, checkpoint, biz TO app_user;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA meta, rag, checkpoint, biz TO app_user;

    ALTER DEFAULT PRIVILEGES IN SCHEMA meta, rag, checkpoint, biz
        GRANT ALL ON TABLES TO app_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA meta, rag, checkpoint, biz
        GRANT ALL ON SEQUENCES TO app_user;

    -- 只读账号：仅 biz schema 的 SELECT，且会话强制只读 + 限时
    GRANT USAGE ON SCHEMA biz TO biz_ro;
    GRANT SELECT ON ALL TABLES IN SCHEMA biz TO biz_ro;
    ALTER DEFAULT PRIVILEGES IN SCHEMA biz
        GRANT SELECT ON TABLES TO biz_ro;

    ALTER ROLE biz_ro SET default_transaction_read_only            = on;
    ALTER ROLE biz_ro SET statement_timeout                        = '15s';
    ALTER ROLE biz_ro SET idle_in_transaction_session_timeout      = '15s';
EOSQL

echo "[init-roles] app_user / biz_ro created or updated"
