"""add_video_production_tables

Revision ID: 9f1a2b3c4d5e
Revises: 8f9a0b1c2d3e
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f1a2b3c4d5e"
down_revision: Union[str, Sequence[str], None] = "8f9a0b1c2d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_production_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_stage", sa.String(length=40), nullable=False),
        sa.Column("pixelle_stage_task_id", sa.String(length=100), nullable=True),
        sa.Column("storyboard_json", sa.JSON(), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("edit_manifest_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_video_production_runs_series_episode", "video_production_runs", ["series_id", "episode_id"])
    op.create_index("idx_video_production_runs_status", "video_production_runs", ["status"])

    op.create_table(
        "video_production_assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("frame_id", sa.String(length=100), nullable=False),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("pixelle_task_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", "frame_id", "asset_type", "version", name="uq_video_asset_version"),
    )
    op.create_index("idx_video_assets_run_stage", "video_production_assets", ["run_id", "stage"])
    op.create_index("idx_video_assets_run_frame", "video_production_assets", ["run_id", "frame_id"])
    op.create_index("idx_video_assets_status", "video_production_assets", ["status"])

    op.create_table(
        "video_review_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("video_production_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("criteria_json", sa.JSON(), nullable=True),
        sa.Column("issues_json", sa.JSON(), nullable=True),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_video_review_asset", "video_review_records", ["asset_id"])
    op.create_index("idx_video_review_run", "video_review_records", ["run_id"])
    op.create_index("idx_video_review_status", "video_review_records", ["status"])


def downgrade() -> None:
    op.drop_index("idx_video_review_status", table_name="video_review_records")
    op.drop_index("idx_video_review_run", table_name="video_review_records")
    op.drop_index("idx_video_review_asset", table_name="video_review_records")
    op.drop_table("video_review_records")

    op.drop_index("idx_video_assets_status", table_name="video_production_assets")
    op.drop_index("idx_video_assets_run_frame", table_name="video_production_assets")
    op.drop_index("idx_video_assets_run_stage", table_name="video_production_assets")
    op.drop_table("video_production_assets")

    op.drop_index("idx_video_production_runs_status", table_name="video_production_runs")
    op.drop_index("idx_video_production_runs_series_episode", table_name="video_production_runs")
    op.drop_table("video_production_runs")
