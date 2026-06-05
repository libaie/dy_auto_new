"""control plane convergence

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a8b9
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("video_production_runs", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("production_plan_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("production_episode_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column(
                "production_link_status",
                sa.String(length=30),
                nullable=False,
                server_default="legacy_unlinked",
            )
        )
        batch.create_foreign_key(
            "fk_video_runs_production_plan",
            "production_plans",
            ["production_plan_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_video_runs_production_episode",
            "production_episodes",
            ["production_episode_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "idx_video_production_runs_production_links",
            ["production_plan_id", "production_episode_id"],
        )
        batch.create_index("idx_video_production_runs_link_status", ["production_link_status"])

    with op.batch_alter_table("video_production_assets", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("production_shot_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("1")))
        batch.add_column(sa.Column("source_version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(
            sa.Column("copy_status", sa.String(length=30), nullable=False, server_default="registered")
        )
        batch.add_column(sa.Column("checksum", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_video_assets_production_shot_id",
            "production_shots",
            ["production_shot_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("idx_video_assets_production_shot", ["production_shot_id"])
        batch.create_index(
            "idx_video_assets_segment_latest",
            ["production_segment_id", "asset_type", "is_latest"],
        )

    with op.batch_alter_table("video_review_records", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("target_type", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("target_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("production_segment_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("asset_version", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("is_latest_asset_review", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )
        batch.create_foreign_key(
            "fk_video_reviews_production_segment_id",
            "production_segments",
            ["production_segment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("idx_video_review_target_version", ["target_type", "target_id", "asset_version"])

    with op.batch_alter_table("production_jobs", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("resume_status", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("blocked_reason", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("paused_at", sa.DateTime(), nullable=True))
        batch.create_index(
            "idx_production_jobs_plan_status_resume",
            ["plan_id", "status", "resume_status"],
        )

    op.create_table(
        "production_audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("production_plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("production_episode_id", sa.String(length=36), sa.ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("production_segment_id", sa.String(length=36), sa.ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_production_audit_events_run_id", "production_audit_events", ["run_id"])
    op.create_index("idx_production_audit_events_plan_id", "production_audit_events", ["production_plan_id"])
    op.create_index("idx_production_audit_events_segment_id", "production_audit_events", ["production_segment_id"])
    op.create_index("idx_production_audit_events_type", "production_audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_production_audit_events_type", table_name="production_audit_events")
    op.drop_index("idx_production_audit_events_segment_id", table_name="production_audit_events")
    op.drop_index("idx_production_audit_events_plan_id", table_name="production_audit_events")
    op.drop_index("idx_production_audit_events_run_id", table_name="production_audit_events")
    op.drop_table("production_audit_events")

    with op.batch_alter_table("production_jobs", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_index("idx_production_jobs_plan_status_resume")
        batch.drop_column("paused_at")
        batch.drop_column("blocked_reason")
        batch.drop_column("resume_status")

    with op.batch_alter_table("video_review_records", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_index("idx_video_review_target_version")
        batch.drop_constraint("fk_video_reviews_production_segment_id", type_="foreignkey")
        batch.drop_column("is_latest_asset_review")
        batch.drop_column("asset_version")
        batch.drop_column("production_segment_id")
        batch.drop_column("target_id")
        batch.drop_column("target_type")

    with op.batch_alter_table("video_production_assets", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_index("idx_video_assets_segment_latest")
        batch.drop_index("idx_video_assets_production_shot")
        batch.drop_constraint("fk_video_assets_production_shot_id", type_="foreignkey")
        batch.drop_column("size_bytes")
        batch.drop_column("checksum")
        batch.drop_column("copy_status")
        batch.drop_column("source_version")
        batch.drop_column("is_latest")
        batch.drop_column("production_shot_id")

    with op.batch_alter_table("video_production_runs", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_index("idx_video_production_runs_link_status")
        batch.drop_index("idx_video_production_runs_production_links")
        batch.drop_constraint("fk_video_runs_production_episode", type_="foreignkey")
        batch.drop_constraint("fk_video_runs_production_plan", type_="foreignkey")
        batch.drop_column("production_link_status")
        batch.drop_column("production_episode_id")
        batch.drop_column("production_plan_id")
