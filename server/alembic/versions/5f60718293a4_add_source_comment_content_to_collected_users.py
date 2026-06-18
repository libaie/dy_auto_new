"""add source comment content to collected users

Revision ID: 5f60718293a4
Revises: 4e5f60718293
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f60718293a4"
down_revision: Union[str, Sequence[str], None] = "4e5f60718293"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "collected_users" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("collected_users")}
    if "source_comment_content" in existing:
        return
    with op.batch_alter_table("collected_users") as batch_op:
        batch_op.add_column(sa.Column("source_comment_content", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "collected_users" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("collected_users")}
    if "source_comment_content" not in existing:
        return
    with op.batch_alter_table("collected_users") as batch_op:
        batch_op.drop_column("source_comment_content")
