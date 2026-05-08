"""STE-20：Qwen3 Chat 客户端封装（占位）。

实现见 commit 2；本提交先暴露符号让测试 import 不爆。
封装契约严格对齐 `.cursor/plans/...plan.md` §3.4.1 (6)。
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI


@lru_cache(maxsize=1)
def get_chat_llm() -> ChatOpenAI:
    """获取单例 Qwen3 Chat 客户端。

    必须严格对齐 §3.4.1 (6) 的字段集（model / api_key / base_url /
    temperature / max_tokens / timeout / max_retries），其它参数一律不传，
    避免 langchain 默认值漂移。
    """
    raise NotImplementedError
