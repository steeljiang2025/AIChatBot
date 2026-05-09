"""STE-21：语义混合检索。

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
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import bindparam, text

from app.llm import get_embeddings

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
    #: 便于 NL2SQL：物理 schema（小写归一建议使用方在 SQL 中引用）
    schema_name: str | None = None
    #: 物理表名（不含 schema）
    table_name: str | None = None
    #: 列命中时的物理列名；表/术语/关联命中为 None
    physical_column: str | None = None


DEFAULT_ALPHA: float = 0.3
DEFAULT_TOP_K: int = 10


# 4 类资源各自的 SELECT，每条都暴露同样的列：
# type, id, title, snippet, ts_rank, cosine_distance,
# schema_name, table_name, physical_column（后三列供 NL2SQL 用物理标识符）
#
# - `:q` 是 plainto_tsquery 文本；空 query 时 ts_rank 退化为 0
# - `:qvec` 是查询的嵌入向量（pgvector text 表示 `[0.1,0.2,...]`）；
#   传 NULL 时 cosine_distance 退化为 1（即 cosine_similarity = 0），
#   保持公式可加。
_PER_TYPE_SQL: dict[str, str] = {
    "table": """
        SELECT 'table'::text AS type, t.id AS id,
               COALESCE(t.display_name, t.table_name) AS title,
               COALESCE(t.description, '')             AS snippet,
               COALESCE(ts_rank_cd(t.tsv, plainto_tsquery('simple', :q)), 0)::float AS ts_rank,
               COALESCE(t.embedding <=> CAST(:qvec AS vector), 1)::float            AS cosine_distance,
               t.schema_name::varchar(63)              AS schema_name,
               t.table_name::varchar(63)               AS table_name,
               NULL::varchar(63)                       AS physical_column
          FROM rag.semantic_tables t
         WHERE t.tenant_id = :tid
    """,
    "column": """
        SELECT 'column'::text AS type, c.id AS id,
               COALESCE(c.display_name, c.column_name) AS title,
               COALESCE(c.business_meaning, c.description, '') AS snippet,
               COALESCE(ts_rank_cd(c.tsv, plainto_tsquery('simple', :q)), 0)::float AS ts_rank,
               COALESCE(c.embedding <=> CAST(:qvec AS vector), 1)::float AS cosine_distance,
               tb.schema_name::varchar(63)             AS schema_name,
               tb.table_name::varchar(63)               AS table_name,
               c.column_name::varchar(63)               AS physical_column
          FROM rag.semantic_columns c
          JOIN rag.semantic_tables tb
            ON tb.id = c.table_id AND tb.tenant_id = c.tenant_id
         WHERE c.tenant_id = :tid
    """,
    "term": """
        SELECT 'term'::text AS type, m.id AS id,
               m.term                                AS title,
               COALESCE(m.definition, '')            AS snippet,
               COALESCE(ts_rank_cd(m.tsv, plainto_tsquery('simple', :q)), 0)::float AS ts_rank,
               COALESCE(m.embedding <=> CAST(:qvec AS vector), 1)::float AS cosine_distance,
               NULL::varchar(63)                     AS schema_name,
               NULL::varchar(63)                     AS table_name,
               NULL::varchar(63)                     AS physical_column
          FROM rag.semantic_terms m
         WHERE m.tenant_id = :tid
    """,
    "relation": """
        SELECT 'relation'::text AS type, r.id AS id,
               r.relation_type                       AS title,
               COALESCE(r.description, '')           AS snippet,
               0::float                              AS ts_rank,
               1::float                              AS cosine_distance,
               NULL::varchar(63)                     AS schema_name,
               NULL::varchar(63)                     AS table_name,
               NULL::varchar(63)                     AS physical_column
          FROM rag.semantic_relations r
         WHERE r.tenant_id = :tid
    """,
}


def _format_vector_for_pg(vec: list[float] | None) -> str | None:
    """pgvector 接受 `[0.1,0.2,...]` 字符串字面量。None 时 SQL 端走 NULL 路径。"""
    if vec is None:
        return None
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def _run_hybrid_query(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int,
    types: tuple[HitType, ...] | None,
) -> list[dict[str, Any]]:
    """执行混合检索 SQL，返回行字典（至少含 type, id, title, snippet,
    ts_rank, cosine_distance；以及 schema_name/table_name/physical_column）。

    每个类型 SELECT top_k 条候选，最终在 Python 端做 weighted 合并。

    向量端：query 非空时调 LLM `aembed_query` 得到 1024 维向量；
    query 为空时 `:qvec` 传 NULL，由 SQL 端 COALESCE 退化为 1。
    """
    selected_types: tuple[HitType, ...] = types or ("table", "column", "term", "relation")

    # query 为空：跳过向量查询，纯全文也无意义 → 返回 []
    if not query.strip():
        return []

    qvec_str: str | None = None
    if query.strip():
        client = get_embeddings()
        vec = await client.aembed_query(query)
        qvec_str = _format_vector_for_pg(vec)

    # 拼 UNION ALL；每个子查询自带 LIMIT 让 PG 用各自索引
    selects: list[str] = []
    for tp in selected_types:
        sub = _PER_TYPE_SQL[tp].strip()
        selects.append(f"({sub} ORDER BY ts_rank DESC, cosine_distance ASC LIMIT :limit_each)")
    full_sql = "\nUNION ALL\n".join(selects)

    stmt = text(full_sql).bindparams(bindparam("qvec", type_=None))
    params = {
        "tid": tenant_id,
        "q": query,
        "qvec": qvec_str,
        "limit_each": top_k,
    }

    result = await session.execute(stmt, params)
    return [dict(r._mapping) for r in result.all()]


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
        query: 自然语言 query；空字符串视为「不过滤」并直接返回 []，
            避免空 LLM 调用浪费配额。
        top_k: 返回前 K 条。默认 10。
        alpha: 全文权重 ∈ [0, 1]，`α=0` 为纯向量，`α=1` 为纯全文。
        types: 限制仅返回某些类型；None 表示 4 类全召回。

    Returns:
        按 score 降序的 Hit 列表，长度 ≤ top_k。
    """
    rows = await _run_hybrid_query(
        session,
        tenant_id=tenant_id,
        query=query,
        top_k=top_k,
        types=types,
    )

    hits: list[Hit] = []
    for row in rows:
        ts_rank = float(row["ts_rank"])
        cosine_distance = float(row["cosine_distance"])
        cosine_sim = 1.0 - cosine_distance
        score = alpha * ts_rank + (1.0 - alpha) * cosine_sim
        hits.append(
            Hit(
                type=row["type"],
                id=row["id"],
                title=row["title"],
                snippet=row["snippet"],
                score=score,
                schema_name=row.get("schema_name"),
                table_name=row.get("table_name"),
                physical_column=row.get("physical_column"),
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
