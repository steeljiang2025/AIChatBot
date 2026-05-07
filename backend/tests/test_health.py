"""Phase1 冒烟测试：/health 与 /version。"""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["db"]["meta"] == "ok"
    assert payload["db"]["biz"] == "ok"
    assert "version" in payload


async def test_version(client: AsyncClient) -> None:
    resp = await client.get("/version")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["name"] == "AIChatBot"
    assert payload["version"]


async def test_openapi_schema_available(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "AIChatBot"
