"""add conversation messages ledger

Revision ID: 6a7b8c9d0e1f
Revises: 5f60718293a4
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a7b8c9d0e1f"
down_revision: Union[str, Sequence[str], None] = "5f60718293a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("device_id", sa.String(length=36), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("dm_sequence_id", sa.String(length=36), nullable=True),
        sa.Column("message_order", sa.Integer(), nullable=True),
        sa.Column("message_key", sa.String(length=200), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False, server_default="outbound"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="sent"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("conversation_id", "message_key", name="uq_conversation_message_key"),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_index("ix_conversation_messages_conversation_order", "conversation_messages", ["conversation_id", "message_order"])
    op.create_index("ix_conversation_messages_dm_sequence_id", "conversation_messages", ["dm_sequence_id"])
    op.create_index("ix_conversation_messages_task_id", "conversation_messages", ["task_id"])
    op.create_index("ix_conversation_messages_status", "conversation_messages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_status", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_task_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_dm_sequence_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_conversation_order", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")