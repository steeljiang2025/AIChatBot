"""STE-22：SQL 安全子系统。

对外稳定接口（commit 2 通过 `sql_safety_service.sanitize_sql` 暴露）：
- 异常树：SqlSafetyError 及其子类
- AST 校验：validator.{parse_safe, validate_select_only, check_system_schemas,
  check_forbidden_functions, enforce_limit}
- 白名单：schema_whitelist.check_table_columns
- 租户守卫：tenant_guard.{inject_tenant_guard, reverify_tenant_guards, TENANT_PARAM_NAME}
"""

from app.sql_safety.errors import (
    ForbiddenFunctionError,
    ForbiddenStatementError,
    LimitTooLargeError,
    MissingTenantGuardError,
    MultiStatementError,
    SqlSafetyError,
    SqlSyntaxError,
    SystemSchemaError,
    UnregisteredTableError,
)

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
