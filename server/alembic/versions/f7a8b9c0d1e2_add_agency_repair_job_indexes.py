"""add agency repair job indexes

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_production_jobs_plan_stage_status",
        "production_jobs",
        ["plan_id", "stage", "status"],
    )
    op.create_index(
        "idx_production_jobs_stage_created_at",
        "production_jobs",
        ["stage", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_production_jobs_stage_created_at", table_name="production_jobs")
    op.drop_index("idx_production_jobs_plan_stage_status", table_name="production_jobs")
