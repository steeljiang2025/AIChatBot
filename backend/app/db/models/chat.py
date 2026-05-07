"""会话 + 消息（落 meta schema）。

设计要点：
- `tenant_id` 在 `Message` 上冗余存储，便于 SQL 安全模块在不 join 的情况下注入租户过滤；
- LangGraph checkpoint 与本表 **解耦**：`thread_id = chat_session_id`，
  实际 state 由 `langgraph-checkpoint-postgres` 在 checkpoint schema 中维护；
- `Message.role` 用受控字符串枚举，避免使用 PG ENUM（DDL 重构成本高）。
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.declarative import Base

from ._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from .iam import Tenant, User


class MessageRole(enum.StrEnum):
    """消息角色（与 LangChain 的 `BaseMessage.type` 对齐 + 扩展 system）。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """一次对话会话；id 同时作为 LangGraph thread_id。"""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_tenant_user", "tenant_id", "user_id"),
        Index("ix_chat_sessions_updated_at", "updated_at"),
        {"schema": "meta"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(256))

    tenant: Mapped[Tenant] = relationship()
    user: Mapped[User] = relationship(back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )


class Message(UUIDPrimaryKeyMixin, Base):
    """会话中的一条消息。

    与 LangGraph 的 messages reducer 共享 schema；可通过 `extra` 存
    `langgraph_node`、`langgraph_step`、`tool_calls` 等流式上下文。
    """

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_session_created", "session_id", "created_at"),
        Index("ix_messages_tenant", "tenant_id"),
        {"schema": "meta"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_usage: Mapped[dict | None] = mapped_column(JSONB)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    user: Mapped[User | None] = relationship(back_populates="messages")
