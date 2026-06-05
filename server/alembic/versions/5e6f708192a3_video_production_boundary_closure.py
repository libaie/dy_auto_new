"""video production boundary closure

Revision ID: 5e6f708192a3
Revises: 4d5e6f708192
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5e6f708192a3"
down_revision: Union[str, Sequence[str], None] = "4d5e6f708192"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_stage_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("production_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="reserved"),
        sa.Column("provider_task_id", sa.String(length=160), nullable=True),
        sa.Column("external_task_id", sa.String(length=160), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("response_summary_json", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_provider_stage_tasks_idempotency"),
    )
    op.create_index(
        "idx_provider_stage_tasks_run_stage_status",
        "provider_stage_tasks",
        ["run_id", "stage", "status"],
    )
    op.create_index(
        "idx_provider_stage_tasks_plan_stage_status",
        "provider_stage_tasks",
        ["plan_id", "stage", "status"],
    )
    op.create_index("idx_provider_stage_tasks_target", "provider_stage_tasks", ["target_type", "target_id"])
    op.create_index(
        "idx_provider_stage_tasks_provider_task_id",
        "provider_stage_tasks",
        ["provider_task_id"],
    )

    op.create_table(
        "provider_cost_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_stage_task_id", sa.String(length=36), sa.ForeignKey("provider_stage_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active_unsubmitted"),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reserved_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actual_cost", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("units_json", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "provider_stage_task_id",
            name="uq_provider_cost_reservation_stage_task",
        ),
    )
    op.create_index(
        "idx_provider_cost_reservations_plan_status",
        "provider_cost_reservations",
        ["plan_id", "status"],
    )
    op.create_index(
        "idx_provider_cost_reservations_expires",
        "provider_cost_reservations",
        ["expires_at", "status"],
    )

    with op.batch_alter_table("video_production_assets", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("storage_path", sa.Text(), nullable=True))
        batch.add_column(sa.Column("source_url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("storage_error_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("provider_response_summary_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("provider_stage_task_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_video_assets_provider_stage_task_id",
            "provider_stage_tasks",
            ["provider_stage_task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("idx_video_assets_provider_stage_task", ["provider_stage_task_id"])

    with op.batch_alter_table("video_review_records", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("reviewer_role", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("action", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("asset_snapshot_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("model_trace_summary_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("production_audit_events", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("actor_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("actor_role", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("production_audit_events", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_column("actor_role")
        batch.drop_column("actor_user_id")

    with op.batch_alter_table("video_review_records", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_column("model_trace_summary_json")
        batch.drop_column("asset_snapshot_json")
        batch.drop_column("action")
        batch.drop_column("reviewer_role")

    with op.batch_alter_table("video_production_assets", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_index("idx_video_assets_provider_stage_task")
        batch.drop_constraint("fk_video_assets_provider_stage_task_id", type_="foreignkey")
        batch.drop_column("provider_stage_task_id")
        batch.drop_column("provider_response_summary_json")
        batch.drop_column("storage_error_json")
        batch.drop_column("source_url")
        batch.drop_column("storage_path")

    op.drop_index("idx_provider_cost_reservations_expires", table_name="provider_cost_reservations")
    op.drop_index("idx_provider_cost_reservations_plan_status", table_name="provider_cost_reservations")
    op.drop_table("provider_cost_reservations")

    op.drop_index("idx_provider_stage_tasks_provider_task_id", table_name="provider_stage_tasks")
    op.drop_index("idx_provider_stage_tasks_target", table_name="provider_stage_tasks")
    op.drop_index("idx_provider_stage_tasks_plan_stage_status", table_name="provider_stage_tasks")
    op.drop_index("idx_provider_stage_tasks_run_stage_status", table_name="provider_stage_tasks")
    op.drop_table("provider_stage_tasks")
