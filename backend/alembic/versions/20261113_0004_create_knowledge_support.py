"""create knowledge and support tables

Revision ID: 20261113_0004
Revises: 20261113_0003
Create Date: 2026-11-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20261113_0004"
down_revision: Union[str, None] = "20261113_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=True),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("doc_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "scope IN ('product', 'category', 'platform')",
            name="ck_knowledge_documents_scope_valid",
        ),
        sa.CheckConstraint(
            "doc_type IN ('detail', 'faq', 'size', 'care', 'policy')",
            name="ck_knowledge_documents_doc_type_valid",
        ),
        sa.CheckConstraint(
            "source IN ('seed', 'session_extraction', 'manual')",
            name="ck_knowledge_documents_source_valid",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_knowledge_documents_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_knowledge_documents_product_id_products",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_knowledge_documents_category_id_categories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_documents"),
    )
    op.create_index(
        "ix_knowledge_documents_product_id",
        "knowledge_documents",
        ["product_id"],
    )
    op.create_index(
        "ix_knowledge_documents_category_id",
        "knowledge_documents",
        ["category_id"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=True),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            name="fk_knowledge_chunks_document_id_knowledge_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_chunks"),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"]
    )
    op.create_index(
        "ix_knowledge_chunks_product_id", "knowledge_chunks", ["product_id"]
    )
    op.create_index(
        "ix_knowledge_chunks_category_id", "knowledge_chunks", ["category_id"]
    )
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_search_text_gin "
        "ON knowledge_chunks USING gin (to_tsvector('simple', search_text))"
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "slot_state",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('guide', 'support')", name="ck_chat_sessions_type_valid"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'waiting_human', 'human', 'closed')",
            name="ck_chat_sessions_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_chat_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_chat_sessions_product_id_products",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
    )
    op.create_index(
        "ix_chat_sessions_user_type_status",
        "chat_sessions",
        ["user_id", "type", "status"],
    )
    op.create_index("ix_chat_sessions_product_id", "chat_sessions", ["product_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_type", sa.String(length=20), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=True),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sender_type IN ('user', 'ai', 'agent', 'system')",
            name="ck_chat_messages_sender_type_valid",
        ),
        sa.CheckConstraint(
            "content_type IN "
            "('text', 'image', 'voice', 'product_cards', 'action_card', "
            "'system_event')",
            name="ck_chat_messages_content_type_valid",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name="fk_chat_messages_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="waiting", nullable=False),
        sa.Column("assigned_agent_id", sa.BigInteger(), nullable=True),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column(
            "extraction_status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("close_reason", sa.String(length=50), nullable=True),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("rating_comment", sa.String(length=500), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('waiting', 'connected', 'closed')",
            name="ck_support_tickets_status_valid",
        ),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'running', 'done', 'failed')",
            name="ck_support_tickets_extraction_status_valid",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating BETWEEN 1 AND 5)",
            name="ck_support_tickets_rating_range",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name="fk_support_tickets_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_support_tickets_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_support_tickets_product_id_products",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_agent_id"],
            ["users.id"],
            name="fk_support_tickets_assigned_agent_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_support_tickets"),
    )
    op.create_index(
        "ix_support_tickets_status_created",
        "support_tickets",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_support_tickets_session_id", "support_tickets", ["session_id"]
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])


def downgrade() -> None:
    op.drop_table("support_tickets")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
