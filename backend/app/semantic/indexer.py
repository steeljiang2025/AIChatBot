"""STE-21：语义索引器。

职责：
1. 把 `SemanticTable` / `SemanticColumn` / `SemanticTerm` / `SemanticRelation`
   各自渲染成「卡片化文本」（人类可读、信息密集）。
2. 调 `app.llm.get_embeddings()` 批量 embed，每批 ≤ 10（百炼 v4 上限）。
3. 把向量写回各表的 `embedding` 列。

调用模式（用户决策：手动）：
- API: `POST /semantics/reindex` → 调 `reindex_tenant()`，
  对该租户的全部 4 张表做全量重建。
- 不在 CRUD 写入路径上做（避免 API 卡 200~500ms）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

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


# 百炼 text-embedding-v4 单批上限 10
_EMBED_BATCH_SIZE: int = 10


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


# ---------- Card builders ----------


def card_for_table(
    *, display_name: str | None, table_name: str, description: str | None
) -> str:
    """把表的元数据渲染成 embedding input。"""
    parts: list[str] = []
    if display_name:
        parts.append(f"表显示名: {display_name}")
    parts.append(f"表名: {table_name}")
    if description:
        parts.append(f"描述: {description}")
    return " | ".join(parts)


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
    parts: list[str] = [f"表: {table_name}", f"列名: {column_name}"]
    if display_name:
        parts.append(f"显示名: {display_name}")
    parts.append(f"类型: {data_type}")
    if business_meaning:
        parts.append(f"业务含义: {business_meaning}")
    if description:
        parts.append(f"描述: {description}")
    return " | ".join(parts)


def card_for_term(
    *, term: str, definition: str | None, synonyms: list[str] | None
) -> str:
    """把术语 + 同义词渲染成 embedding input。"""
    parts: list[str] = [f"术语: {term}"]
    if definition:
        parts.append(f"定义: {definition}")
    if synonyms:
        parts.append(f"同义词: {', '.join(synonyms)}")
    return " | ".join(parts)


def card_for_relation(
    *,
    relation_type: str,
    from_table_name: str,
    to_table_name: str,
    description: str | None,
) -> str:
    """把表间关系渲染成 embedding input。"""
    parts: list[str] = [
        f"关系: {relation_type}",
        f"源表: {from_table_name}",
        f"目标表: {to_table_name}",
    ]
    if description:
        parts.append(f"描述: {description}")
    return " | ".join(parts)


def _flatten_synonyms(raw: Any) -> list[str] | None:
    """把 ORM `synonyms` (JSONB) 字段抹平成 list[str] 供 card_for_term 使用。

    支持两种 JSONB 形态：
    - `["a", "b"]`：直接 list；
    - `{"alts": ["a", "b"], "zh": "x"}`：dict，把所有 string / list[string] 值拍平。
    其它形态返回 None。
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        out = [str(x) for x in raw if x is not None]
        return out or None
    if isinstance(raw, dict):
        out: list[str] = []
        for v in raw.values():
            if isinstance(v, list):
                out.extend(str(x) for x in v if x is not None)
            elif isinstance(v, str):
                out.append(v)
        return out or None
    return None


# ---------- internal helpers ----------


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
    """加载本租户所有 4 类语义对象。

    relations 用 `selectinload` 预拉 from_table / to_table，避免渲染卡片时 N+1。
    """
    from app.db.models import (
        SemanticColumn,
        SemanticRelation,
        SemanticTable,
        SemanticTerm,
    )

    tables_res = await session.execute(
        select(SemanticTable).where(SemanticTable.tenant_id == tenant_id)
    )
    tables = list(tables_res.scalars().all())

    cols_res = await session.execute(
        select(SemanticColumn)
        .where(SemanticColumn.tenant_id == tenant_id)
        .options(selectinload(SemanticColumn.table))
    )
    columns = list(cols_res.scalars().all())

    terms_res = await session.execute(
        select(SemanticTerm).where(SemanticTerm.tenant_id == tenant_id)
    )
    terms = list(terms_res.scalars().all())

    rels_res = await session.execute(
        select(SemanticRelation).where(SemanticRelation.tenant_id == tenant_id)
    )
    relations = list(rels_res.scalars().all())

    # relations 没建到 SemanticTable 的 ORM 关系上（避免 mappers 复杂），
    # 用一次性 lookup 把 from_table_name / to_table_name 算出来挂在临时属性。
    table_by_id = {t.id: t for t in tables}
    # 兜底：relations 里引用的表 id 不在本批 tables 里时，再单查
    missing_ids: set[uuid.UUID] = set()
    for r in relations:
        for tid in (r.from_table_id, r.to_table_id):
            if tid not in table_by_id:
                missing_ids.add(tid)
    if missing_ids:
        extra_res = await session.execute(
            select(SemanticTable).where(SemanticTable.id.in_(missing_ids))
        )
        for t in extra_res.scalars().all():
            table_by_id[t.id] = t
    for r in relations:
        from_t = table_by_id.get(r.from_table_id)
        to_t = table_by_id.get(r.to_table_id)
        # 临时属性，仅本进程访问，不入库
        r.from_table_name_for_card = (  # type: ignore[attr-defined]
            from_t.table_name if from_t is not None else "?"
        )
        r.to_table_name_for_card = (  # type: ignore[attr-defined]
            to_t.table_name if to_t is not None else "?"
        )

    return tables, columns, terms, relations


# ---------- 编排入口 ----------


async def reindex_tenant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> ReindexReport:
    """对指定租户的全部 4 类语义对象做全量 embedding 重建。

    步骤：
    1. 加载 4 类对象（_load_tenant_objects）。
    2. 为每个对象渲染 card 文本，组成 (obj, text) 列表。
    3. 按 _EMBED_BATCH_SIZE=10 切批，调 LLM aembed_documents，
       结果写回 obj.embedding。
    4. session.commit()。
    """
    tables, columns, terms, relations = await _load_tenant_objects(
        session, tenant_id=tenant_id
    )

    items: list[tuple[Any, str]] = []
    for t in tables:
        items.append(
            (
                t,
                card_for_table(
                    display_name=t.display_name,
                    table_name=t.table_name,
                    description=t.description,
                ),
            )
        )
    for c in columns:
        # _FakeColumn 在测试里用 table_name_for_card 模拟 ORM relationship
        table_name = (
            getattr(c, "table_name_for_card", None)
            or getattr(getattr(c, "table", None), "table_name", "?")
        )
        items.append(
            (
                c,
                card_for_column(
                    table_name=table_name,
                    column_name=c.column_name,
                    display_name=c.display_name,
                    data_type=c.data_type,
                    business_meaning=c.business_meaning,
                    description=c.description,
                ),
            )
        )
    for tm in terms:
        items.append(
            (
                tm,
                card_for_term(
                    term=tm.term,
                    definition=tm.definition,
                    synonyms=_flatten_synonyms(tm.synonyms),
                ),
            )
        )
    for r in relations:
        from_name = getattr(r, "from_table_name_for_card", "?")
        to_name = getattr(r, "to_table_name_for_card", "?")
        items.append(
            (
                r,
                card_for_relation(
                    relation_type=r.relation_type,
                    from_table_name=from_name,
                    to_table_name=to_name,
                    description=r.description,
                ),
            )
        )

    embeddings_called = 0
    if items:
        client = get_embeddings()
        for i in range(0, len(items), _EMBED_BATCH_SIZE):
            batch = items[i : i + _EMBED_BATCH_SIZE]
            texts = [t for _, t in batch]
            vectors = await client.aembed_documents(texts)
            for (obj, _t), vec in zip(batch, vectors, strict=True):
                obj.embedding = vec
            embeddings_called += 1

    await session.commit()

    return ReindexReport(
        tables_reindexed=len(tables),
        columns_reindexed=len(columns),
        terms_reindexed=len(terms),
        relations_reindexed=len(relations),
        embeddings_called=embeddings_called,
    )
