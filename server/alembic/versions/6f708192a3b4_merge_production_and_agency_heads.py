"""Merge production boundary and agency repair index histories.

Revision ID: 6f708192a3b4
Revises: 5e6f708192a3, f7a8b9c0d1e2
Create Date: 2026-11-05
"""

revision = "6f708192a3b4"
down_revision = ("5e6f708192a3", "f7a8b9c0d1e2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Both parent branches contain their own schema changes."""


def downgrade() -> None:
    """Splitting the version graph does not itself change the schema."""
