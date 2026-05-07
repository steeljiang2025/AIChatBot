"""ORM 模型聚合入口。

import 此包即触发所有领域模型注册到 `Base.metadata`，
alembic env.py 通过 `from app.db.models import Base` 一次性拿到完整 metadata。

领域划分：
- iam  → meta schema：Tenant、User
- chat → meta schema：ChatSession、Message
- rag  → rag  schema：SemanticTable、SemanticColumn、SemanticTerm、SemanticRelation
"""

from __future__ import annotations

from app.db.declarative import Base

from .chat import ChatSession, Message, MessageRole
from .iam import Tenant, User
from .rag import SemanticColumn, SemanticRelation, SemanticTable, SemanticTerm

__all__ = [
    "Base",
    "ChatSession",
    "Message",
    "MessageRole",
    "SemanticColumn",
    "SemanticRelation",
    "SemanticTable",
    "SemanticTerm",
    "Tenant",
    "User",
]
