"""STE-21：retriever 单测（纯 Python 算分）。

策略：
- 不打 PG。把 retriever 内部的 `_run_hybrid_query`（commit 2 internal）
  monkeypatch 成返回固定的「行集」，行包含 ts_rank / cosine_distance；
  retriever.search 内部要做的「合并 4 类资源 + α 加权 + top_k 截断 +
  按 score 降序」全在 Python 里完成，可被纯单测覆盖。
- α 边界：α=0 → 纯向量；α=1 → 纯全文。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.semantic import retriever


# 行 schema：{type, id, title, snippet, ts_rank, cosine_distance}
def _row(
    *,
    type_: str = "table",
    id_: uuid.UUID | None = None,
    title: str = "t",
    snippet: str = "s",
    ts_rank: float = 0.0,
    cosine_distance: float = 1.0,
) -> dict[str, Any]:
    return {
        "type": type_,
        "id": id_ or uuid.uuid4(),
        "title": title,
        "snippet": snippet,
        "ts_rank": ts_rank,
        "cosine_distance": cosine_distance,
    }


@pytest.fixture
def patched_run_query(monkeypatch: pytest.MonkeyPatch):
    """让 _run_hybrid_query 返回 fixture 注入的行。"""
    state: dict[str, Any] = {}

    async def _fake(session: Any, **kwargs: Any) -> list[dict[str, Any]]:
        state["last_kwargs"] = kwargs
        return state["rows"]

    monkeypatch.setattr("app.semantic.retriever._run_hybrid_query", _fake)
    return state


# ---- 打分公式 ----


@pytest.mark.asyncio
async def test_search_weighted_blend_default_alpha(patched_run_query) -> None:
    """α=0.3 默认：score = 0.3 × ts_rank + 0.7 × (1 - cosine_distance)。"""
    rows = [
        _row(type_="table", title="A", ts_rank=0.5, cosine_distance=0.2),
        _row(type_="table", title="B", ts_rank=0.0, cosine_distance=0.0),
    ]
    patched_run_query["rows"] = rows

    hits = await retriever.search(
        session=None,  # 被 patched_run_query 忽略
        tenant_id=uuid.uuid4(),
        query="订单",
        top_k=10,
    )

    by_title = {h.title: h for h in hits}
    # A: 0.3*0.5 + 0.7*(1-0.2) = 0.15 + 0.56 = 0.71
    # B: 0.3*0   + 0.7*(1-0)   = 0.7
    assert by_title["A"].score == pytest.approx(0.71)
    assert by_title["B"].score == pytest.approx(0.70)
    # A > B
    assert hits[0].title == "A"


@pytest.mark.asyncio
async def test_search_alpha_zero_pure_vector(patched_run_query) -> None:
    """α=0 → score = 1 - cosine_distance；ts_rank 完全忽略。"""
    rows = [
        _row(title="X", ts_rank=999.0, cosine_distance=0.5),  # cos sim = 0.5
        _row(title="Y", ts_rank=0.0, cosine_distance=0.1),  # cos sim = 0.9
    ]
    patched_run_query["rows"] = rows

    hits = await retriever.search(
        session=None, tenant_id=uuid.uuid4(), query="q", top_k=10, alpha=0.0
    )
    titles = [h.title for h in hits]
    # Y > X 因为 Y 的 cosine sim 更高
    assert titles[0] == "Y"
    assert hits[0].score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_search_alpha_one_pure_text(patched_run_query) -> None:
    """α=1 → score = ts_rank；向量距离完全忽略。"""
    rows = [
        _row(title="X", ts_rank=0.2, cosine_distance=0.0),
        _row(title="Y", ts_rank=0.8, cosine_distance=2.0),
    ]
    patched_run_query["rows"] = rows
    hits = await retriever.search(
        session=None, tenant_id=uuid.uuid4(), query="q", top_k=10, alpha=1.0
    )
    titles = [h.title for h in hits]
    assert titles[0] == "Y"
    assert hits[0].score == pytest.approx(0.8)


# ---- top_k 与排序 ----


@pytest.mark.asyncio
async def test_search_returns_top_k_descending(patched_run_query) -> None:
    rows = [
        _row(title=f"r{i}", ts_rank=i * 0.1, cosine_distance=0.5) for i in range(20)
    ]
    patched_run_query["rows"] = rows

    hits = await retriever.search(
        session=None, tenant_id=uuid.uuid4(), query="q", top_k=5
    )
    assert len(hits) == 5
    # score 严格递减
    for a, b in zip(hits, hits[1:]):
        assert a.score >= b.score


@pytest.mark.asyncio
async def test_search_propagates_tenant_id_and_types(patched_run_query) -> None:
    """tenant_id 与 types 必须传给 _run_hybrid_query（隔离 + 类型过滤都在 SQL 层做）。"""
    patched_run_query["rows"] = []
    tid = uuid.uuid4()
    await retriever.search(
        session=None,
        tenant_id=tid,
        query="q",
        top_k=10,
        types=("table", "column"),
    )
    kw = patched_run_query["last_kwargs"]
    assert kw["tenant_id"] == tid
    assert kw["types"] == ("table", "column")


# ---- 默认参数 ----


@pytest.mark.asyncio
async def test_search_default_alpha_and_top_k(patched_run_query) -> None:
    patched_run_query["rows"] = [
        _row(title="A", ts_rank=0.4, cosine_distance=0.2),
    ]
    hits = await retriever.search(session=None, tenant_id=uuid.uuid4(), query="q")
    # 默认 α=0.3 → 0.3*0.4 + 0.7*(1-0.2) = 0.12 + 0.56 = 0.68
    assert hits[0].score == pytest.approx(0.68)
