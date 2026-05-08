"""STE-20：LLM 客户端单元测试。

策略：
- 不打外网。用 monkeypatch 把 ChatOpenAI / OpenAIEmbeddings 类整体替换
  为捕获参数的 _Fake，断言传入参数严格对齐
  `.cursor/plans/...plan.md` §3.4.1 (5)/(6) 的字段规范。
- get_chat_llm() / get_embeddings() 是 lru_cache 单例：每个测试前 cache_clear；
  并独立测一条「同实例返回」契约。
- settings 字段注入：通过 get_settings.cache_clear() + monkeypatch 环境变量
  覆盖，验证 settings 的 4 个 chat 字段确实被读到。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import get_settings
from app.llm import LLMAuthError, LLMError, LLMRateLimitError, LLMTimeoutError, embedding, qwen

# ---- 公共：lru_cache 重置 ----


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    qwen.get_chat_llm.cache_clear()
    embedding.get_embeddings.cache_clear()
    get_settings.cache_clear()
    yield
    qwen.get_chat_llm.cache_clear()
    embedding.get_embeddings.cache_clear()
    get_settings.cache_clear()


# ---- ChatOpenAI 参数对齐 §3.4.1 (6) ----


def test_get_chat_llm_passes_required_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """ChatOpenAI 构造时必须传齐 §3.4.1 (6) 的字段集（默认值对齐）。"""
    captured: dict[str, Any] = {}

    class _FakeChat:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.llm.qwen.ChatOpenAI", _FakeChat)
    # 配死一个 fake key，避免读到空字符串触发 langchain 校验
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")

    qwen.get_chat_llm()

    # 模型 / 鉴权 / 端点：与 settings 对齐
    assert captured["model"] == "qwen3-max"
    assert captured["api_key"] == "fake-key"
    assert captured["base_url"].endswith("/compatible-mode/v1")

    # §3.4.1 (6) 写死的 4 个调参字段（默认值）
    assert captured["temperature"] == pytest.approx(0.2)
    assert captured["max_tokens"] == 2048
    assert captured["timeout"] == 30
    assert captured["max_retries"] == 2


def test_get_chat_llm_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """lru_cache 契约：同一进程内多次调用返回同一实例。"""
    monkeypatch.setattr("app.llm.qwen.ChatOpenAI", lambda **_: object())
    a = qwen.get_chat_llm()
    b = qwen.get_chat_llm()
    assert a is b


def test_get_chat_llm_settings_overrides_pick_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """settings 中 chat 调参字段被覆盖后，下次构造应反映新值。"""
    captured: dict[str, Any] = {}

    class _FakeChat:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.llm.qwen.ChatOpenAI", _FakeChat)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")
    monkeypatch.setenv("QWEN_CHAT_TEMPERATURE", "0.7")
    monkeypatch.setenv("QWEN_CHAT_MAX_TOKENS", "512")
    monkeypatch.setenv("QWEN_CHAT_TIMEOUT", "60")
    monkeypatch.setenv("QWEN_CHAT_MAX_RETRIES", "5")

    qwen.get_chat_llm()

    assert captured["temperature"] == pytest.approx(0.7)
    assert captured["max_tokens"] == 512
    assert captured["timeout"] == 60
    assert captured["max_retries"] == 5


# ---- OpenAIEmbeddings 参数对齐 §3.4.1 (5) ----


def test_get_embeddings_passes_required_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAIEmbeddings 必须按 §3.4.1 (5) 的「必踩坑」字段集构造。"""
    captured: dict[str, Any] = {}

    class _FakeEmb:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.llm.embedding.OpenAIEmbeddings", _FakeEmb)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")

    embedding.get_embeddings()

    assert captured["model"] == "text-embedding-v4"
    assert captured["api_key"] == "fake-key"
    assert captured["base_url"].endswith("/compatible-mode/v1")
    # 必踩坑 1：dimensions 与 RAG 向量列 vector(1024) 对齐
    assert captured["dimensions"] == 1024
    # 必踩坑 2：百炼 v4 batch 上限
    assert captured["chunk_size"] == 10
    # 必踩坑 3：必须关，否则会触发 400
    assert captured["check_embedding_ctx_length"] is False


def test_get_embeddings_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.llm.embedding.OpenAIEmbeddings", lambda **_: object())
    a = embedding.get_embeddings()
    b = embedding.get_embeddings()
    assert a is b


# ---- 错误异常树契约 ----


def test_llm_timeout_is_subclass_of_llm_error() -> None:
    assert issubclass(LLMTimeoutError, LLMError)


def test_llm_rate_limit_is_subclass_of_llm_error() -> None:
    assert issubclass(LLMRateLimitError, LLMError)


def test_llm_auth_is_subclass_of_llm_error() -> None:
    assert issubclass(LLMAuthError, LLMError)
