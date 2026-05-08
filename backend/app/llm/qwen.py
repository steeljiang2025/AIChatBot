"""STE-20：Qwen3 Chat 客户端封装。

字段集严格对齐 `.cursor/plans/...plan.md` §3.4.1 (6)。其它参数一律不传，
避免 langchain 默认值随版本漂移。
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_chat_llm() -> ChatOpenAI:
    """获取单例 Qwen3 Chat 客户端。

    单例语义说明：
    - `@lru_cache(maxsize=1)` 让一个进程内复用同一个 ChatOpenAI 实例，
      避免每次调用都重新做 langchain client 的反射 / 校验（~50ms）。
    - 测试时调 `get_chat_llm.cache_clear()` 重置。
    - 配置（settings）改变时也需要 `cache_clear()`，但运行期 settings
      本身也是 `@lru_cache`，正常不会变。
    """
    s = get_settings()
    return ChatOpenAI(
        model=s.qwen_chat_model,
        api_key=s.dashscope_api_key,
        base_url=s.qwen_base_url,
        temperature=s.qwen_chat_temperature,
        max_tokens=s.qwen_chat_max_tokens,
        timeout=s.qwen_chat_timeout,
        max_retries=s.qwen_chat_max_retries,
    )
