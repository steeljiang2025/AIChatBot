"""STE-21：语义层 API 端到端测试。

策略（参考 STE-19 sessions API 测试）：
- access token 用 STE-18 的 security.create_access_token 真造，避免再 mock
  user_repo（ContextVar 中间件不查 users 表）。
- 把 4 类资源的 service 函数全部 monkeypatch 成内存 _SemStore 实现。
- 不连 PG，不打 LLM。

覆盖点：
- 鉴权：无 token / refresh token 当 access 用 → 401
- list：empty + multi-tenant 隔离
- create：4 类资源各一条 smoke
- get / patch / delete：owner 200|204；跨租户 → 404；不存在 → 404
- discover：调 schema_loader 不入库
- reindex：调 indexer，返回 ReindexReport
- search：调 retriever，返回 list[Hit]
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import security

# ---- 测试身份 ----


_USER_A = uuid.uuid4()
_USER_B = uuid.uuid4()
_TENANT_X = uuid.uuid4()
_TENANT_Y = uuid.uuid4()


def _make_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    return security.create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id), roles=["analyst"]
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token_x() -> str:
    return _make_token(user_id=_USER_A, tenant_id=_TENANT_X)


def _token_y() -> str:
    return _make_token(user_id=_USER_B, tenant_id=_TENANT_Y)


# ---- 内存替身 ----


class _Row:
    """通用 ORM 替身：拿 dict 任意字段。"""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.pop("id", uuid.uuid4())
        now = datetime.now(tz=UTC)
        self.created_at = kwargs.pop("created_at", now)
        self.updated_at = kwargs.pop("updated_at", now)
        for k, v in kwargs.items():
            setattr(self, k, v)


class _SemStore:
    """4 类资源 + 高层操作的内存实现，签名与 semantic_service 对齐。"""

    def __init__(self) -> None:
        self.tables: dict[uuid.UUID, _Row] = {}
        self.columns: dict[uuid.UUID, _Row] = {}
        self.terms: dict[uuid.UUID, _Row] = {}
        self.relations: dict[uuid.UUID, _Row] = {}

    # ---------- tables ----------
    async def list_tables(
        self, _db: Any, *, tenant_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[_Row], int]:
        owned = [t for t in self.tables.values() if t.tenant_id == tenant_id]
        owned.sort(key=lambda t: t.updated_at, reverse=True)
        return owned[offset : offset + limit], len(owned)

    async def get_table(
        self, _db: Any, *, table_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> _Row | None:
        t = self.tables.get(table_id)
        return t if (t and t.tenant_id == tenant_id) else None

    async def create_table(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        schema_name: str,
        table_name: str,
        display_name: str | None,
        description: str | None,
        tags: dict[str, Any] | None,
    ) -> _Row:
        row = _Row(
            tenant_id=tenant_id,
            schema_name=schema_name,
            table_name=table_name,
            display_name=display_name,
            description=description,
            tags=tags,
        )
        self.tables[row.id] = row
        return row

    async def patch_table(
        self,
        _db: Any,
        *,
        table_id: uuid.UUID,
        tenant_id: uuid.UUID,
        changes: dict[str, Any],
    ) -> _Row | None:
        t = await self.get_table(_db, table_id=table_id, tenant_id=tenant_id)
        if t is None:
            return None
        for k, v in changes.items():
            setattr(t, k, v)
        t.updated_at = datetime.now(tz=UTC)
        return t

    async def remove_table(
        self, _db: Any, *, table_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        t = await self.get_table(_db, table_id=table_id, tenant_id=tenant_id)
        if t is None:
            return False
        self.tables.pop(table_id, None)
        # cascade columns
        for cid in [c.id for c in self.columns.values() if c.table_id == table_id]:
            self.columns.pop(cid, None)
        return True

    # ---------- columns ----------
    async def list_columns(
        self, _db: Any, *, table_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[_Row] | None:
        parent = await self.get_table(_db, table_id=table_id, tenant_id=tenant_id)
        if parent is None:
            return None
        return [c for c in self.columns.values() if c.table_id == table_id]

    async def create_column(
        self,
        _db: Any,
        *,
        table_id: uuid.UUID,
        tenant_id: uuid.UUID,
        column_name: str,
        data_type: str,
        display_name: str | None,
        description: str | None,
        business_meaning: str | None,
        is_pii: bool,
    ) -> _Row | None:
        parent = await self.get_table(_db, table_id=table_id, tenant_id=tenant_id)
        if parent is None:
            return None
        row = _Row(
            tenant_id=tenant_id,
            table_id=table_id,
            column_name=column_name,
            data_type=data_type,
            display_name=display_name,
            description=description,
            business_meaning=business_meaning,
            is_pii=is_pii,
        )
        self.columns[row.id] = row
        return row

    async def patch_column(
        self,
        _db: Any,
        *,
        column_id: uuid.UUID,
        tenant_id: uuid.UUID,
        changes: dict[str, Any],
    ) -> _Row | None:
        c = self.columns.get(column_id)
        if c is None or c.tenant_id != tenant_id:
            return None
        for k, v in changes.items():
            setattr(c, k, v)
        c.updated_at = datetime.now(tz=UTC)
        return c

    async def remove_column(
        self, _db: Any, *, column_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        c = self.columns.get(column_id)
        if c is None or c.tenant_id != tenant_id:
            return False
        self.columns.pop(column_id, None)
        return True

    # ---------- terms ----------
    async def list_terms(
        self, _db: Any, *, tenant_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[_Row], int]:
        owned = [t for t in self.terms.values() if t.tenant_id == tenant_id]
        owned.sort(key=lambda t: t.updated_at, reverse=True)
        return owned[offset : offset + limit], len(owned)

    async def get_term(
        self, _db: Any, *, term_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> _Row | None:
        t = self.terms.get(term_id)
        return t if (t and t.tenant_id == tenant_id) else None

    async def create_term(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        term: str,
        definition: str | None,
        synonyms: dict[str, Any] | None,
        related_refs: dict[str, Any] | None,
    ) -> _Row:
        row = _Row(
            tenant_id=tenant_id,
            term=term,
            definition=definition,
            synonyms=synonyms,
            related_refs=related_refs,
        )
        self.terms[row.id] = row
        return row

    async def patch_term(
        self,
        _db: Any,
        *,
        term_id: uuid.UUID,
        tenant_id: uuid.UUID,
        changes: dict[str, Any],
    ) -> _Row | None:
        t = await self.get_term(_db, term_id=term_id, tenant_id=tenant_id)
        if t is None:
            return None
        for k, v in changes.items():
            setattr(t, k, v)
        t.updated_at = datetime.now(tz=UTC)
        return t

    async def remove_term(
        self, _db: Any, *, term_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        t = await self.get_term(_db, term_id=term_id, tenant_id=tenant_id)
        if t is None:
            return False
        self.terms.pop(term_id, None)
        return True

    # ---------- relations ----------
    async def list_relations(
        self, _db: Any, *, tenant_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[_Row], int]:
        owned = [r for r in self.relations.values() if r.tenant_id == tenant_id]
        owned.sort(key=lambda r: r.updated_at, reverse=True)
        return owned[offset : offset + limit], len(owned)

    async def get_relation(
        self, _db: Any, *, relation_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> _Row | None:
        r = self.relations.get(relation_id)
        return r if (r and r.tenant_id == tenant_id) else None

    async def create_relation(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        from_table_id: uuid.UUID,
        to_table_id: uuid.UUID,
        relation_type: str,
        from_column_id: uuid.UUID | None,
        to_column_id: uuid.UUID | None,
        description: str | None,
    ) -> _Row | None:
        # both tables must exist & belong to tenant
        if not await self.get_table(_db, table_id=from_table_id, tenant_id=tenant_id):
            return None
        if not await self.get_table(_db, table_id=to_table_id, tenant_id=tenant_id):
            return None
        row = _Row(
            tenant_id=tenant_id,
            from_table_id=from_table_id,
            to_table_id=to_table_id,
            from_column_id=from_column_id,
            to_column_id=to_column_id,
            relation_type=relation_type,
            description=description,
        )
        self.relations[row.id] = row
        return row

    async def patch_relation(
        self,
        _db: Any,
        *,
        relation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        changes: dict[str, Any],
    ) -> _Row | None:
        r = await self.get_relation(_db, relation_id=relation_id, tenant_id=tenant_id)
        if r is None:
            return None
        for k, v in changes.items():
            setattr(r, k, v)
        r.updated_at = datetime.now(tz=UTC)
        return r

    async def remove_relation(
        self, _db: Any, *, relation_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        r = await self.get_relation(_db, relation_id=relation_id, tenant_id=tenant_id)
        if r is None:
            return False
        self.relations.pop(relation_id, None)
        return True

    # ---------- 高层 ----------
    async def discover_business_schema(
        self,
        *,
        engine: Any,
        include_schemas: list[str] | None = None,
        include_views: bool = False,
    ) -> list[Any]:
        # 返回 dict 形式的 TableInfo（API 层做 pydantic 转换）
        from app.semantic.schema_loader import ColumnInfo, TableInfo

        return [
            TableInfo(
                schema_name="public",
                table_name="orders",
                table_type="BASE TABLE",
                columns=(
                    ColumnInfo(
                        column_name="id",
                        data_type="uuid",
                        is_nullable=False,
                    ),
                ),
            )
        ]

    async def reindex(self, _db: Any, *, tenant_id: uuid.UUID) -> Any:
        from app.semantic.indexer import ReindexReport

        return ReindexReport(
            tables_reindexed=len(
                [t for t in self.tables.values() if t.tenant_id == tenant_id]
            ),
            columns_reindexed=len(
                [c for c in self.columns.values() if c.tenant_id == tenant_id]
            ),
            terms_reindexed=len(
                [t for t in self.terms.values() if t.tenant_id == tenant_id]
            ),
            relations_reindexed=len(
                [r for r in self.relations.values() if r.tenant_id == tenant_id]
            ),
            embeddings_called=1,
        )

    async def hybrid_search(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        query: str,
        top_k: int,
        alpha: float,
        types: tuple[str, ...] | None = None,
    ) -> list[Any]:
        from app.semantic.retriever import Hit

        # 简单返回 1 条假命中：仅用于验 API 契约
        if not query:
            return []
        return [
            Hit(
                type="table",
                id=uuid.uuid4(),
                title=f"hit-for-{query}",
                snippet=f"alpha={alpha}",
                score=0.5,
            )
        ]


# ---- fixtures ----


@pytest.fixture()
def store() -> _SemStore:
    return _SemStore()


@pytest.fixture()
def auth_app(monkeypatch: pytest.MonkeyPatch, store: _SemStore) -> Any:
    async def _fake_ping(_engine: Any) -> bool:
        return True

    monkeypatch.setattr("app.api.health.ping_engine", _fake_ping)
    monkeypatch.setattr("app.main.ping_engine", _fake_ping)

    SVC = "app.services.semantic_service"
    for name in (
        "list_tables",
        "get_table",
        "create_table",
        "patch_table",
        "remove_table",
        "list_columns",
        "create_column",
        "patch_column",
        "remove_column",
        "list_terms",
        "get_term",
        "create_term",
        "patch_term",
        "remove_term",
        "list_relations",
        "get_relation",
        "create_relation",
        "patch_relation",
        "remove_relation",
        "discover_business_schema",
        "reindex",
        "hybrid_search",
    ):
        monkeypatch.setattr(f"{SVC}.{name}", getattr(store, name))

    from app.main import create_app

    app = create_app()
    # discover 端点强校 app.state.business_engine 不为 None；测试不连真实业务库，
    # 只塞一个 sentinel 让契约能跑通（mock 后的 service 不读这个值）。
    app.state.business_engine = object()
    return app


@pytest.fixture()
async def client(auth_app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ============================ 鉴权 ============================


async def test_list_tables_without_token_returns_401(client: AsyncClient) -> None:
    r = await client.get("/semantics/tables")
    assert r.status_code == 401


async def test_list_tables_with_garbage_token_returns_401(client: AsyncClient) -> None:
    r = await client.get(
        "/semantics/tables", headers={"Authorization": "Bearer garbage"}
    )
    assert r.status_code == 401


async def test_search_with_refresh_token_returns_401(client: AsyncClient) -> None:
    refresh = security.create_refresh_token(
        user_id=str(_USER_A), tenant_id=str(_TENANT_X)
    )
    r = await client.post(
        "/semantics/search", headers=_bearer(refresh), json={"query": "x"}
    )
    assert r.status_code == 401


# ============================ tables CRUD ============================


async def test_create_and_list_tables(client: AsyncClient) -> None:
    r = await client.post(
        "/semantics/tables",
        headers=_bearer(_token_x()),
        json={
            "schema_name": "public",
            "table_name": "orders",
            "display_name": "订单",
            "description": "订单事实表",
            "tags": {"domain": "sales"},
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["table_name"] == "orders"
    assert body["display_name"] == "订单"

    r2 = await client.get("/semantics/tables", headers=_bearer(_token_x()))
    assert r2.status_code == 200
    data = r2.json()
    assert data["total"] == 1
    assert data["items"][0]["table_name"] == "orders"


async def test_get_table_cross_tenant_returns_404(client: AsyncClient) -> None:
    """X 创的表 Y 看不到。"""
    r = await client.post(
        "/semantics/tables",
        headers=_bearer(_token_x()),
        json={"schema_name": "public", "table_name": "x_table"},
    )
    table_id = r.json()["id"]

    r2 = await client.get(
        f"/semantics/tables/{table_id}", headers=_bearer(_token_y())
    )
    assert r2.status_code == 404


async def test_patch_table_owner(client: AsyncClient) -> None:
    r = await client.post(
        "/semantics/tables",
        headers=_bearer(_token_x()),
        json={"schema_name": "public", "table_name": "p"},
    )
    tid = r.json()["id"]
    r2 = await client.patch(
        f"/semantics/tables/{tid}",
        headers=_bearer(_token_x()),
        json={"display_name": "改后名"},
    )
    assert r2.status_code == 200
    assert r2.json()["display_name"] == "改后名"


async def test_delete_table_cascades_columns(client: AsyncClient) -> None:
    r = await client.post(
        "/semantics/tables",
        headers=_bearer(_token_x()),
        json={"schema_name": "public", "table_name": "p"},
    )
    tid = r.json()["id"]
    r2 = await client.post(
        f"/semantics/tables/{tid}/columns",
        headers=_bearer(_token_x()),
        json={"column_name": "id", "data_type": "uuid", "is_pii": False},
    )
    assert r2.status_code == 201

    r3 = await client.delete(
        f"/semantics/tables/{tid}", headers=_bearer(_token_x())
    )
    assert r3.status_code == 204

    r4 = await client.get(
        f"/semantics/tables/{tid}/columns", headers=_bearer(_token_x())
    )
    assert r4.status_code == 404  # 父表没了


# ============================ columns ============================


async def test_create_column_under_other_tenant_table_returns_404(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/semantics/tables",
        headers=_bearer(_token_x()),
        json={"schema_name": "public", "table_name": "p"},
    )
    tid = r.json()["id"]
    r2 = await client.post(
        f"/semantics/tables/{tid}/columns",
        headers=_bearer(_token_y()),
        json={"column_name": "c", "data_type": "text", "is_pii": False},
    )
    assert r2.status_code == 404


# ============================ terms ============================


async def test_terms_crud_basic(client: AsyncClient) -> None:
    r = await client.post(
        "/semantics/terms",
        headers=_bearer(_token_x()),
        json={
            "term": "GMV",
            "definition": "商品交易总额",
            "synonyms": {"alts": ["商品成交额"]},
        },
    )
    assert r.status_code == 201
    term_id = r.json()["id"]

    r2 = await client.patch(
        f"/semantics/terms/{term_id}",
        headers=_bearer(_token_x()),
        json={"definition": "新口径"},
    )
    assert r2.status_code == 200
    assert r2.json()["definition"] == "新口径"

    r3 = await client.delete(
        f"/semantics/terms/{term_id}", headers=_bearer(_token_x())
    )
    assert r3.status_code == 204


async def test_term_cross_tenant_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/semantics/terms",
        headers=_bearer(_token_x()),
        json={"term": "t", "definition": "d"},
    )
    term_id = r.json()["id"]
    r2 = await client.get(
        f"/semantics/terms/{term_id}", headers=_bearer(_token_y())
    )
    assert r2.status_code == 404


# ============================ relations ============================


async def test_relations_require_existing_endpoints(client: AsyncClient) -> None:
    """from / to 表都必须存在且属于本租户，否则 404。"""
    # x 创 1 张表
    r = await client.post(
        "/semantics/tables",
        headers=_bearer(_token_x()),
        json={"schema_name": "public", "table_name": "p"},
    )
    tid_x = r.json()["id"]

    # 用 x 试图创建一条指向 y 表（不存在）的 relation → 404
    bogus = str(uuid.uuid4())
    r2 = await client.post(
        "/semantics/relations",
        headers=_bearer(_token_x()),
        json={
            "from_table_id": tid_x,
            "to_table_id": bogus,
            "relation_type": "fk",
        },
    )
    assert r2.status_code == 404


# ============================ 高层操作 ============================


async def test_discover_returns_table_list(client: AsyncClient) -> None:
    r = await client.post("/semantics/discover", headers=_bearer(_token_x()))
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["tables"], list)
    assert body["tables"][0]["schema_name"] == "public"
    assert body["tables"][0]["table_name"] == "orders"


async def test_reindex_returns_report(client: AsyncClient) -> None:
    # 先建一条 term 让 report 不为 0
    await client.post(
        "/semantics/terms",
        headers=_bearer(_token_x()),
        json={"term": "GMV", "definition": "x"},
    )
    r = await client.post("/semantics/reindex", headers=_bearer(_token_x()))
    assert r.status_code == 200
    body = r.json()
    assert body["terms_reindexed"] == 1
    assert body["total"] == 1


async def test_search_returns_hits(client: AsyncClient) -> None:
    r = await client.post(
        "/semantics/search",
        headers=_bearer(_token_x()),
        json={"query": "订单", "top_k": 5, "alpha": 0.3},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["hits"], list)
    assert len(body["hits"]) == 1
    assert body["hits"][0]["title"] == "hit-for-订单"


async def test_search_empty_query_returns_empty_hits(client: AsyncClient) -> None:
    r = await client.post(
        "/semantics/search",
        headers=_bearer(_token_x()),
        json={"query": ""},
    )
    assert r.status_code == 200
    assert r.json()["hits"] == []
