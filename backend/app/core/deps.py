"""STE-18：FastAPI Depends 工具。

`get_current_user` 读取 ContextVar 中的 user_id，再去 user_repo 取实体；
任何异常一律 401，不暴露细节。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_user_id
from app.db.base import get_meta_session
from app.db.models import User
from app.services import user_repo


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def get_current_user_id() -> uuid.UUID:
    raw = current_user_id.get()
    if raw is None:
        raise _unauthorized()
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError) as exc:
        raise _unauthorized() from exc


# 复用别名，避免在每个 endpoint 重复写一长串 Annotated[...]
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
MetaSession = Annotated[AsyncSession, Depends(get_meta_session)]


async def get_current_user(
    user_id: CurrentUserId,
    session: MetaSession,
) -> User:
    user = await user_repo.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
