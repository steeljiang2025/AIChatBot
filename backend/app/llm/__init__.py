"""LLM 客户端 + Prompt 模板包。

对外稳定接口：
- get_chat_llm() / get_embeddings()：lru_cache 单例
- render_prompt(name, **vars)：渲染 prompts/*.j2 模板
- LLMError 及子类：统一的可读异常树
"""

from app.llm.embedding import get_embeddings
from app.llm.errors import (
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from app.llm.prompts import render_prompt
from app.llm.qwen import get_chat_llm

__all__ = [
    "LLMAuthError",
    "LLMError",
    "LLMRateLimitError",
    "LLMServerError",
    "LLMTimeoutError",
    "get_chat_llm",
    "get_embeddings",
    "render_prompt",
]
