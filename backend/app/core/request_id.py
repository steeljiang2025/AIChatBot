"""为每个 HTTP 请求注入 X-Request-ID，便于前后端日志串联（Phase 4）。"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """从请求头读取或生成 UUID，写入 response.headers 与 request.state。"""

    header_name = "X-Request-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[self.header_name] = rid
        return response
