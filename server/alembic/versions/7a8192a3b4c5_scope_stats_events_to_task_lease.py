"""Scope stats operation idempotency to a task execution lease.

Revision ID: 7a8192a3b4c5
Revises: 6f708192a3b4
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = '7a8192a3b4c5'
down_revision = '6f708192a3b4'
branch_labels = None
depends_on = None

TABLE = 'stats_events'
CONSTRAINT = 'uq_stats_event_idempotent'
LEGACY_KEY = ['task_id', 'device_id', 'event_type', 'target_id', 'op_index']
LEASE_KEY = LEGACY_KEY + ['lease_id']


def upgrade():
    inspector = sa.inspect(op.get_bind())
    # StatsEvent was historically created by Base.metadata.create_all at
    # startup, not by a published revision. Fresh migrations leave its creation
    # to the current ORM instead of inventing a second partial table definition.
    if TABLE not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns(TABLE)}
    existing = next((constraint for constraint in inspector.get_unique_constraints(TABLE)
                     if constraint['name'] == CONSTRAINT), None)
    if 'lease_id' in columns and existing and existing['column_names'] == LEASE_KEY:
        return
    # Alembic recreates the SQLite table while preserving its rows/indexes/FKs;
    # other dialects, including MySQL, receive their native ALTER statements.
    with op.batch_alter_table(TABLE) as batch:
        if 'lease_id' not in columns:
            batch.add_column(sa.Column('lease_id', sa.String(36), nullable=False, server_default=''))
        if existing:
            batch.drop_constraint(CONSTRAINT, type_='unique')
        batch.create_unique_constraint(CONSTRAINT, LEASE_KEY)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns(TABLE)}
    if 'lease_id' not in columns:
        return
    table = sa.table(TABLE, *(sa.column(name) for name in LEGACY_KEY))
    collision = bind.execute(sa.select(sa.literal(1)).select_from(table).group_by(
        *(table.c[name] for name in LEGACY_KEY)
    ).having(sa.func.count() > 1).limit(1)).first()
    if collision:
        raise RuntimeError('Cannot downgrade stats_events: distinct leases share a legacy operation key')
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(CONSTRAINT, type_='unique')
        batch.create_unique_constraint(CONSTRAINT, LEGACY_KEY)
        batch.drop_column('lease_id')
