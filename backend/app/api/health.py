"""健康检查与版本路由。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.base import biz_engine, meta_engine, ping_engine

router = APIRouter(tags=["health"])


class DbStatus(BaseModel):
    meta: str
    biz: str


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str
    db: DbStatus


class VersionResponse(BaseModel):
    name: str
    version: str
    env: str


@router.get("/health", response_model=HealthResponse, summary="后端 + 数据库健康探针")
async def health() -> HealthResponse:
    settings = get_settings()
    meta_ok = await ping_engine(meta_engine)
    biz_ok = await ping_engine(biz_engine)
    overall = "ok" if meta_ok and biz_ok else "degraded"
    return HealthResponse(
        status=overall,
        version=settings.app_version,
        env=settings.app_env,
        db=DbStatus(meta="ok" if meta_ok else "down", biz="ok" if biz_ok else "down"),
    )


@router.get("/version", response_model=VersionResponse, summary="版本信息")
async def version() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(name=settings.app_name, version=settings.app_version, env=settings.app_env)
