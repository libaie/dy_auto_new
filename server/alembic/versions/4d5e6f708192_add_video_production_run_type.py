"""add video production run type

Revision ID: 4d5e6f708192
Revises: 3c4d5e6f7081
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d5e6f708192"
down_revision: Union[str, Sequence[str], None] = "3c4d5e6f7081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("video_production_runs", reflect_kwargs={"resolve_fks": False}) as batch_op:
        batch_op.add_column(
            sa.Column(
                "run_type",
                sa.String(length=40),
                nullable=False,
                server_default="legacy_episode_run",
            )
        )
    op.create_index("idx_video_production_runs_type", "video_production_runs", ["run_type"])

    with op.batch_alter_table("video_production_runs", reflect_kwargs={"resolve_fks": False}) as batch_op:
        batch_op.alter_column(
            "run_type",
            existing_type=sa.String(length=40),
            server_default=None,
            existing_nullable=False,
        )


def downgrade() -> None:
    op.drop_index("idx_video_production_runs_type", table_name="video_production_runs")
    with op.batch_alter_table("video_production_runs", reflect_kwargs={"resolve_fks": False}) as batch_op:
        batch_op.drop_column("run_type")
