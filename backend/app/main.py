"""FastAPI 应用入口。

Phase3 起 lifespan 串起：
- DB probe（meta / biz）
- LangGraph 工作流装配（依赖 checkpointer schema）
- 业务侧路由：health / auth / sessions / semantics（chat 留给 STE-24）
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.semantics import router as semantics_router
from app.api.sessions import router as sessions_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import JWTAuthMiddleware
from app.db.base import (
    MetaSession,
    biz_engine,
    dispose_engines,
    meta_engine,
    ping_engine,
)
from app.graph.builder import build_graph
from app.graph.checkpointer import open_checkpointer

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _graph_lifespan(app: FastAPI, checkpoint_db_url: str):
    """LangGraph 工作流的子 lifespan。

    成功：app.state.graph = CompiledStateGraph，pool 在退出时自动关闭。
    失败：打 warning + app.state.graph = None；不阻塞应用启动，让其它
    路由（health / auth / sessions / semantics）仍可正常工作。
    """
    try:
        async with open_checkpointer(checkpoint_db_url) as cp:
            app.state.graph = build_graph(cp)
            _logger.info(
                "LangGraph 装配完成（checkpointer setup OK，schema=checkpoint）"
            )
            yield
    except Exception as exc:
        _logger.warning(
            "LangGraph 不装配（checkpointer 启动失败）: %s", exc, exc_info=True
        )
        app.state.graph = None
        yield


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.app_log_level)
    _logger.info(
        "Starting %s v%s [env=%s]",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )

    meta_ok = await ping_engine(meta_engine)
    biz_ok = await ping_engine(biz_engine)
    _logger.info(
        "DB probe — meta=%s biz=%s",
        "ok" if meta_ok else "down",
        "ok" if biz_ok else "down",
    )

    # STE-21 / STE-23 节点共享：semantics router 已用 app.state.business_engine
    # 探针；graph 节点 retrieve 用 meta_session_factory；sql_exec 用 biz_engine。
    app.state.business_engine = biz_engine
    app.state.meta_session_factory = MetaSession
    app.state.graph = None  # 默认 None，graph_lifespan 成功才覆盖

    if meta_ok:
        async with _graph_lifespan(app, settings.checkpoint_db_url):
            try:
                yield
            finally:
                _logger.info("Shutting down ...")
    else:
        _logger.warning("meta DB down — 跳过 LangGraph 装配，应用降级启动")
        try:
            yield
        finally:
            _logger.info("Shutting down ...")

    await dispose_engines()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 中间件加载顺序：FastAPI 按 LIFO 包装 → 后 add 的位于外层。
    # 因此先 add JWT、再 add CORS，运行顺序是 CORS → JWT → handler，
    # CORS preflight (OPTIONS) 由 CORSMiddleware 直接回复，不会被 JWT 拦。
    app.add_middleware(JWTAuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(sessions_router)
    app.include_router(semantics_router)
    app.include_router(chat_router)
    return app


app = create_app()
