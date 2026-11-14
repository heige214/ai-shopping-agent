from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.catalog.models import Product


class ChatSession(Base):
    """会话：M3 只使用 type=support；guide 留给 M4。"""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        CheckConstraint("type IN ('guide', 'support')", name="type_valid"),
        CheckConstraint(
            "status IN ('active', 'waiting_human', 'human', 'closed')",
            name="status_valid",
        ),
        Index("ix_chat_sessions_user_type_status", "user_id", "type", "status"),
        Index("ix_chat_sessions_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    slot_state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product: Mapped[Product | None] = relationship(lazy="selectin")
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    tickets: Mapped[list[SupportTicket]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """消息：content 为 JSONB，M3 只写 text。"""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "sender_type IN ('user', 'ai', 'agent', 'system')",
            name="sender_type_valid",
        ),
        CheckConstraint(
            "content_type IN "
            "('text', 'image', 'voice', 'product_cards', 'action_card', "
            "'system_event')",
            name="content_type_valid",
        ),
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_id: Mapped[int | None] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class SupportTicket(Base):
    """转人工工单：M3 只创建 waiting 工单，排队/接入/结束在 M6。"""

    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting', 'connected', 'closed')", name="status_valid"
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'running', 'done', 'failed')",
            name="extraction_status_valid",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating BETWEEN 1 AND 5)", name="rating_range"
        ),
        Index("ix_support_tickets_status_created", "status", "created_at"),
        Index("ix_support_tickets_session_id", "session_id"),
        Index("ix_support_tickets_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="waiting", server_default="waiting"
    )
    assigned_agent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    context_summary: Mapped[str | None] = mapped_column(Text)
    extraction_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    close_reason: Mapped[str | None] = mapped_column(String(50))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    rating_comment: Mapped[str | None] = mapped_column(String(500))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    session: Mapped[ChatSession] = relationship(back_populates="tickets")
