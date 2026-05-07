"""异步 SQLAlchemy engine / sessionmaker。

- meta_engine：应用元数据库（读写）
- biz_engine：业务库连接（仅 SELECT，业务侧账号已限制 statement_timeout）

启动期 / 健康检查时会调用 `ping_engine` 做 `SELECT 1` 探针。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from app.core.config import get_settings

_logger = logging.getLogger(__name__)
_settings = get_settings()

meta_engine: Final[AsyncEngine] = create_async_engine(
    _settings.meta_db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

biz_engine: Final[AsyncEngine] = create_async_engine(
    _settings.biz_db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
    # 业务库默认拒绝隐式提交，进一步降低被误改的风险
    isolation_level="AUTOCOMMIT",
)

MetaSession: Final = async_sessionmaker(meta_engine, expire_on_commit=False, class_=AsyncSession)
BizSession: Final = async_sessionmaker(biz_engine, expire_on_commit=False, class_=AsyncSession)


async def ping_engine(engine: AsyncEngine) -> bool:
    """对指定 engine 做一次 `SELECT 1` 探针。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        _logger.warning("ping_engine failed url=%s err=%s", engine.url, exc)
        return False


async def dispose_engines() -> None:
    """应用关闭时释放连接池。"""
    await meta_engine.dispose()
    await biz_engine.dispose()


# FastAPI dependency 用法示例（Phase3 起在路由中使用）
async def get_meta_session() -> AsyncIterator[AsyncSession]:
    async with MetaSession() as session:
        yield session


async def get_biz_session() -> AsyncIterator[AsyncSession]:
    async with BizSession() as session:
        yield session
