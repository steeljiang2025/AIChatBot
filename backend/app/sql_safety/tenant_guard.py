"""STE-22：多租户 WHERE 注入与复检。

注入策略：
- 遍历 AST 中所有 `Select`，每个 select 处理自己「直接 from / join 的多租户表」。
  子查询表由它自身的 Select 节点处理，避免外层重复注入。
- 多张多租户表共存时，使用 alias-prefixed 形式 `<alias>.tenant_id = :tid`，
  以避免 PG 在 JOIN 时的 ambiguous column 报错。
- 已存在 `tenant_id = :tid`（unqualified 单表场景）或 `<alias>.tenant_id = :tid`
  时不再重复注入。
- 占位符使用 sqlglot `Var(':tid')`，确保 PG 方言渲染输出 `:tid`
  （sqlglot 默认把 `Placeholder('tid')` 渲染成 `%(tid)s` psycopg 风格）。

复检策略：
- 把改写后的 AST 渲染回 SQL，再次 sqlglot.parse_one；
- 对每个引用了多租户表的 Select 检查 WHERE 至少存在一个 `tenant_id` 谓词
  （unqualified 或 alias.tenant_id 都算通过；严格的「每表都需独立谓词」由
  STE-23 SQL 生成 prompt 引导 LLM 配合实现）。
"""

from __future__ import annotations

from typing import Final

import sqlglot
from sqlglot import expressions as exp

from app.sql_safety.errors import MissingTenantGuardError

TENANT_PARAM_NAME: Final[str] = "tid"
_DIALECT: Final[str] = "postgres"


# ---- 内部辅助 ----


def _direct_tables(select: exp.Select) -> list[exp.Table]:
    """该 select 直接 from / join 的表（不进入嵌套子查询）。"""
    out: list[exp.Table] = []
    f = select.args.get("from_")
    if f is not None:
        if isinstance(f.this, exp.Table):
            out.append(f.this)
        for child in f.expressions or []:
            if isinstance(child, exp.Table):
                out.append(child)
    for j in select.args.get("joins") or []:
        if isinstance(j.this, exp.Table):
            out.append(j.this)
    return out


def _is_tenant_param(node: exp.Expression, param_name: str) -> bool:
    """识别 tenant 参数占位：注入产生的 Var(':tid') 或 round-trip 后的 Placeholder('tid')。"""
    if isinstance(node, exp.Placeholder) and node.this == param_name:
        return True
    if isinstance(node, exp.Var) and node.this == f":{param_name}":
        return True
    return False


def _existing_tenant_aliases(
    where: exp.Where | None, param_name: str
) -> set[str]:
    """返回 WHERE 中已含 `tenant_id = :tid` 形式谓词的「table alias」集合。

    unqualified `tenant_id` 用空字符串 `""` 作为 sentinel。
    """
    out: set[str] = set()
    if where is None:
        return out
    for eq in where.find_all(exp.EQ):
        left, right = eq.this, eq.expression
        if not isinstance(left, exp.Column):
            continue
        if (left.name or "").lower() != "tenant_id":
            continue
        if not _is_tenant_param(right, param_name):
            continue
        table = (left.table or "").lower()
        out.add(table)
    return out


def _and_into_where(
    select: exp.Select, predicates: list[exp.Expression]
) -> None:
    """把 predicates 用 AND 串接到 select.WHERE 上（原地修改）。"""
    if not predicates:
        return
    where = select.args.get("where")
    tree: exp.Expression | None = where.this if where is not None else None
    for p in predicates:
        tree = p if tree is None else exp.And(this=tree, expression=p)
    select.set("where", exp.Where(this=tree))


def _make_tenant_predicate(
    alias_or_table: str, param_name: str
) -> exp.EQ:
    """构造 `<alias_or_table>.tenant_id = :tid`。"""
    return exp.EQ(
        this=exp.Column(
            this=exp.Identifier(this="tenant_id"),
            table=exp.Identifier(this=alias_or_table),
        ),
        expression=exp.Var(this=f":{param_name}"),
    )


def _normalize_tenant_placeholders(
    ast: exp.Expression, param_name: str
) -> None:
    """把用户输入 SQL 里的 `Placeholder('tid')`（来自 `:tid`）原地替换成
    `Var(':tid')`，确保 PG 方言渲染始终输出 `:tid`（而非 sqlglot 默认的
    psycopg 风格 `%(tid)s`）。

    选择 `Var` 是因为它会原样输出字面量；`Placeholder('tid')` 在 PG dialect
    下被强制渲染成 `%(tid)s`，与下游 SQLAlchemy `bindparam(:tid)` 风格不一致。
    """
    for ph in list(ast.find_all(exp.Placeholder)):
        if ph.this == param_name:
            ph.replace(exp.Var(this=f":{param_name}"))


# ---- 对外 API ----


def inject_tenant_guard(
    ast: exp.Expression,
    *,
    tenant_scoped_tables: set[tuple[str, str]],
    tenant_id_param: str = TENANT_PARAM_NAME,
) -> exp.Expression:
    """对每个 Select 中引用的多租户表注入 tenant_id 谓词。

    Returns: 同一棵 AST（原地修改）。
    """
    _normalize_tenant_placeholders(ast, tenant_id_param)

    for select in list(ast.find_all(exp.Select)):
        direct = _direct_tables(select)
        scoped = [
            t
            for t in direct
            if ((t.db or "public").lower(), (t.name or "").lower())
            in tenant_scoped_tables
        ]
        if not scoped:
            continue

        existing = _existing_tenant_aliases(
            select.args.get("where"), tenant_id_param
        )

        # 单表 + 已有 unqualified tenant_id 谓词 → 完全跳过
        if "" in existing and len(scoped) == 1:
            continue

        new_preds: list[exp.Expression] = []
        for tbl in scoped:
            alias_or_name = (tbl.alias or tbl.name or "").lower()
            if not alias_or_name:
                continue
            if alias_or_name in existing:
                continue
            new_preds.append(
                _make_tenant_predicate(alias_or_name, tenant_id_param)
            )

        _and_into_where(select, new_preds)

    return ast


def reverify_tenant_guards(
    ast: exp.Expression,
    *,
    tenant_scoped_tables: set[tuple[str, str]],
    tenant_id_param: str = TENANT_PARAM_NAME,
) -> None:
    """复检：渲染 → 再 parse → 每个引用多租户表的 Select 必须带 tenant_id 谓词。

    Raises: MissingTenantGuardError
    """
    # 复检前 normalize，让仅传入未注入过的 ast 也能被识别（如直接调用复检的
    # 测试场景：用户已写好 `:tid` 但未走 inject 流水线）。
    _normalize_tenant_placeholders(ast, tenant_id_param)
    sql = ast.sql(dialect=_DIALECT)
    re_ast = sqlglot.parse_one(sql, dialect=_DIALECT)

    for select in re_ast.find_all(exp.Select):
        direct = _direct_tables(select)
        scoped_present = any(
            ((t.db or "public").lower(), (t.name or "").lower())
            in tenant_scoped_tables
            for t in direct
        )
        if not scoped_present:
            continue
        existing = _existing_tenant_aliases(
            select.args.get("where"), tenant_id_param
        )
        if not existing:
            raise MissingTenantGuardError(
                f"Tenant guard missing in SELECT: "
                f"{select.sql(dialect=_DIALECT)}"
            )
