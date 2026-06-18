"""add asset anchor tables

Revision ID: 1b2c3d4e5f60
Revises: 0a1b2c3d4e5f
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1b2c3d4e5f60"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "character_anchors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("character_id", sa.String(length=36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("reference_slot", sa.String(length=80), nullable=False, server_default="avatar_front_url"),
        sa.Column("base_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("anchor_image_url", sa.Text(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("ref_mode", sa.String(length=80), nullable=False, server_default="character_face"),
        sa.Column("provider_options_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("character_id", "reference_slot", name="uq_character_anchor_slot"),
    )
    op.create_index("idx_character_anchors_character_id", "character_anchors", ["character_id"])
    op.create_index("idx_character_anchors_status", "character_anchors", ["status"])

    op.create_table(
        "scene_anchors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scene_id", sa.String(length=36), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("reference_slot", sa.String(length=80), nullable=False, server_default="reference_wideshot_url"),
        sa.Column("environment_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("anchor_image_url", sa.Text(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("ref_mode", sa.String(length=80), nullable=False, server_default="scene_environment"),
        sa.Column("provider_options_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("scene_id", "reference_slot", name="uq_scene_anchor_slot"),
    )
    op.create_index("idx_scene_anchors_scene_id", "scene_anchors", ["scene_id"])
    op.create_index("idx_scene_anchors_status", "scene_anchors", ["status"])


def downgrade() -> None:
    op.drop_index("idx_scene_anchors_status", table_name="scene_anchors")
    op.drop_index("idx_scene_anchors_scene_id", table_name="scene_anchors")
    op.drop_table("scene_anchors")
    op.drop_index("idx_character_anchors_status", table_name="character_anchors")
    op.drop_index("idx_character_anchors_character_id", table_name="character_anchors")
    op.drop_table("character_anchors")
