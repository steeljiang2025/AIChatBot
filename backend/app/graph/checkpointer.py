"""STE-23：AsyncPostgresSaver 工厂（占位）。

模块职责（commit 2 实现）：
- `derive_checkpoint_db_url(meta_db_url) -> str`
  从 `meta_db_url` 派生 langgraph 用的 checkpoint URL；详见 plan §3.7.1 (1)。
- `open_checkpointer(checkpoint_db_url) -> AsyncContextManager[AsyncPostgresSaver]`
  按 plan §3.7.1 (3) 的 Pool 姿势构造 AsyncPostgresSaver；
  yield 一个已 setup() 完毕的 checkpointer。

测试只覆盖 URL 派生（纯字符串），不真连 PG（CI 友好）。
真连 PG 的 setup() 由 main.py lifespan 在启动时执行。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def derive_checkpoint_db_url(meta_db_url: str) -> str:
    """meta_db_url → langgraph 用 checkpoint URL。

    实现等价于 `app.core.config._derive_checkpoint_url`，本函数把派生逻辑
    暴露给 graph 模块独立使用（测试 / 脚本场景），避免循环依赖。
    """
    raise NotImplementedError


@asynccontextmanager
async def open_checkpointer(
    checkpoint_db_url: str,
) -> AsyncIterator["AsyncPostgresSaver"]:
    """构造并启动一个 AsyncPostgresSaver。

    yield 之前完成：
    - AsyncConnectionPool(open=False) + 显式 await pool.open()
    - kwargs={'autocommit': True, 'prepare_threshold': 0}
    - JsonPlusSerializer(allowed_objects='messages')
    - await cp.setup()

    yield 之后退出 with 块时关闭 pool。
    """
    raise NotImplementedError
    yield  # pragma: no cover  -- 仅用于类型推断；占位实现先 raise
