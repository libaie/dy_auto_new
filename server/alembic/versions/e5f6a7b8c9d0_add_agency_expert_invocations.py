"""add agency expert invocations

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agency_expert_invocations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "retry_of_invocation_id",
            sa.String(length=36),
            sa.ForeignKey("agency_expert_invocations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("production_plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("production_episode_id", sa.String(length=36), sa.ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("production_segment_id", sa.String(length=36), sa.ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pipeline_run_id", sa.String(length=36), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("expert_id", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("execution_status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("result_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("input_summary_json", sa.JSON(), nullable=True),
        sa.Column("output_summary_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("source_repo", sa.String(length=120), nullable=False, server_default="jnMetaCode/agency-agents-zh"),
        sa.Column("source_commit", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("source_path", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("source_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("model_config_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("token_usage_json", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("repair_action", sa.Text(), nullable=True),
        sa.Column("repair_route", sa.Text(), nullable=True),
        sa.Column("repair_target_type", sa.String(length=80), nullable=True),
        sa.Column("repair_target_ids_json", sa.JSON(), nullable=True),
        sa.Column("retry_scope", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_agency_invocations_series_created",
        "agency_expert_invocations",
        ["series_id", "created_at"],
    )
    op.create_index(
        "idx_agency_invocations_series_run_stage",
        "agency_expert_invocations",
        ["series_id", "run_id", "stage"],
    )
    op.create_index(
        "idx_agency_invocations_run_stage_created",
        "agency_expert_invocations",
        ["run_id", "stage", "created_at"],
    )
    op.create_index(
        "idx_agency_invocations_pipeline_stage_created",
        "agency_expert_invocations",
        ["pipeline_run_id", "stage", "created_at"],
    )
    op.create_index(
        "idx_agency_invocations_plan_episode_stage",
        "agency_expert_invocations",
        ["production_plan_id", "production_episode_id", "stage"],
    )
    op.create_index(
        "idx_agency_invocations_expert_result_created",
        "agency_expert_invocations",
        ["expert_id", "result_status", "created_at"],
    )
    op.create_index(
        "idx_agency_invocations_error_created",
        "agency_expert_invocations",
        ["error_code", "created_at"],
    )
    op.create_index(
        "idx_agency_invocations_idempotency",
        "agency_expert_invocations",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_agency_invocations_idempotency", table_name="agency_expert_invocations")
    op.drop_index("idx_agency_invocations_error_created", table_name="agency_expert_invocations")
    op.drop_index("idx_agency_invocations_expert_result_created", table_name="agency_expert_invocations")
    op.drop_index("idx_agency_invocations_plan_episode_stage", table_name="agency_expert_invocations")
    op.drop_index("idx_agency_invocations_pipeline_stage_created", table_name="agency_expert_invocations")
    op.drop_index("idx_agency_invocations_run_stage_created", table_name="agency_expert_invocations")
    op.drop_index("idx_agency_invocations_series_run_stage", table_name="agency_expert_invocations")
    op.drop_index("idx_agency_invocations_series_created", table_name="agency_expert_invocations")
    op.drop_table("agency_expert_invocations")
