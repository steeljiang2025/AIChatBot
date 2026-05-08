"""STE-21：语义混合检索（占位）。

打分公式（用户决策：weighted blend，α=0.3）：

    score = α × ts_rank + (1 - α) × (1 - cosine_distance)

其中：
- `ts_rank` 来自 `ts_rank_cd(tsv, plainto_tsquery('simple', :q))`，
  归一化到 [0, 1)
- `cosine_distance` 来自 pgvector `embedding <=> :q_vec`，∈ [0, 2]
- `(1 - cosine_distance)` 即 cosine similarity，∈ [-1, 1]，
  实战中嵌入向量 `text-embedding-v4` 都是单位长度，落 [0, 1] 区间

α 默认 0.3 → 向量为主，但保留全文匹配关键词的能力（防止
embedding 把"客户活跃度"切成模糊语义而漏掉精确字面命中）。

实现见 commit 2。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


HitType = Literal["table", "column", "term", "relation"]


@dataclass(frozen=True, slots=True)
class Hit:
    """混合检索单条结果。"""

    type: HitType
    id: uuid.UUID
    title: str
    snippet: str
    score: float


DEFAULT_ALPHA: float = 0.3
DEFAULT_TOP_K: int = 10


async def _run_hybrid_query(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int,
    types: tuple[HitType, ...] | None,
) -> list[dict]:
    """执行混合检索 SQL，返回 `{type, id, title, snippet, ts_rank, cosine_distance}`
    行集。SQL 在 commit 2 实现；测试用 monkeypatch 替换它。
    """
    raise NotImplementedError


async def search(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    alpha: float = DEFAULT_ALPHA,
    types: tuple[HitType, ...] | None = None,
) -> list[Hit]:
    """混合检索本租户的语义对象。

    Args:
        session: meta DB session（rag.semantic_* 与 meta.tenants 都在同一 PG）。
        tenant_id: 强制隔离。每条 SQL where 都带 tenant_id。
        query: 自然语言 query；空字符串视为「不过滤」（仅做向量打分）。
        top_k: 返回前 K 条。默认 10。
        alpha: 全文权重 ∈ [0, 1]，`α=0` 为纯向量，`α=1` 为纯全文。
        types: 限制仅返回某些类型；None 表示 4 类全召回。

    Returns:
        按 score 降序的 Hit 列表，长度 ≤ top_k。
    """
    raise NotImplementedError
