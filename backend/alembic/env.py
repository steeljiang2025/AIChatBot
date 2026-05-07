"""Alembic 环境脚本（async + 多 schema + 排除 langgraph checkpoint）。

约束（已写入 plan.md §3.7.1）：
1. **绝不接管 `checkpoint` schema** —— 那 4 张表归 `langgraph-checkpoint-postgres`
   的 `AsyncPostgresSaver.setup()` 自治。
2. **不接管 `biz` schema** —— 业务表由抽取/导入脚本管理，alembic 只读语义层。
3. `alembic_version` 表落 `meta` schema，避免污染 public。
4. URL 优先环境变量 `META_DB_URL`，本地兜底 `Settings.meta_db_url`。
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# 让 alembic 进程能 import 到 `app.*`：
# 必须先把 backend 目录注入 sys.path 再 import 模型，否则 `python -m alembic …`
# 直接运行时找不到 `app` 包。E402 在此是有意为之。
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db.models import Base  # noqa: E402  触发所有模型注册到 Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# 连接 URL 解析
# ---------------------------------------------------------------------------
def _resolve_database_url() -> str:
    url = os.getenv("META_DB_URL")
    if url:
        return url
    # 兜底：本地直跑时从 Settings 读
    from app.core.config import get_settings  # 延迟 import，避免污染 alembic 子命令

    return get_settings().meta_db_url


# ---------------------------------------------------------------------------
# 对象过滤：保护 checkpoint / biz schema
# ---------------------------------------------------------------------------
EXCLUDED_SCHEMAS = {"checkpoint", "biz"}


def include_object(object_, name, type_, reflected, compare_to):
    """阻断 alembic 对受保护 schema 的任何 diff/迁移操作。

    - `table` / `index` / `unique_constraint` / `foreign_key_constraint` 等都带
      `.schema` 属性；落在 EXCLUDED_SCHEMAS 内的一律忽略。
    - reflected=True（DB 中存在但 metadata 中没有）的对象，如果在受保护 schema
      也要忽略，否则 autogenerate 会 drop 掉 langgraph 自管的 4 张表。
    """
    schema = getattr(object_, "schema", None)
    if schema in EXCLUDED_SCHEMAS:
        return False
    return True


def include_name(name, type_, parent_names):
    """`include_schemas=True` 时由 alembic 用此回调决定是否反射某个 schema。

    我们只关心 `meta` 与 `rag`；`public` / `checkpoint` / `biz` 一律跳过。
    """
    if type_ == "schema":
        return name in {"meta", "rag"}
    return True


# ---------------------------------------------------------------------------
# offline / online 入口
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """生成纯 SQL（不连库）。CI/审计用。"""
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        include_name=include_name,
        version_table="alembic_version",
        version_table_schema="meta",
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        include_name=include_name,
        version_table="alembic_version",
        version_table_schema="meta",
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """连真实库执行（容器内/本地 dev）。"""
    cfg_section = config.get_section(config.config_ini_section, {}) or {}
    cfg_section["sqlalchemy.url"] = _resolve_database_url()

    connectable = async_engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
