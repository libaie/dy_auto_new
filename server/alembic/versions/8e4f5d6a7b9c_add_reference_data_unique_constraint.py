"""add_reference_data_unique_constraint

Revision ID: 8e4f5d6a7b9c
Revises: 7d63133d4c64
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8e4f5d6a7b9c'
down_revision: Union[str, Sequence[str], None] = '7d63133d4c64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'reference_data' not in set(inspector.get_table_names()):
        return
    columns = {column['name'] for column in inspector.get_columns('reference_data')}
    if {'category', 'value'}.issubset(columns):
        with op.batch_alter_table('reference_data') as batch:
            batch.create_unique_constraint(
                'uq_reference_data_category_value',
                ['category', 'value']
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'reference_data' not in set(inspector.get_table_names()):
        return
    with op.batch_alter_table('reference_data') as batch:
        batch.drop_constraint(
            'uq_reference_data_category_value',
            type_='unique'
        )
