"""SQLAlchemy ORM 基类（独立模块，避免触发 engine 实例化）。

alembic env.py 与业务代码都从这里 import `Base`，
确保即便 alembic 在没有完整 ENV（DASHSCOPE_API_KEY 等）的本地终端运行时，
也不会因为加载 `app.db.base` 而被迫初始化 engine。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(DeclarativeBase):
    """全局 ORM 基类。

    所有模型继承此类后，通过 `Base.metadata` 即可被 alembic 检测。
    使用 SQLAlchemy 2.x `DeclarativeBase`（typing-friendly）。

    NOTE: 故意 **不** 混入 `MappedAsDataclass`，因为 vector / 复合类型用
    `Mapped[T]` 注解 + 非 dataclass 风格更直观，且与 `pgvector.sqlalchemy.Vector`
    兼容性更好。
    """

    pass


__all__ = ["Base", "MappedAsDataclass"]

