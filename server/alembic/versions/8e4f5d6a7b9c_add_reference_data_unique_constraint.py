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
    op.create_unique_constraint(
        'uq_reference_data_category_value',
        'reference_data',
        ['category', 'value']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_reference_data_category_value',
        'reference_data',
        type_='unique'
    )
