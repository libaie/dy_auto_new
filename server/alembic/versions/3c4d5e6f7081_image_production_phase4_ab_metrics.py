"""image production phase4 ab metrics

Revision ID: 3c4d5e6f7081
Revises: 2b3c4d5e6f70
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c4d5e6f7081"
down_revision: Union[str, Sequence[str], None] = "2b3c4d5e6f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_production_ab_groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("source_request_hash", sa.String(length=80), nullable=False),
        sa.Column("prompt_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("cost_confirmation_json", sa.JSON(), nullable=True),
        sa.Column("winner_attempt_id", sa.String(length=36), nullable=True),
        sa.Column("decision_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("idempotency_key", name="uq_image_ab_group_idempotency_key"),
    )
    op.create_index("idx_image_ab_groups_status", "image_production_ab_groups", ["status"])
    op.create_index("idx_image_ab_groups_created", "image_production_ab_groups", ["created_at"])
    op.create_index("idx_image_ab_groups_winner", "image_production_ab_groups", ["winner_attempt_id"])

    op.create_table(
        "image_production_ab_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "group_id",
            sa.String(length=36),
            sa.ForeignKey("image_production_ab_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("image_creation_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="creating"),
        sa.Column("metrics_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("human_decision_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("group_id", "strategy_id", "strategy_version", name="uq_image_ab_attempt_strategy"),
    )
    op.create_index("idx_image_ab_attempts_group", "image_production_ab_attempts", ["group_id"])
    op.create_index("idx_image_ab_attempts_task", "image_production_ab_attempts", ["task_id"])
    op.create_index("idx_image_ab_attempts_status", "image_production_ab_attempts", ["status"])

    op.create_table(
        "image_production_metrics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("human_pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repaint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_latency_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("average_cost_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "uq_image_metric_strategy_version_model",
        "image_production_metrics",
        ["strategy_id", "strategy_version", sa.text("coalesce(model_id, '__strategy__')")],
        unique=True,
    )
    op.create_index("idx_image_metrics_strategy", "image_production_metrics", ["strategy_id", "strategy_version"])
    op.create_index("idx_image_metrics_updated", "image_production_metrics", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_image_metrics_updated", table_name="image_production_metrics")
    op.drop_index("idx_image_metrics_strategy", table_name="image_production_metrics")
    op.drop_index("uq_image_metric_strategy_version_model", table_name="image_production_metrics")
    op.drop_table("image_production_metrics")

    op.drop_index("idx_image_ab_attempts_status", table_name="image_production_ab_attempts")
    op.drop_index("idx_image_ab_attempts_task", table_name="image_production_ab_attempts")
    op.drop_index("idx_image_ab_attempts_group", table_name="image_production_ab_attempts")
    op.drop_table("image_production_ab_attempts")

    op.drop_index("idx_image_ab_groups_winner", table_name="image_production_ab_groups")
    op.drop_index("idx_image_ab_groups_created", table_name="image_production_ab_groups")
    op.drop_index("idx_image_ab_groups_status", table_name="image_production_ab_groups")
    op.drop_table("image_production_ab_groups")
