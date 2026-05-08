"""STE-21：语义索引器（占位）。

职责：
1. 把 `SemanticTable` / `SemanticColumn` / `SemanticTerm` / `SemanticRelation`
   各自渲染成「卡片化文本」（人类可读、信息密集）。
2. 调 `app.llm.get_embeddings()` 批量 embed，每批 ≤ 10（百炼 v4 上限）。
3. 把向量写回各表的 `embedding` 列。

调用模式（用户决策：手动）：
- API: `POST /semantics/reindex` → 调 `reindex_tenant()`，
  对该租户的全部 4 张表做全量重建。
- 不在 CRUD 写入路径上做（避免 API 卡 200~500ms）。

实现见 commit 2。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

# 注意：from app.llm import get_embeddings 必须在模块顶部导入而非 lazy，
# 这样测试中 `monkeypatch.setattr("app.semantic.indexer.get_embeddings", ...)`
# 能命中本模块的引用（而不是去改 app.llm 的全局符号）。
from app.llm import get_embeddings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import (
        SemanticColumn,
        SemanticRelation,
        SemanticTable,
        SemanticTerm,
    )

__all__ = [
    "ReindexReport",
    "card_for_column",
    "card_for_relation",
    "card_for_table",
    "card_for_term",
    "get_embeddings",
    "reindex_tenant",
]


@dataclass(frozen=True, slots=True)
class ReindexReport:
    """全量重建结果。"""

    tables_reindexed: int
    columns_reindexed: int
    terms_reindexed: int
    relations_reindexed: int
    embeddings_called: int  # 实际向 LLM 发起的 batch 数（每批 ≤ 10）

    @property
    def total(self) -> int:
        return (
            self.tables_reindexed
            + self.columns_reindexed
            + self.terms_reindexed
            + self.relations_reindexed
        )


# ---------- Card builders（commit 2 实现） ----------


def card_for_table(*, display_name: str | None, table_name: str, description: str | None) -> str:
    """把表的元数据渲染成 embedding input。"""
    raise NotImplementedError


def card_for_column(
    *,
    table_name: str,
    column_name: str,
    display_name: str | None,
    data_type: str,
    business_meaning: str | None,
    description: str | None,
) -> str:
    """把列的元数据渲染成 embedding input。"""
    raise NotImplementedError


def card_for_term(*, term: str, definition: str | None, synonyms: list[str] | None) -> str:
    """把术语 + 同义词渲染成 embedding input。"""
    raise NotImplementedError


def card_for_relation(
    *,
    relation_type: str,
    from_table_name: str,
    to_table_name: str,
    description: str | None,
) -> str:
    """把表间关系渲染成 embedding input。"""
    raise NotImplementedError


# ---------- internal helpers（占位；测试用 monkeypatch 替换） ----------


async def _load_tenant_objects(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> tuple[
    list[SemanticTable],
    list[SemanticColumn],
    list[SemanticTerm],
    list[SemanticRelation],
]:
    """加载本租户所有 4 类语义对象（commit 2 实现真实查询）。"""
    raise NotImplementedError


# ---------- 编排入口（commit 2 实现） ----------


async def reindex_tenant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> ReindexReport:
    """对指定租户的全部 4 类语义对象做全量 embedding 重建。"""
    raise NotImplementedError
