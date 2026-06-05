"""image production strategy control plane

Revision ID: 1a2b3c4d5e6f
Revises: f6a7b8c9d0e1
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_production_policy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("policy_type", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_type", "name", "version", name="uq_image_policy_version"),
    )
    op.create_index(
        "idx_image_policy_versions_type_status",
        "image_production_policy_versions",
        ["policy_type", "status"],
    )

    op.create_table(
        "image_production_strategies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("destination_role", sa.String(length=80), nullable=False),
        sa.Column("supported_modes_json", sa.JSON(), nullable=False),
        sa.Column("default_model_id", sa.String(length=36), nullable=True),
        sa.Column("fallback_model_ids_json", sa.JSON(), nullable=False),
        sa.Column("common_parameters_json", sa.JSON(), nullable=False),
        sa.Column("provider_options_json", sa.JSON(), nullable=False),
        sa.Column("review_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("cost_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("capacity_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("ab_test_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["review_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cost_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["capacity_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ab_test_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_image_strategy_slug"),
    )
    op.create_index("idx_image_strategies_role_status", "image_production_strategies", ["destination_role", "status"])
    op.create_index("idx_image_strategies_status_updated", "image_production_strategies", ["status", "updated_at"])

    op.create_table(
        "image_production_strategy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["image_production_strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "version", name="uq_image_strategy_version"),
    )
    op.create_index("idx_image_strategy_versions_strategy", "image_production_strategy_versions", ["strategy_id"])

    op.create_table(
        "image_selection_previews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_version", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("destination_role", sa.String(length=80), nullable=True),
        sa.Column("model_id", sa.String(length=36), nullable=True),
        sa.Column("selected_model_id", sa.String(length=36), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["image_production_strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_image_selection_previews_hash", "image_selection_previews", ["request_hash"])
    op.create_index("idx_image_selection_previews_expires", "image_selection_previews", ["expires_at"])
    op.create_index("idx_image_selection_previews_user_created", "image_selection_previews", ["user_id", "created_at"])

    op.add_column("image_creation_tasks", sa.Column("strategy_id", sa.String(length=36), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("strategy_version", sa.Integer(), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("strategy_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("selection_explanation_json", sa.JSON(), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("selection_preview_id", sa.String(length=36), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("selection_preview_request_hash", sa.String(length=64), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("fallback_trace_json", sa.JSON(), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("queue_job_id", sa.String(length=36), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("capacity_lease_id", sa.String(length=80), nullable=True))
    op.add_column("image_creation_tasks", sa.Column("ab_test_group_id", sa.String(length=36), nullable=True))
    op.create_index("idx_image_tasks_strategy", "image_creation_tasks", ["strategy_id", "strategy_version"])
    op.create_index("idx_image_tasks_selection_preview", "image_creation_tasks", ["selection_preview_id"])


def downgrade() -> None:
    op.drop_index("idx_image_tasks_selection_preview", table_name="image_creation_tasks")
    op.drop_index("idx_image_tasks_strategy", table_name="image_creation_tasks")
    op.drop_column("image_creation_tasks", "ab_test_group_id")
    op.drop_column("image_creation_tasks", "capacity_lease_id")
    op.drop_column("image_creation_tasks", "queue_job_id")
    op.drop_column("image_creation_tasks", "fallback_trace_json")
    op.drop_column("image_creation_tasks", "selection_preview_request_hash")
    op.drop_column("image_creation_tasks", "selection_preview_id")
    op.drop_column("image_creation_tasks", "selection_explanation_json")
    op.drop_column("image_creation_tasks", "strategy_snapshot_json")
    op.drop_column("image_creation_tasks", "strategy_version")
    op.drop_column("image_creation_tasks", "strategy_id")

    op.drop_index("idx_image_selection_previews_user_created", table_name="image_selection_previews")
    op.drop_index("idx_image_selection_previews_expires", table_name="image_selection_previews")
    op.drop_index("idx_image_selection_previews_hash", table_name="image_selection_previews")
    op.drop_table("image_selection_previews")

    op.drop_index("idx_image_strategy_versions_strategy", table_name="image_production_strategy_versions")
    op.drop_table("image_production_strategy_versions")

    op.drop_index("idx_image_strategies_status_updated", table_name="image_production_strategies")
    op.drop_index("idx_image_strategies_role_status", table_name="image_production_strategies")
    op.drop_table("image_production_strategies")

    op.drop_index("idx_image_policy_versions_type_status", table_name="image_production_policy_versions")
    op.drop_table("image_production_policy_versions")
