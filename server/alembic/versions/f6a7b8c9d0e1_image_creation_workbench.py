"""image creation workbench

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_creation_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("output_mode", sa.String(length=20), nullable=False, server_default="single"),
        sa.Column("capability_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_asset_id", sa.String(length=36), nullable=True),
        sa.Column("reference_images_json", sa.JSON(), nullable=True),
        sa.Column("destination_role", sa.String(length=60), nullable=True),
        sa.Column("destination_context_json", sa.JSON(), nullable=True),
        sa.Column("size", sa.String(length=30), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("output_format", sa.String(length=20), nullable=True),
        sa.Column("response_format", sa.String(length=20), nullable=True),
        sa.Column("watermark", sa.Boolean(), nullable=True),
        sa.Column("provider_options_json", sa.JSON(), nullable=True),
        sa.Column("estimated_cost_json", sa.JSON(), nullable=True),
        sa.Column("cost_status", sa.String(length=30), nullable=False, server_default="not_estimated"),
        sa.Column("requires_cost_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("storage_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("model_scene_key", sa.String(length=80), nullable=True),
        sa.Column("model_scene", sa.String(length=80), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("external_task_id", sa.String(length=120), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("target_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_policy", sa.String(length=40), nullable=True),
        sa.Column("selected_asset_id", sa.String(length=36), nullable=True),
        sa.Column("selected_asset_version", sa.Integer(), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("pixelle_payload_json", sa.JSON(), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=True),
        sa.Column("provider_response_json", sa.JSON(), nullable=True),
        sa.Column("pixelle_task_id", sa.String(length=120), nullable=True),
        sa.Column("partial_results_json", sa.JSON(), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("repair_action", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_image_task_idempotency_key"),
        sa.UniqueConstraint("pixelle_task_id", name="uq_image_task_pixelle_task_id"),
    )
    op.create_index("idx_image_tasks_user", "image_creation_tasks", ["user_id"])
    op.create_index("idx_image_tasks_status", "image_creation_tasks", ["status"])
    op.create_index("idx_image_tasks_status_created", "image_creation_tasks", ["status", "created_at"])
    op.create_index("idx_image_tasks_series_episode", "image_creation_tasks", ["series_id", "episode_id"])
    op.create_index("idx_image_tasks_model_capability", "image_creation_tasks", ["model_scene_key", "capability_key"])
    op.create_index("idx_image_tasks_created", "image_creation_tasks", ["created_at"])

    op.create_table(
        "image_creation_assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_type", sa.String(length=30), nullable=False, server_default="image"),
        sa.Column("asset_kind", sa.String(length=30), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=80), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("seed", sa.String(length=120), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="review_pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_asset_id", sa.String(length=36), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("reference_images_json", sa.JSON(), nullable=True),
        sa.Column("slot_key", sa.String(length=160), nullable=False, server_default="default"),
        sa.Column("group_id", sa.String(length=80), nullable=True),
        sa.Column("group_index", sa.Integer(), nullable=True),
        sa.Column("destination_role", sa.String(length=60), nullable=True),
        sa.Column("destination_context_json", sa.JSON(), nullable=True),
        sa.Column("downstream_usage_json", sa.JSON(), nullable=True),
        sa.Column("provider_error_json", sa.JSON(), nullable=True),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("pixelle_task_id", sa.String(length=120), nullable=True),
        sa.Column("model_scene", sa.String(length=80), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("variant_index", sa.Integer(), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("audit_status", sa.String(length=30), nullable=True),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("ai_report_json", sa.JSON(), nullable=True),
        sa.Column("manual_review_status", sa.String(length=30), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("storage_status", sa.String(length=30), nullable=False, server_default="persisted"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("task_id", "slot_key", "version", name="uq_image_asset_slot_version"),
    )
    op.create_index(
        "uq_image_asset_canonical_slot_version",
        "image_creation_assets",
        [
            "task_id",
            sa.text("coalesce(group_id, slot_key, 'default')"),
            sa.text("coalesce(group_index, -1)"),
            "version",
        ],
        unique=True,
    )
    op.create_index("idx_image_assets_task", "image_creation_assets", ["task_id"])
    op.create_index("idx_image_assets_task_version", "image_creation_assets", ["task_id", "version"])
    op.create_index("idx_image_assets_status", "image_creation_assets", ["status"])
    op.create_index("idx_image_assets_audit_status", "image_creation_assets", ["audit_status"])
    op.create_index("idx_image_assets_destination", "image_creation_assets", ["destination_role"])
    op.create_index("idx_image_assets_series_episode", "image_creation_assets", ["series_id", "episode_id"])
    op.create_index("idx_image_assets_group", "image_creation_assets", ["group_id", "group_index"])
    op.create_index("idx_image_assets_source", "image_creation_assets", ["source_asset_id"])
    op.create_index("idx_image_assets_latest", "image_creation_assets", ["is_latest"])

    op.create_table(
        "image_creation_review_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("image_creation_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_type", sa.String(length=20), nullable=False),
        sa.Column("reviewer_type", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("criteria_json", sa.JSON(), nullable=True),
        sa.Column("issues_json", sa.JSON(), nullable=True),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("asset_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_latest_asset_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_image_review_asset", "image_creation_review_records", ["asset_id"])
    op.create_index("idx_image_review_task", "image_creation_review_records", ["task_id"])
    op.create_index("idx_image_review_status", "image_creation_review_records", ["status"])
    op.create_index(
        "idx_image_review_latest",
        "image_creation_review_records",
        ["asset_id", "asset_version", "is_latest_asset_review"],
    )
    op.create_index(
        "uq_image_review_latest_asset_version",
        "image_creation_review_records",
        ["asset_id", "asset_version"],
        unique=True,
        sqlite_where=sa.text("is_latest_asset_review = 1"),
        postgresql_where=sa.text("is_latest_asset_review = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_image_review_latest_asset_version", table_name="image_creation_review_records")
    op.drop_index("idx_image_review_latest", table_name="image_creation_review_records")
    op.drop_index("idx_image_review_status", table_name="image_creation_review_records")
    op.drop_index("idx_image_review_task", table_name="image_creation_review_records")
    op.drop_index("idx_image_review_asset", table_name="image_creation_review_records")
    op.drop_table("image_creation_review_records")

    op.drop_index("idx_image_assets_latest", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_source", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_group", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_series_episode", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_destination", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_audit_status", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_status", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_task_version", table_name="image_creation_assets")
    op.drop_index("idx_image_assets_task", table_name="image_creation_assets")
    op.drop_index("uq_image_asset_canonical_slot_version", table_name="image_creation_assets")
    op.drop_table("image_creation_assets")

    op.drop_index("idx_image_tasks_created", table_name="image_creation_tasks")
    op.drop_index("idx_image_tasks_model_capability", table_name="image_creation_tasks")
    op.drop_index("idx_image_tasks_series_episode", table_name="image_creation_tasks")
    op.drop_index("idx_image_tasks_status_created", table_name="image_creation_tasks")
    op.drop_index("idx_image_tasks_status", table_name="image_creation_tasks")
    op.drop_index("idx_image_tasks_user", table_name="image_creation_tasks")
    op.drop_table("image_creation_tasks")
