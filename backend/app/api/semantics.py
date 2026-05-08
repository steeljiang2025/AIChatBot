"""STE-21：语义层管理 API（占位）。

端点清单（实现见 commit 2，全部需要 JWT，进 _PUBLIC_PATHS 之外的默认路径）：

| Method | Path                                          | 说明                       |
|--------|-----------------------------------------------|--------------------------|
| GET    | /semantics/tables                             | 列表（分页）              |
| POST   | /semantics/tables                             | 登记一张业务表           |
| GET    | /semantics/tables/{id}                        | 详情                     |
| PATCH  | /semantics/tables/{id}                        | 部分更新                 |
| DELETE | /semantics/tables/{id}                        | 删除（cascade 列）       |
| GET    | /semantics/tables/{id}/columns                | 该表的列列表             |
| POST   | /semantics/tables/{id}/columns                | 登记列                   |
| PATCH  | /semantics/columns/{id}                       | 列部分更新               |
| DELETE | /semantics/columns/{id}                       | 删除列                   |
| GET    | /semantics/terms                              | 术语列表                 |
| POST   | /semantics/terms                              | 创建术语                 |
| GET    | /semantics/terms/{id}                         | 术语详情                 |
| PATCH  | /semantics/terms/{id}                         | 术语部分更新             |
| DELETE | /semantics/terms/{id}                         | 删除术语                 |
| GET    | /semantics/relations                          | 关联列表                 |
| POST   | /semantics/relations                          | 创建关联                 |
| GET    | /semantics/relations/{id}                     | 关联详情                 |
| PATCH  | /semantics/relations/{id}                     | 关联部分更新             |
| DELETE | /semantics/relations/{id}                     | 删除关联                 |
| POST   | /semantics/discover                           | 发现业务库（dry-run）    |
| POST   | /semantics/reindex                            | 全量重建本租户向量       |
| POST   | /semantics/search                             | 混合检索                 |

实现见 commit 2。本占位只暴露空 router，让 main.py 提前挂载，避免
commit 2 同时改 main.py（main.py 的 import 顺序对 lint 敏感）。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/semantics", tags=["semantics"])


__all__ = ["router"]
