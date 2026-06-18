"""add agency creative patches

Revision ID: 2c3d4e5f6071
Revises: 1b2c3d4e5f60
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa


revision = "2c3d4e5f6071"
down_revision = "1b2c3d4e5f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agency_creative_patches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("series_id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("production_plan_id", sa.String(length=36), nullable=True),
        sa.Column("production_episode_id", sa.String(length=36), nullable=True),
        sa.Column("production_segment_id", sa.String(length=36), nullable=True),
        sa.Column("source_invocation_id", sa.String(length=36), nullable=True),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("expert_id", sa.String(length=80), nullable=False),
        sa.Column("patch_type", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=False),
        sa.Column("after_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_episode_id"], ["production_episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_plan_id"], ["production_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_segment_id"], ["production_segments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["video_production_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_invocation_id"], ["agency_expert_invocations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_agency_creative_patches_series_created",
        "agency_creative_patches",
        ["series_id", "created_at"],
    )
    op.create_index(
        "idx_agency_creative_patches_run_status",
        "agency_creative_patches",
        ["run_id", "status"],
    )
    op.create_index(
        "idx_agency_creative_patches_invocation",
        "agency_creative_patches",
        ["source_invocation_id"],
    )
    op.create_index(
        "idx_agency_creative_patches_target_status",
        "agency_creative_patches",
        ["target_type", "target_id", "status"],
    )
    op.create_index(
        "idx_agency_creative_patches_plan_stage_status",
        "agency_creative_patches",
        ["production_plan_id", "stage", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_agency_creative_patches_plan_stage_status", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_target_status", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_invocation", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_run_status", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_series_created", table_name="agency_creative_patches")
    op.drop_table("agency_creative_patches")
