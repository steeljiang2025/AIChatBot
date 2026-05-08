"""应用全局配置：从环境变量 / .env 加载。

Phase1 仅声明骨架需要的字段；后续 Phase3 会扩展 LLM/JWT 等细节字段。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 后端独立项目：仅从 backend/.env 加载（容器内由 compose 通过 env_file 注入；
# 进程内已存在的环境变量优先级高于本文件）
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 应用 ----
    app_env: str = Field(default="dev")
    app_log_level: str = Field(default="INFO")
    app_name: str = Field(default="AIChatBot")
    app_version: str = Field(default="0.1.0")

    # ---- 数据库 ----
    meta_db_url: str = Field(
        default="postgresql+psycopg://app_user:app_pwd_change_me@localhost:5432/aichatbot",
        description="应用元数据库（用户/会话/语义等）",
    )
    biz_db_url: str = Field(
        default="postgresql+psycopg://biz_ro:biz_ro_pwd_change_me@localhost:5432/aichatbot",
        description="业务库连接（只读账号，用于跑 LLM 生成的 SQL）",
    )

    # ---- CORS ----
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="逗号分隔的 CORS Origin 白名单",
    )

    # ---- LLM（Phase3 才会用到，提前占位避免漂移） ----
    dashscope_api_key: str = Field(default="")
    qwen_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    qwen_chat_model: str = Field(default="qwen3-max")
    qwen_embedding_model: str = Field(default="text-embedding-v4")
    qwen_embedding_dim: int = Field(default=1024)

    # ---- JWT（Phase3 才会用到） ----
    jwt_secret: str = Field(default="change-me-to-a-long-random-string")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=120)
    jwt_refresh_expire_days: int = Field(
        default=14,
        description="refresh token 有效期（天）。STE-18 起用；过期后用户需重新 /auth/login。",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例配置；测试中可调用 get_settings.cache_clear() 重置。"""
    return Settings()
