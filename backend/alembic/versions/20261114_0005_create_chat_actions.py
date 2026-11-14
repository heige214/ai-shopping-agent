"""create chat actions table

Revision ID: 20261114_0005
Revises: 20261113_0004
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261114_0005"
down_revision: Union[str, None] = "20261113_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "executed_at", sa.DateTime(timezone=True), nullable=True
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
        sa.CheckConstraint(
            "action_type IN ('add_to_cart')",
            name="ck_chat_actions_action_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'executed', 'failed')",
            name="ck_chat_actions_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name="fk_chat_actions_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name="fk_chat_actions_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_actions"),
    )
    op.create_index(
        "ix_chat_actions_session_id", "chat_actions", ["session_id"]
    )
    op.create_index(
        "ix_chat_actions_message_id", "chat_actions", ["message_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_actions_message_id", table_name="chat_actions")
    op.drop_index("ix_chat_actions_session_id", table_name="chat_actions")
    op.drop_table("chat_actions")
