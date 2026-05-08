"""STE-20：text-embedding-v4 客户端封装（占位）。

实现见 commit 2；本提交先暴露符号让测试 import 不爆。
封装契约严格对齐 `.cursor/plans/...plan.md` §3.4.1 (5) 的「必踩坑」配置：

- chunk_size=10（百炼 v4 batch 上限）
- check_embedding_ctx_length=False（必须关，否则 langchain 默认 tiktoken
  切分模式会触发 `contents is neither str nor list of str` 400 错误）
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """获取单例 text-embedding-v4 客户端。"""
    raise NotImplementedError
