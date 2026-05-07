"""跨域共用的 ORM mixin / 工具列。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class UUIDPrimaryKeyMixin:
    """所有业务表统一使用 server-side `gen_random_uuid()` 作为 PK。

    依赖 PostgreSQL 13+ 自带的 `pgcrypto`/`gen_random_uuid()`；
    aichatbot 用的 pgvector/pg16 镜像默认就带，无需额外扩展。
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """`created_at` / `updated_at` 走数据库时钟，避免应用时区漂移。"""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )


__all__ = ["TimestampMixin", "UUIDPrimaryKeyMixin"]
