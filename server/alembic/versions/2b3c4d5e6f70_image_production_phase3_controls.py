from alembic import op
import sqlalchemy as sa


revision = "2b3c4d5e6f70"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_production_cost_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=220), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False, server_default="image_generation"),
        sa.Column("strategy_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_version", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actual_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("units_json", sa.JSON(), nullable=True),
        sa.Column("estimate_source", sa.String(length=40), nullable=False, server_default="policy"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["image_creation_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["image_creation_assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_image_cost_event_key"),
    )
    op.create_index("idx_image_cost_events_task", "image_production_cost_events", ["task_id"])
    op.create_index("idx_image_cost_events_event_type", "image_production_cost_events", ["event_type"])
    op.create_index("idx_image_cost_events_strategy", "image_production_cost_events", ["strategy_id", "strategy_version"])
    op.create_index("idx_image_cost_events_created", "image_production_cost_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_image_cost_events_created", table_name="image_production_cost_events")
    op.drop_index("idx_image_cost_events_strategy", table_name="image_production_cost_events")
    op.drop_index("idx_image_cost_events_event_type", table_name="image_production_cost_events")
    op.drop_index("idx_image_cost_events_task", table_name="image_production_cost_events")
    op.drop_table("image_production_cost_events")
