"""pytest fixtures：在测试中默认 mock 掉数据库探针，避免真实连库。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> Any:
    # 测试环境直接把 ping_engine 兑换成 True，避免连接真实 PG
    async def _fake_ping(_engine: Any) -> bool:
        return True

    monkeypatch.setattr("app.api.health.ping_engine", _fake_ping)
    monkeypatch.setattr("app.main.ping_engine", _fake_ping)
    return create_app()


@pytest.fixture()
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
