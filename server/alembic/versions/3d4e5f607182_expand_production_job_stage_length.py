"""expand production job stage length

Revision ID: 3d4e5f607182
Revises: 2c3d4e5f6071
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d4e5f607182"
down_revision: Union[str, Sequence[str], None] = "2c3d4e5f6071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("production_jobs", reflect_kwargs={"resolve_fks": False}) as batch_op:
        batch_op.alter_column(
            "stage",
            existing_type=sa.String(length=40),
            type_=sa.String(length=80),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    too_long = bind.execute(
        sa.text("SELECT COUNT(*) FROM production_jobs WHERE length(stage) > 40")
    ).scalar() or 0
    if too_long:
        raise RuntimeError(
            "Cannot downgrade production_jobs.stage to length 40 while rows contain longer stage values."
        )
    with op.batch_alter_table("production_jobs", reflect_kwargs={"resolve_fks": False}) as batch_op:
        batch_op.alter_column(
            "stage",
            existing_type=sa.String(length=80),
            type_=sa.String(length=40),
            existing_nullable=False,
        )
