"""STE-21：schema_loader 单测。

策略：
- 不连真实 PG。把 `_fetch_information_schema_rows`（commit 2 的 internal）
  monkeypatch 成返回固定行；本测试只验「行 → list[TableInfo]」聚合 +
  默认黑名单过滤的纯 Python 逻辑。
- 这个间接策略让 commit 2 实现时的真实 SQL 不影响单测稳定性。

红色形态：commit 1 没有 `_fetch_information_schema_rows`，
load_schema 直接 raise NotImplementedError。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.semantic import schema_loader

# 7 元组：(schema, table, table_type, column, data_type, is_nullable, default)
_FAKE_ROWS: list[tuple[str, str, str, str, str, bool, str | None]] = [
    ("public", "orders", "BASE TABLE", "id", "uuid", False, None),
    ("public", "orders", "BASE TABLE", "amount", "numeric", True, None),
    ("public", "orders", "BASE TABLE", "tenant_id", "uuid", False, None),
    ("public", "products", "BASE TABLE", "id", "uuid", False, None),
    ("public", "products", "BASE TABLE", "name", "text", True, None),
    ("public", "monthly_sales", "VIEW", "month", "date", True, None),
    ("public", "monthly_sales", "VIEW", "total", "numeric", True, None),
    # 内部 schema 在 SQL 层就被过滤；测试这里也包含一行验证
    ("meta", "tenants", "BASE TABLE", "id", "uuid", False, None),
]


@pytest.fixture
def patched_fetch(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """让 _fetch_... 直接返回 _FAKE_ROWS，并记录传入的 kwargs。"""
    captured_kwargs: list[Any] = []

    async def _fake(engine: Any, **kwargs: Any) -> list[Any]:
        captured_kwargs.append(kwargs)
        return _FAKE_ROWS

    monkeypatch.setattr(
        "app.semantic.schema_loader._fetch_information_schema_rows",
        _fake,
    )
    return captured_kwargs


@pytest.mark.asyncio
async def test_load_schema_groups_columns_under_tables(patched_fetch) -> None:
    tables = await schema_loader.load_schema(engine=None)

    by_name = {(t.schema_name, t.table_name): t for t in tables}
    assert ("public", "orders") in by_name
    assert ("public", "products") in by_name

    orders = by_name[("public", "orders")]
    assert {c.column_name for c in orders.columns} == {"id", "amount", "tenant_id"}
    products = by_name[("public", "products")]
    assert {c.column_name for c in products.columns} == {"id", "name"}


@pytest.mark.asyncio
async def test_load_schema_excludes_internal_schemas_by_default(patched_fetch) -> None:
    """默认不抽 meta / rag / checkpoint —— 由 SQL where 子句保证；
    本测试通过传给 _fetch_... 的 kwargs 确认黑名单被正确传入。"""
    await schema_loader.load_schema(engine=None)
    assert patched_fetch, "_fetch_... 未被调用"
    kwargs = patched_fetch[0]
    # 黑名单形态：要么是 None（让 _fetch_... 自己处理），要么是显式 list
    # 我们要求实现层在 SQL 里排除内部 schema。这里只断言 include_schemas 是 None。
    assert kwargs.get("include_schemas") is None
    assert kwargs.get("include_views") is False


@pytest.mark.asyncio
async def test_load_schema_views_excluded_by_default(patched_fetch) -> None:
    """include_views=False 时，VIEW 行应被聚合层过滤掉。"""
    tables = await schema_loader.load_schema(engine=None)
    assert all(t.table_type == "BASE TABLE" for t in tables)
    assert all(t.table_name != "monthly_sales" for t in tables)


@pytest.mark.asyncio
async def test_load_schema_views_included_when_flag_on(patched_fetch) -> None:
    tables = await schema_loader.load_schema(engine=None, include_views=True)
    names = {(t.schema_name, t.table_name) for t in tables}
    assert ("public", "monthly_sales") in names


@pytest.mark.asyncio
async def test_load_schema_sorted_by_schema_then_table(patched_fetch) -> None:
    tables = await schema_loader.load_schema(engine=None, include_views=True)
    keys = [(t.schema_name, t.table_name) for t in tables]
    assert keys == sorted(keys), f"未按 (schema, table) 排序: {keys}"


@pytest.mark.asyncio
async def test_load_schema_drops_internal_schemas_at_aggregation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """聚合层兜底：即使 _fetch_... 返回了内部 schema 的行（实现 bug），
    load_schema 也必须二次过滤掉。"""

    async def _fake(_engine: Any, **_: Any) -> list[Any]:
        return _FAKE_ROWS  # 包含 meta.tenants 行

    monkeypatch.setattr(
        "app.semantic.schema_loader._fetch_information_schema_rows", _fake
    )
    tables = await schema_loader.load_schema(engine=None, include_views=True)
    assert all(t.schema_name != "meta" for t in tables)
