"""add device_id to chain_instances

Revision ID: a1b2c3d4e5f6
Revises: 3145b6441241
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "3145b6441241"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Table may not exist on fresh DBs (they use init_db() → create_all).
    # Only alter if the table was created by a prior migration.
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    if "chain_instances" not in sa_inspect(bind).get_table_names():
        return
    with op.batch_alter_table("chain_instances") as batch_op:
        batch_op.add_column(sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chain_instances") as batch_op:
        batch_op.drop_column("device_id")
