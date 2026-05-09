"""sql_gen：白名单物理列与检索卡片合并。"""

from __future__ import annotations

from app.graph.nodes.sql_gen import merge_whitelist_with_rag_schema_cards


def test_merge_fills_all_english_columns_from_whitelist() -> None:
    cfg = {
        "known_tables": {("biz", "demo_orders")},
        "known_columns": {
            ("biz", "demo_orders"): {"amount", "region", "product_name", "tenant_id"},
        },
    }
    rag_cards = [
        {
            "table": "biz.demo_orders",
            "display_name": "演示订单",
            "columns": ["amount"],
            "description": "语义补充",
        },
    ]
    merged = merge_whitelist_with_rag_schema_cards(cfg, rag_cards)
    assert len(merged) == 1
    assert merged[0]["table"] == "biz.demo_orders"
    assert merged[0]["display_name"] == "演示订单"
    assert merged[0]["description"] == "语义补充"
    assert set(merged[0]["columns"]) == {
        "amount",
        "region",
        "product_name",
        "tenant_id",
    }


def test_merge_without_whitelist_falls_back_to_rag_only() -> None:
    cfg: dict = {}
    rag = [
        {
            "table": "（术语，非物理表）华东",
            "display_name": "华东",
            "columns": [],
            "description": "",
        }
    ]
    assert merge_whitelist_with_rag_schema_cards(cfg, rag) is rag
