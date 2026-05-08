"""STE-22：SQL 安全检查异常树。

业务侧应只对 `SqlSafetyError` 做 except，子类用于日志/监控分类。
"""

from __future__ import annotations


class SqlSafetyError(Exception):
    """SQL 安全检查失败的根异常。"""


class SqlSyntaxError(SqlSafetyError):
    """sqlglot 解析失败：可能是 LLM 输出了不合法 SQL。"""


class MultiStatementError(SqlSafetyError):
    """检测到多条语句（如 `SELECT 1; DROP TABLE x`）。"""


class ForbiddenStatementError(SqlSafetyError):
    """非 SELECT / CTE 语句（INSERT / UPDATE / DELETE / DDL / COPY 等）。"""


class SystemSchemaError(SqlSafetyError):
    """引用了系统 schema（pg_catalog / pg_toast / information_schema）
    或系统表前缀（`pg_*`）。"""


class ForbiddenFunctionError(SqlSafetyError):
    """调用了危险函数（`pg_read_file` / `lo_import` / `dblink` 等）。"""


class UnregisteredTableError(SqlSafetyError):
    """引用了未在 SemanticTable 中登记的表，或未登记的列。
    防止 LLM 幻觉出虚构表 / 列。"""


class MissingTenantGuardError(SqlSafetyError):
    """复检时发现某多租户表的 `tenant_id` 谓词丢失。
    通常意味着 tenant_guard 注入逻辑有 bug，或 LLM 用了无法注入的奇异结构。"""


class LimitTooLargeError(SqlSafetyError):
    """LIMIT 显式大于配置上限。
    一般 sanitize 时会自动截断到上限，这条仅在严格模式下抛。"""


__all__ = [
    "ForbiddenFunctionError",
    "ForbiddenStatementError",
    "LimitTooLargeError",
    "MissingTenantGuardError",
    "MultiStatementError",
    "SqlSafetyError",
    "SqlSyntaxError",
    "SystemSchemaError",
    "UnregisteredTableError",
]
