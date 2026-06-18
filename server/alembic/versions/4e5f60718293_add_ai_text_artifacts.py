"""add ai text artifacts

Revision ID: 4e5f60718293
Revises: 3d4e5f607182
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4e5f60718293"
down_revision: Union[str, Sequence[str], None] = "3d4e5f607182"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_text_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("series_id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("production_plan_id", sa.String(length=36), nullable=True),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("parent_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("review_trace_json", sa.JSON(), nullable=True),
        sa.Column("consumer_trace_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(), nullable=True),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_artifact_id"], ["ai_text_artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_plan_id"], ["production_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["video_production_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_type", "target_id", "artifact_type", "version", name="uq_ai_text_artifact_version"),
    )
    op.create_index(
        "idx_ai_text_artifacts_series_type_status",
        "ai_text_artifacts",
        ["series_id", "artifact_type", "status"],
    )
    op.create_index(
        "idx_ai_text_artifacts_episode_type_status",
        "ai_text_artifacts",
        ["episode_id", "artifact_type", "status"],
    )
    op.create_index(
        "idx_ai_text_artifacts_target_type",
        "ai_text_artifacts",
        ["target_type", "target_id", "artifact_type"],
    )
    op.create_index("idx_ai_text_artifacts_parent", "ai_text_artifacts", ["parent_artifact_id"])

    op.create_table(
        "ai_text_artifact_consumers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=False),
        sa.Column("consumer_type", sa.String(length=80), nullable=False),
        sa.Column("consumer_id", sa.String(length=120), nullable=False),
        sa.Column("series_id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["artifact_id"], ["ai_text_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["video_production_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_text_artifact_consumers_artifact", "ai_text_artifact_consumers", ["artifact_id"])
    op.create_index(
        "idx_ai_text_artifact_consumers_consumer",
        "ai_text_artifact_consumers",
        ["consumer_type", "consumer_id"],
    )
    op.create_index("idx_ai_text_artifact_consumers_run", "ai_text_artifact_consumers", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_ai_text_artifact_consumers_run", table_name="ai_text_artifact_consumers")
    op.drop_index("idx_ai_text_artifact_consumers_consumer", table_name="ai_text_artifact_consumers")
    op.drop_index("idx_ai_text_artifact_consumers_artifact", table_name="ai_text_artifact_consumers")
    op.drop_table("ai_text_artifact_consumers")
    op.drop_index("idx_ai_text_artifacts_parent", table_name="ai_text_artifacts")
    op.drop_index("idx_ai_text_artifacts_target_type", table_name="ai_text_artifacts")
    op.drop_index("idx_ai_text_artifacts_episode_type_status", table_name="ai_text_artifacts")
    op.drop_index("idx_ai_text_artifacts_series_type_status", table_name="ai_text_artifacts")
    op.drop_table("ai_text_artifacts")
