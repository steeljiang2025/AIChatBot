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
    # 以下 4 个字段允许通过 .env 覆盖；默认值与
    # `.cursor/plans/...plan.md` §3.4.1 (6) 已 probe 验证的字段集对齐。
    qwen_chat_temperature: float = Field(default=0.2)
    qwen_chat_max_tokens: int = Field(default=2048)
    qwen_chat_timeout: int = Field(default=30)
    qwen_chat_max_retries: int = Field(default=2)

    # ---- JWT（Phase3 才会用到） ----
    jwt_secret: str = Field(default="change-me-to-a-long-random-string")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=120)
    jwt_refresh_expire_days: int = Field(
        default=14,
        description="refresh token 有效期（天）。STE-18 起用；过期后用户需重新 /auth/login。",
    )

    # ---- SQL 安全（STE-22 起用） ----
    sql_max_rows: int = Field(
        default=5000,
        description=(
            "自动 LIMIT 上限：sql_safety.validator.enforce_limit 会把超过此值"
            "的 LIMIT 截断到此值，无 LIMIT 则注入此值。生产推荐 ≤ 10000。"
        ),
    )

    # ---- LangGraph（STE-23 起用） ----
    graph_max_retries: int = Field(
        default=2,
        description=(
            "sql_validate 失败回到 sql_gen 的最大重试次数。retries < 上限"
            "时回 sql_gen 让 LLM 改写；达到上限走失败分支由 summarize 报错。"
        ),
    )
    sql_exec_timeout_ms: int = Field(
        default=30000,
        description="sql_exec 节点对业务库 SQL 的 statement_timeout（毫秒）。",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def checkpoint_db_url(self) -> str:
        """从 meta_db_url 派生 langgraph-checkpoint-postgres 用 URL。

        plan §3.7.1 (1) 必坑：
        - 去掉 `+psycopg`（langgraph 走原生 psycopg3，不是 SQLAlchemy dialect）
        - 加 `?options=-c%20search_path%3Dcheckpoint`，绕过 PG 15+ 起 app_user
          在 public schema 没有 CREATE 权限的问题。
        - 已有 query string 时丢弃（避免 ?A&B 串接出 ??）。
        """
        return _derive_checkpoint_url(self.meta_db_url)


def _derive_checkpoint_url(meta_url: str) -> str:
    """meta_db_url → langgraph 用 checkpoint URL。

    输入示例：`postgresql+psycopg://app_user:pwd@host:5432/db?x=1`
    输出示例：`postgresql://app_user:pwd@host:5432/db?options=-c%20search_path%3Dcheckpoint`
    """
    base = meta_url
    if base.startswith("postgresql+psycopg://"):
        base = "postgresql://" + base[len("postgresql+psycopg://") :]
    base = base.split("?", 1)[0]
    return f"{base}?options=-c%20search_path%3Dcheckpoint"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例配置；测试中可调用 get_settings.cache_clear() 重置。"""
    return Settings()
