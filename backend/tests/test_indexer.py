"""STE-21：indexer 单测。

策略：
- card_for_*：纯字符串函数，直接验关键字段被拼到输出。
- reindex_tenant：mock `_load_tenant_objects`（commit 2 internal）返回
  4 个 list，mock `app.llm.get_embeddings()` 客户端 → 验调用 batch 数、
  embedding 写回、ReindexReport 计数。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.semantic import indexer

# ---- card_for_* ----


def test_card_for_table_includes_display_and_table_name() -> None:
    out = indexer.card_for_table(
        display_name="订单事实表",
        table_name="orders",
        description="每行一笔订单，含金额、地区、时间",
    )
    assert "订单事实表" in out
    assert "orders" in out
    assert "金额" in out


def test_card_for_table_handles_none_display_and_description() -> None:
    out = indexer.card_for_table(
        display_name=None,
        table_name="raw_table",
        description=None,
    )
    assert "raw_table" in out


def test_card_for_column_includes_business_meaning() -> None:
    out = indexer.card_for_column(
        table_name="orders",
        column_name="amount",
        display_name="金额",
        data_type="numeric",
        business_meaning="实际成交额（含税）",
        description=None,
    )
    assert "金额" in out
    assert "amount" in out
    assert "numeric" in out
    assert "实际成交额（含税）" in out


def test_card_for_term_includes_synonyms() -> None:
    out = indexer.card_for_term(
        term="客户活跃度",
        definition="近 30 天有过登录或下单的客户比例",
        synonyms=["活跃用户率", "DAU 占比"],
    )
    assert "客户活跃度" in out
    assert "近 30 天" in out
    assert "活跃用户率" in out


def test_card_for_term_handles_none_synonyms() -> None:
    out = indexer.card_for_term(
        term="GMV",
        definition="商品交易总额",
        synonyms=None,
    )
    assert "GMV" in out
    assert "商品交易总额" in out


def test_card_for_relation_includes_both_table_names() -> None:
    out = indexer.card_for_relation(
        relation_type="fk",
        from_table_name="orders",
        to_table_name="products",
        description="orders.product_id → products.id",
    )
    assert "orders" in out
    assert "products" in out
    assert "fk" in out


# ---- reindex_tenant ----


class _FakeTable:
    """轻量 ORM 替身，足够 reindex_tenant 读字段 + 写 embedding。"""

    def __init__(
        self,
        *,
        display_name: str | None = None,
        table_name: str = "t",
        description: str | None = None,
    ) -> None:
        self.id = uuid.uuid4()
        self.display_name = display_name
        self.table_name = table_name
        self.description = description
        self.embedding: list[float] | None = None


class _FakeColumn:
    def __init__(self, *, table_name: str = "t", column_name: str = "c") -> None:
        self.id = uuid.uuid4()
        self.table_name_for_card = table_name  # commit 2 实现时通过 table 关系拿
        self.column_name = column_name
        self.display_name: str | None = None
        self.data_type = "text"
        self.business_meaning: str | None = None
        self.description: str | None = None
        self.embedding: list[float] | None = None


class _FakeTerm:
    def __init__(self, *, term: str = "x") -> None:
        self.id = uuid.uuid4()
        self.term = term
        self.definition: str | None = None
        self.synonyms: dict[str, Any] | None = None
        self.embedding: list[float] | None = None


class _FakeRelation:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.relation_type = "fk"
        self.from_table_name_for_card = "orders"
        self.to_table_name_for_card = "products"
        self.description: str | None = None
        self.embedding: list[float] | None = None


class _FakeEmbeddingClient:
    """Mock LangChain OpenAIEmbeddings：记录每次 aembed_documents 的 batch。"""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim
        self.batches: list[list[str]] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[float(i) / 10.0] * self.dim for i, _ in enumerate(texts)]


@pytest.fixture
def patched_indexer(monkeypatch: pytest.MonkeyPatch):
    """统一 mock indexer 内部依赖。返回 (fake_embed_client, ref_objects)。"""
    tables = [_FakeTable(display_name="订单", table_name="orders")]
    columns = [_FakeColumn(table_name="orders", column_name="amount")]
    terms = [_FakeTerm(term="GMV")]
    relations = [_FakeRelation()]

    async def _fake_load(_session: Any, *, tenant_id: uuid.UUID) -> tuple[Any, ...]:
        # 让任意 tenant_id 都拿到固定的 4 个 list（隔离的真实测试在 retriever）
        assert isinstance(tenant_id, uuid.UUID)
        return tables, columns, terms, relations

    monkeypatch.setattr("app.semantic.indexer._load_tenant_objects", _fake_load)

    fake_client = _FakeEmbeddingClient()
    monkeypatch.setattr(
        "app.semantic.indexer.get_embeddings",
        lambda: fake_client,
    )
    return fake_client, (tables, columns, terms, relations)


@pytest.mark.asyncio
async def test_reindex_tenant_writes_back_embeddings(patched_indexer) -> None:
    fake_client, (tables, columns, terms, relations) = patched_indexer

    class _StubSession:
        async def commit(self) -> None:
            return None

    report = await indexer.reindex_tenant(
        _StubSession(),
        tenant_id=uuid.uuid4(),
    )

    assert report.tables_reindexed == 1
    assert report.columns_reindexed == 1
    assert report.terms_reindexed == 1
    assert report.relations_reindexed == 1
    assert report.total == 4

    # 每个对象都应被写入了 embedding（非 None）
    for obj in tables + columns + terms + relations:
        assert obj.embedding is not None
        assert len(obj.embedding) == fake_client.dim

    # batch 上限为 10（百炼 v4 上限） — 本例 4 条全部一批
    assert all(len(b) <= 10 for b in fake_client.batches)
    assert sum(len(b) for b in fake_client.batches) == 4


@pytest.mark.asyncio
async def test_reindex_tenant_empty_returns_zero_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _empty_load(_s: Any, *, tenant_id: uuid.UUID) -> tuple[Any, ...]:
        return [], [], [], []

    monkeypatch.setattr("app.semantic.indexer._load_tenant_objects", _empty_load)
    fake_client = _FakeEmbeddingClient()
    monkeypatch.setattr("app.semantic.indexer.get_embeddings", lambda: fake_client)

    class _StubSession:
        async def commit(self) -> None:
            return None

    report = await indexer.reindex_tenant(_StubSession(), tenant_id=uuid.uuid4())
    assert report.total == 0
    assert report.embeddings_called == 0
    assert fake_client.batches == []


@pytest.mark.asyncio
async def test_reindex_tenant_batches_le_10(monkeypatch: pytest.MonkeyPatch) -> None:
    """25 张表 → 至少 3 个 batch（10 + 10 + 5），单 batch ≤ 10。"""
    tables = [
        _FakeTable(display_name=f"t{i}", table_name=f"t{i}") for i in range(25)
    ]

    async def _load_25(_s: Any, *, tenant_id: uuid.UUID) -> tuple[Any, ...]:
        return tables, [], [], []

    monkeypatch.setattr("app.semantic.indexer._load_tenant_objects", _load_25)
    fake_client = _FakeEmbeddingClient()
    monkeypatch.setattr("app.semantic.indexer.get_embeddings", lambda: fake_client)

    class _StubSession:
        async def commit(self) -> None:
            return None

    report = await indexer.reindex_tenant(_StubSession(), tenant_id=uuid.uuid4())
    assert report.tables_reindexed == 25
    assert all(len(b) <= 10 for b in fake_client.batches)
    assert sum(len(b) for b in fake_client.batches) == 25
    # 至少 3 batches
    assert len(fake_client.batches) >= 3
