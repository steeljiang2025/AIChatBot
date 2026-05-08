"""STE-24：schema_provider.load_schema_whitelist 单测（mock DB）。

策略：
- 不真连 PG；用一组假的 ORM 实体喂入 monkeypatched session.execute
- 断言三个集合的小写归一 + tenant_scoped_tables 依据「是否含 tenant_id 列」自动推断
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.schema_provider import SchemaWhitelist, load_schema_whitelist


@dataclass
class _FakeTable:
    id: uuid.UUID
    schema_name: str
    table_name: str


@dataclass
class _FakeColumn:
    table_id: uuid.UUID
    column_name: str


class _FakeSession:
    """模拟 SQLAlchemy AsyncSession.execute 返回结果。"""

    def __init__(self, tables: list[_FakeTable], columns: list[_FakeColumn]) -> None:
        self._tables = tables
        self._columns = columns

    async def execute(self, stmt: Any) -> "_FakeResult":
        # 简化：根据 stmt 是 select(SemanticTable) 还是 select(SemanticColumn) 返回不同
        from app.db.models import SemanticColumn, SemanticTable

        # SQLAlchemy `select` 第一个 column 是判断标准
        cols = list(stmt.selected_columns) if hasattr(stmt, "selected_columns") else []
        first = stmt.column_descriptions[0]["entity"] if stmt.column_descriptions else None
        if first is SemanticTable:
            return _FakeResult(self._tables)
        if first is SemanticColumn:
            return _FakeResult(self._columns)
        return _FakeResult([])


class _FakeResult:
    def __init__(self, items: list) -> None:
        self._items = items

    def scalars(self) -> "_FakeScalars":
        return _FakeScalars(self._items)


class _FakeScalars:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return list(self._items)


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_load_returns_normalized_lowercase(tenant_id: uuid.UUID) -> None:
    t1 = _FakeTable(id=uuid.uuid4(), schema_name="Public", table_name="Orders")
    t2 = _FakeTable(id=uuid.uuid4(), schema_name="public", table_name="products")
    cols = [
        _FakeColumn(table_id=t1.id, column_name="ID"),
        _FakeColumn(table_id=t1.id, column_name="amount"),
        _FakeColumn(table_id=t1.id, column_name="tenant_id"),
        _FakeColumn(table_id=t2.id, column_name="id"),
        _FakeColumn(table_id=t2.id, column_name="name"),
    ]
    session = _FakeSession([t1, t2], cols)

    out: SchemaWhitelist = await load_schema_whitelist(session, tenant_id=tenant_id)
    assert ("public", "orders") in out.known_tables
    assert ("public", "products") in out.known_tables
    assert out.known_columns[("public", "orders")] == {"id", "amount", "tenant_id"}
    assert out.known_columns[("public", "products")] == {"id", "name"}


@pytest.mark.asyncio
async def test_tenant_scoped_inferred_from_tenant_id_column(tenant_id: uuid.UUID) -> None:
    """含 tenant_id 列的表 → 自动进 tenant_scoped_tables。"""
    t_scoped = _FakeTable(id=uuid.uuid4(), schema_name="public", table_name="orders")
    t_global = _FakeTable(id=uuid.uuid4(), schema_name="public", table_name="products")
    cols = [
        _FakeColumn(table_id=t_scoped.id, column_name="id"),
        _FakeColumn(table_id=t_scoped.id, column_name="tenant_id"),
        _FakeColumn(table_id=t_global.id, column_name="id"),
        _FakeColumn(table_id=t_global.id, column_name="name"),
    ]
    session = _FakeSession([t_scoped, t_global], cols)

    out = await load_schema_whitelist(session, tenant_id=tenant_id)
    assert ("public", "orders") in out.tenant_scoped_tables
    assert ("public", "products") not in out.tenant_scoped_tables


@pytest.mark.asyncio
async def test_empty_tenant_returns_empty_collections(tenant_id: uuid.UUID) -> None:
    """没有任何登记的语义对象 → 三个集合都是空。"""
    session = _FakeSession([], [])
    out = await load_schema_whitelist(session, tenant_id=tenant_id)
    assert out.known_tables == set()
    assert out.known_columns == {}
    assert out.tenant_scoped_tables == set()
