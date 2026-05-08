"""STE-18：租户 / 用户 ContextVar。

通过 `contextvars.ContextVar` 在请求范围内携带身份信息，
async 任务/子协程会自动继承当前上下文，service / repo 层无需把
`tenant_id` 在每个调用里手动传递（也能借此在多租户隔离里"忘了过滤"
的 bug 上加一道兜底）。

写入由 `core/middleware.JWTAuthMiddleware` 在请求开头完成，
请求结束时通过 token reset 还原，避免污染下一个请求的上下文。
"""

from __future__ import annotations

from contextvars import ContextVar

current_tenant_id: ContextVar[str | None] = ContextVar(
    "current_tenant_id", default=None
)
current_user_id: ContextVar[str | None] = ContextVar(
    "current_user_id", default=None
)
# 用 tuple 而不是 list 作为默认值，避免可变默认值被意外共享
current_user_roles: ContextVar[tuple[str, ...]] = ContextVar(
    "current_user_roles", default=()
)
