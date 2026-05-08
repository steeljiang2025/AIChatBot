"""STE-22：多租户 WHERE 注入与复检（占位）。

策略（用户决策：tenant_id 用占位符 `:tid`）：
- 注入：遍历 AST 所有 `Select`，对引用了 multi-tenant 表的 SELECT，
  在其 WHERE 上 AND `tenant_id = :tid`（如已存在则跳过）。
- 复检：把改写后的 AST 渲染回 SQL，再次 sqlglot.parse_one，遍历每个
  Select 重新确认上述谓词存在；不存在则抛 MissingTenantGuardError。

不做的事：
- 不试图解析嵌套子查询的「列归属」；嵌套 SELECT 由外层遍历再次访问。
- 不限制 tenant_id 出现在 ON 子句还是 WHERE；本期只接受 WHERE 形式
  的谓词，约定 SQL 生成 prompt 让 LLM 把 tenant 过滤放 WHERE。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import sqlglot.expressions as exp


TENANT_PARAM_NAME: Final[str] = "tid"


def inject_tenant_guard(
    ast: exp.Expression,
    *,
    tenant_scoped_tables: set[tuple[str, str]],
    tenant_id_param: str = TENANT_PARAM_NAME,
) -> exp.Expression:
    """对 AST 中每个引用了多租户表的 SELECT，注入 `tenant_id = :tid` 谓词。

    Returns: 同一棵 AST（原地修改）。
    """
    raise NotImplementedError


def reverify_tenant_guards(
    ast: exp.Expression,
    *,
    tenant_scoped_tables: set[tuple[str, str]],
    tenant_id_param: str = TENANT_PARAM_NAME,
) -> None:
    """复检：注入完成后再 parse 一次，确认每个 select 都仍带 tenant_id 谓词。

    Raises: MissingTenantGuardError
    """
    raise NotImplementedError
