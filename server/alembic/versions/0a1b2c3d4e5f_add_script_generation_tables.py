"""add script generation tables

Revision ID: 0a1b2c3d4e5f
Revises: 5e6f708192a3, f7a8b9c0d1e2
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = ("5e6f708192a3", "f7a8b9c0d1e2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "episode_scripts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_run_id", sa.String(length=36), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_prompt", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("agency_trace_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_episode_scripts_series_episode", "episode_scripts", ["series_id", "episode_id"])
    op.create_index("idx_episode_scripts_pipeline_run", "episode_scripts", ["pipeline_run_id"])
    op.create_index("idx_episode_scripts_status", "episode_scripts", ["status"])

    op.create_table(
        "script_dramatic_beats",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("script_id", sa.String(length=36), sa.ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("beat_type", sa.String(length=40), nullable=False),
        sa.Column("emotional_value", sa.String(length=40), nullable=False),
        sa.Column("plot_summary", sa.Text(), nullable=False),
        sa.UniqueConstraint("script_id", "order_index", name="uq_script_dramatic_beat_order"),
    )
    op.create_index("idx_script_dramatic_beats_script_id", "script_dramatic_beats", ["script_id"])
    op.create_index("idx_script_dramatic_beats_type", "script_dramatic_beats", ["beat_type"])

    op.create_table(
        "script_scene_outlines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("script_id", sa.String(length=36), sa.ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("dramatic_beat_type", sa.String(length=40), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("characters_json", sa.JSON(), nullable=True),
        sa.Column("conflict", sa.Text(), nullable=False),
        sa.Column("emotional_turn", sa.Text(), nullable=False),
        sa.Column("visual_mandate", sa.Text(), nullable=False),
        sa.UniqueConstraint("script_id", "scene_number", name="uq_script_scene_outline_number"),
    )
    op.create_index("idx_script_scene_outlines_script_id", "script_scene_outlines", ["script_id"])

    op.create_table(
        "script_visual_shots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("script_id", sa.String(length=36), sa.ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_number", sa.Integer(), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("beat_type", sa.String(length=40), nullable=False),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("visual_prompt", sa.Text(), nullable=False),
        sa.Column("video_prompt", sa.Text(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.UniqueConstraint("script_id", "shot_number", name="uq_script_visual_shot_number"),
    )
    op.create_index("idx_script_visual_shots_script_id", "script_visual_shots", ["script_id"])
    op.create_index("idx_script_visual_shots_scene", "script_visual_shots", ["script_id", "scene_number"])


def downgrade() -> None:
    op.drop_index("idx_script_visual_shots_scene", table_name="script_visual_shots")
    op.drop_index("idx_script_visual_shots_script_id", table_name="script_visual_shots")
    op.drop_table("script_visual_shots")
    op.drop_index("idx_script_scene_outlines_script_id", table_name="script_scene_outlines")
    op.drop_table("script_scene_outlines")
    op.drop_index("idx_script_dramatic_beats_type", table_name="script_dramatic_beats")
    op.drop_index("idx_script_dramatic_beats_script_id", table_name="script_dramatic_beats")
    op.drop_table("script_dramatic_beats")
    op.drop_index("idx_episode_scripts_status", table_name="episode_scripts")
    op.drop_index("idx_episode_scripts_pipeline_run", table_name="episode_scripts")
    op.drop_index("idx_episode_scripts_series_episode", table_name="episode_scripts")
    op.drop_table("episode_scripts")
