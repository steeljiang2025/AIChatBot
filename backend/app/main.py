"""FastAPI 应用入口。

Phase1 仅装载 health/version 路由，并完成 lifespan 钩子（启动期数据库探针）。
Phase3 起会在此处挂载 auth/sessions/chat/semantics 等业务路由。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import JWTAuthMiddleware
from app.db.base import biz_engine, dispose_engines, meta_engine, ping_engine

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.app_log_level)
    _logger.info("Starting %s v%s [env=%s]", settings.app_name, settings.app_version, settings.app_env)

    meta_ok = await ping_engine(meta_engine)
    biz_ok = await ping_engine(biz_engine)
    _logger.info("DB probe — meta=%s biz=%s", "ok" if meta_ok else "down", "ok" if biz_ok else "down")

    yield

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
    return app


app = create_app()
