"""IAM 域：租户 + 用户（落 meta schema）。"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.declarative import Base

from ._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from .chat import ChatSession, Message


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户：多租户隔离的根实体。

    `code` 是对外短编码（建议英文小写+数字+下划线），用于 URL/日志/审计。
    `name` 是面向用户的展示名。
    """

    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("code", name="uq_tenants_code"),
        {"schema": "meta"},
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    users: Mapped[list[User]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """用户：必须归属于一个租户；email 在租户内唯一。

    `password_hash` 走 bcrypt（passlib），STE-18 鉴权落地。
    `roles` 用 PG 原生 text[]，常用值：admin/analyst/viewer。
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        {"schema": "meta"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    roles: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        nullable=False,
        server_default="{}",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    sessions: Mapped[list[ChatSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
