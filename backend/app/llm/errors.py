"""STE-20：LLM 客户端可读异常封装。

把 openai SDK / langchain / httpx 的低层异常转译为业务侧统一异常树，
让上层路由、LangGraph 节点对失败语义有稳定契约：是该重试、该降级、
还是该向用户回错。
"""

from __future__ import annotations


class LLMError(Exception):
    """LLM 调用失败的根异常。"""


class LLMTimeoutError(LLMError):
    """请求超时（连接/读 timeout）。"""


class LLMRateLimitError(LLMError):
    """被服务端限流（HTTP 429）。"""


class LLMAuthError(LLMError):
    """API key 无效或权限不足（HTTP 401/403）。"""


class LLMServerError(LLMError):
    """服务端 5xx。"""


__all__ = [
    "LLMAuthError",
    "LLMError",
    "LLMRateLimitError",
    "LLMServerError",
    "LLMTimeoutError",
]
