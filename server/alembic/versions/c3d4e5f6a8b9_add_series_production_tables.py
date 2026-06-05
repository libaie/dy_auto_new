"""add series production tables

Revision ID: c3d4e5f6a8b9
Revises: 9f1a2b3c4d5e
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a8b9"
down_revision: Union[str, Sequence[str], None] = "9f1a2b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("active_version", sa.Integer(), nullable=False),
        sa.Column("target_total_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("budget_limit", sa.Float(), nullable=True),
        sa.Column("current_cost", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_production_plans_series_id", "production_plans", ["series_id"])
    op.create_index("idx_production_plans_status", "production_plans", ["status"])

    op.create_table(
        "production_plan_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("style_lock_json", sa.JSON(), nullable=True),
        sa.Column("model_config_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("prompt_policy_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_id", "version", name="uq_production_plan_version"),
    )
    op.create_index("idx_production_plan_versions_plan_id", "production_plan_versions", ["plan_id"])

    op.create_table(
        "production_episodes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_id", "episode_id", name="uq_production_episode_plan_episode"),
    )
    op.create_index("idx_production_episodes_plan_id", "production_episodes", ["plan_id"])
    op.create_index("idx_production_episodes_episode_id", "production_episodes", ["episode_id"])
    op.create_index("idx_production_episodes_status", "production_episodes", ["status"])

    op.create_table(
        "production_scenes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("episode_plan_id", sa.String(length=36), sa.ForeignKey("production_episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(length=100), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("location_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("episode_plan_id", "scene_id", name="uq_production_scene_episode_scene"),
    )
    op.create_index("idx_production_scenes_episode_plan_id", "production_scenes", ["episode_plan_id"])
    op.create_index("idx_production_scenes_status", "production_scenes", ["status"])

    op.create_table(
        "production_shots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scene_plan_id", sa.String(length=36), sa.ForeignKey("production_scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_id", sa.String(length=100), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("character_ids", sa.JSON(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("emotion", sa.String(length=50), nullable=True),
        sa.Column("shot_type", sa.String(length=50), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("scene_plan_id", "shot_id", name="uq_production_shot_scene_shot"),
    )
    op.create_index("idx_production_shots_scene_plan_id", "production_shots", ["scene_plan_id"])
    op.create_index("idx_production_shots_status", "production_shots", ["status"])

    op.create_table(
        "production_segments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("shot_plan_id", sa.String(length=36), sa.ForeignKey("production_shots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_segment_id", sa.String(length=36), sa.ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("segment_id", sa.String(length=100), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("continuity_mode", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous_end_frame_url", sa.Text(), nullable=True),
        sa.Column("expected_end_state", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("image_prompt", sa.Text(), nullable=False),
        sa.Column("video_prompt", sa.Text(), nullable=False),
        sa.Column("narration", sa.Text(), nullable=True),
        sa.Column("reference_roles_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("shot_plan_id", "segment_id", "version", name="uq_production_segment_version"),
    )
    op.create_index("idx_production_segments_shot_plan_id", "production_segments", ["shot_plan_id"])
    op.create_index("idx_production_segments_previous_segment_id", "production_segments", ["previous_segment_id"])
    op.create_index("idx_production_segments_status", "production_segments", ["status"])

    op.create_table(
        "production_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("retry_after", sa.DateTime(), nullable=True),
        sa.Column("lease_id", sa.String(length=80), nullable=True),
        sa.Column("leased_until", sa.DateTime(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_production_jobs_idempotency_key"),
    )
    op.create_index("idx_production_jobs_plan_id", "production_jobs", ["plan_id"])
    op.create_index("idx_production_jobs_target", "production_jobs", ["target_type", "target_id"])
    op.create_index("idx_production_jobs_status", "production_jobs", ["status"])

    op.create_table(
        "production_cost_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_plan_id", sa.String(length=36), sa.ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("segment_id", sa.String(length=36), sa.ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("model_config_id", sa.String(length=36), nullable=True),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("actual_cost", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("units_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_production_cost_events_plan_id", "production_cost_events", ["plan_id"])
    op.create_index("idx_production_cost_events_episode_plan_id", "production_cost_events", ["episode_plan_id"])
    op.create_index("idx_production_cost_events_segment_id", "production_cost_events", ["segment_id"])

    op.create_table(
        "video_collections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("included_episode_ids", sa.JSON(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_video_collections_series_id", "video_collections", ["series_id"])
    op.create_index("idx_video_collections_status", "video_collections", ["status"])

    with op.batch_alter_table("video_production_assets", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("production_segment_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("target_type", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("target_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("provider_task_id", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("prompt_hash", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_video_assets_production_segment_id",
            "production_segments",
            ["production_segment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("idx_video_assets_production_segment", ["production_segment_id"])
        batch.create_index("idx_video_assets_target", ["target_type", "target_id"])


def downgrade() -> None:
    with op.batch_alter_table("video_production_assets", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_index("idx_video_assets_target")
        batch.drop_index("idx_video_assets_production_segment")
        batch.drop_constraint("fk_video_assets_production_segment_id", type_="foreignkey")
        batch.drop_column("prompt_hash")
        batch.drop_column("provider_task_id")
        batch.drop_column("target_id")
        batch.drop_column("target_type")
        batch.drop_column("production_segment_id")

    op.drop_index("idx_video_collections_status", table_name="video_collections")
    op.drop_index("idx_video_collections_series_id", table_name="video_collections")
    op.drop_table("video_collections")

    op.drop_index("idx_production_cost_events_segment_id", table_name="production_cost_events")
    op.drop_index("idx_production_cost_events_episode_plan_id", table_name="production_cost_events")
    op.drop_index("idx_production_cost_events_plan_id", table_name="production_cost_events")
    op.drop_table("production_cost_events")

    op.drop_index("idx_production_jobs_status", table_name="production_jobs")
    op.drop_index("idx_production_jobs_target", table_name="production_jobs")
    op.drop_index("idx_production_jobs_plan_id", table_name="production_jobs")
    op.drop_table("production_jobs")

    op.drop_index("idx_production_segments_status", table_name="production_segments")
    op.drop_index("idx_production_segments_previous_segment_id", table_name="production_segments")
    op.drop_index("idx_production_segments_shot_plan_id", table_name="production_segments")
    op.drop_table("production_segments")

    op.drop_index("idx_production_shots_status", table_name="production_shots")
    op.drop_index("idx_production_shots_scene_plan_id", table_name="production_shots")
    op.drop_table("production_shots")

    op.drop_index("idx_production_scenes_status", table_name="production_scenes")
    op.drop_index("idx_production_scenes_episode_plan_id", table_name="production_scenes")
    op.drop_table("production_scenes")

    op.drop_index("idx_production_episodes_status", table_name="production_episodes")
    op.drop_index("idx_production_episodes_episode_id", table_name="production_episodes")
    op.drop_index("idx_production_episodes_plan_id", table_name="production_episodes")
    op.drop_table("production_episodes")

    op.drop_index("idx_production_plan_versions_plan_id", table_name="production_plan_versions")
    op.drop_table("production_plan_versions")

    op.drop_index("idx_production_plans_status", table_name="production_plans")
    op.drop_index("idx_production_plans_series_id", table_name="production_plans")
    op.drop_table("production_plans")
