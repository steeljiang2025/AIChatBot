"""STE-20：text-embedding-v4 客户端封装。

字段集严格对齐 `.cursor/plans/...plan.md` §3.4.1 (5) 的「必踩坑」配置：

- chunk_size=10（百炼 v4 batch 上限；> 10 会被 DashScope 截断 / 报错）
- check_embedding_ctx_length=False（必须关。langchain 默认会用 tiktoken
  按 OpenAI 切分语义把 str 拆成 list[list[int]] 再发，DashScope 兼容
  接口收不到正确的 `input` 字段会回 `contents is neither str nor list
  of str` 的 400）
- dimensions=qwen_embedding_dim：必须与 RAG 表 `vector(1024)` 列对齐。
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """获取单例 text-embedding-v4 客户端。"""
    s = get_settings()
    return OpenAIEmbeddings(
        model=s.qwen_embedding_model,
        api_key=s.dashscope_api_key,
        base_url=s.qwen_base_url,
        dimensions=s.qwen_embedding_dim,
        chunk_size=10,
        check_embedding_ctx_length=False,
    )
