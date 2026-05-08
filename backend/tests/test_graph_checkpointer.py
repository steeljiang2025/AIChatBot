"""STE-23：checkpointer 模块测试（不真连 PG）。

只覆盖 URL 派生（plan §3.7.1 (1) 已 probe 验证的硬约束）。
真连 PG 的 setup() 由 main.py lifespan 在启动时执行；本任务的 verify
通过手动 probe 脚本完成（commit 2 提供）。
"""

from __future__ import annotations

import pytest

from app.core.config import _derive_checkpoint_url
from app.graph.checkpointer import derive_checkpoint_db_url

# ---- core.config._derive_checkpoint_url（兼容 graph.checkpointer 模块函数）----


@pytest.mark.parametrize(
    "input_url, expected",
    [
        # 标准 SQLAlchemy URL（含 +psycopg）
        (
            "postgresql+psycopg://app_user:pwd@host:5432/aichatbot",
            "postgresql://app_user:pwd@host:5432/aichatbot"
            "?options=-c%20search_path%3Dcheckpoint",
        ),
        # 已带 query string —— 应被丢弃，避免 ?A&B 串接出 ??
        (
            "postgresql+psycopg://u:p@h:5432/db?sslmode=require",
            "postgresql://u:p@h:5432/db"
            "?options=-c%20search_path%3Dcheckpoint",
        ),
        # 无 +psycopg 前缀（已是 langgraph 风格）
        (
            "postgresql://u:p@h:5432/db",
            "postgresql://u:p@h:5432/db"
            "?options=-c%20search_path%3Dcheckpoint",
        ),
    ],
)
def test_derive_checkpoint_url_via_config(input_url: str, expected: str) -> None:
    assert _derive_checkpoint_url(input_url) == expected


def test_graph_checkpointer_module_function_matches_config() -> None:
    """`graph.checkpointer.derive_checkpoint_db_url` 应与 config 中的派生逻辑一致。"""
    url = "postgresql+psycopg://app_user:pwd@localhost:5432/aichatbot"
    assert derive_checkpoint_db_url(url) == _derive_checkpoint_url(url)


def test_derive_url_strips_psycopg_and_adds_search_path() -> None:
    out = derive_checkpoint_db_url(
        "postgresql+psycopg://u:p@h:5432/db"
    )
    assert "+psycopg" not in out
    assert "search_path%3Dcheckpoint" in out
    assert out.startswith("postgresql://")


def test_settings_checkpoint_db_url_property() -> None:
    """Settings.checkpoint_db_url 应基于 meta_db_url 派生。"""
    from app.core.config import Settings

    s = Settings(
        meta_db_url=(
            "postgresql+psycopg://app_user:pwd@localhost:5432/aichatbot"
        )
    )
    assert s.checkpoint_db_url == (
        "postgresql://app_user:pwd@localhost:5432/aichatbot"
        "?options=-c%20search_path%3Dcheckpoint"
    )
