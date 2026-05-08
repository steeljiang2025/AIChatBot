"""STE-23：AsyncPostgresSaver 工厂。

按 plan §3.7.1 (1)/(3) 已 probe 验证的姿势构造：
- URL：从 meta_db_url 派生（去掉 +psycopg、加 search_path=checkpoint）
- Pool：AsyncConnectionPool(open=False) + 显式 await pool.open()
- 连接 kwargs：autocommit=True + prepare_threshold=0
- Serde：JsonPlusSerializer 默认构造
  注：plan §3.7.1 提到的 `allowed_objects='messages'` 是 langgraph 未来
  版本的待定 API；当前 langgraph-checkpoint 4.0.x 实际接受的是
  `allowed_json_modules` / `allowed_msgpack_modules`，不接受
  `allowed_objects`。`langgraph.cache.base.__init__` 里的 deprecation
  warning 由 langgraph 自身内部代码触发，与外部传参无关。
- setup() 自治建表（alembic 不接管这 4 张表）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from app.core.config import _derive_checkpoint_url

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def derive_checkpoint_db_url(meta_db_url: str) -> str:
    """meta_db_url → langgraph 用 checkpoint URL。

    包装 `app.core.config._derive_checkpoint_url`，让 graph 模块可以独立
    调用 derive 逻辑（脚本 / 测试），同时不引入循环依赖。
    """
    return _derive_checkpoint_url(meta_db_url)


@asynccontextmanager
async def open_checkpointer(
    checkpoint_db_url: str,
) -> AsyncIterator[AsyncPostgresSaver]:
    """构造并启动一个 AsyncPostgresSaver。

    使用方式（FastAPI lifespan）：
        async with open_checkpointer(settings.checkpoint_db_url) as cp:
            app.state.graph = build_graph(cp)
            yield
    """
    # 延迟 import，避免单测加载本模块时强依赖 psycopg-pool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from psycopg_pool import AsyncConnectionPool

    async with AsyncConnectionPool(
        conninfo=checkpoint_db_url,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,  # plan §3.7.1 (3) 必坑：psycopg-pool 3.3+ 起必须 False
    ) as pool:
        await pool.open()  # 显式打开
        cp = AsyncPostgresSaver(
            pool,
            serde=JsonPlusSerializer(),
        )
        await cp.setup()
        yield cp
