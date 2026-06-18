"""add ai video core tables

Revision ID: 8f9a0b1c2d3e
Revises: 8e4f5d6a7b9c
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f9a0b1c2d3e"
down_revision: Union[str, Sequence[str], None] = "8e4f5d6a7b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create_index_if_missing(name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    tables = _tables()

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("password_hash", sa.String(length=128), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("nickname", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("username", name="uq_users_username"),
        )
        _create_index_if_missing("ix_users_username", "users", ["username"], unique=True)

    if "characters" not in tables:
        op.create_table(
            "characters",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("role_type", sa.String(length=20), nullable=False),
            sa.Column("gender", sa.String(length=10), nullable=False),
            sa.Column("age_range", sa.String(length=20), nullable=True),
            sa.Column("personality", sa.Text(), nullable=True),
            sa.Column("appearance_desc", sa.Text(), nullable=True),
            sa.Column("outfit_desc", sa.Text(), nullable=True),
            sa.Column("avatar_front_url", sa.Text(), nullable=True),
            sa.Column("avatar_side_url", sa.Text(), nullable=True),
            sa.Column("avatar_threequarter_url", sa.Text(), nullable=True),
            sa.Column("avatar_fullbody_url", sa.Text(), nullable=True),
            sa.Column("default_voice_id", sa.String(length=100), nullable=True),
            sa.Column("meta_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if "scenes" not in tables:
        op.create_table(
            "scenes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("scene_type", sa.String(length=20), nullable=False),
            sa.Column("location_desc", sa.Text(), nullable=True),
            sa.Column("lighting", sa.String(length=50), nullable=True),
            sa.Column("mood", sa.String(length=50), nullable=True),
            sa.Column("reference_wideshot_url", sa.Text(), nullable=True),
            sa.Column("reference_midshot_url", sa.Text(), nullable=True),
            sa.Column("reference_aerial_url", sa.Text(), nullable=True),
            sa.Column("meta_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if "series" not in tables:
        op.create_table(
            "series",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("logline", sa.Text(), nullable=True),
            sa.Column("genre", sa.String(length=50), nullable=False),
            sa.Column("total_episodes", sa.Integer(), nullable=False),
            sa.Column("target_duration", sa.Integer(), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("pilot_first", sa.Boolean(), nullable=False),
            sa.Column("story_bible_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    tables = _tables()
    if "series_characters" not in tables:
        op.create_table(
            "series_characters",
            sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id"), primary_key=True),
            sa.Column("character_id", sa.String(length=36), sa.ForeignKey("characters.id"), primary_key=True),
        )

    if "series_scenes" not in tables:
        op.create_table(
            "series_scenes",
            sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id"), primary_key=True),
            sa.Column("scene_id", sa.String(length=36), sa.ForeignKey("scenes.id"), primary_key=True),
        )

    if "episodes" not in tables:
        op.create_table(
            "episodes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
            sa.Column("episode_number", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=True),
            sa.Column("script_json", sa.JSON(), nullable=True),
            sa.Column("storyboard_json", sa.JSON(), nullable=True),
            sa.Column("video_url", sa.Text(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("cost_so_far", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("series_id", "episode_number", name="uq_episodes_series_number"),
        )
        _create_index_if_missing("idx_episodes_series_id", "episodes", ["series_id"])

    tables = _tables()
    if "pipeline_runs" not in tables:
        op.create_table(
            "pipeline_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
            sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("model_ids", sa.JSON(), nullable=True),
            sa.Column("layers_json", sa.JSON(), nullable=True),
            sa.Column("current_layer", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("error_log", sa.Text(), nullable=True),
            sa.Column("actual_cost_so_far", sa.Float(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        _create_index_if_missing("idx_pipeline_runs_series_id", "pipeline_runs", ["series_id"])

    if "generated_videos" not in tables:
        op.create_table(
            "generated_videos",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("task_id", sa.String(length=36), sa.ForeignKey("tasks.id"), nullable=True),
            sa.Column("keyword", sa.String(length=200), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=True),
            sa.Column("video_path", sa.String(length=500), nullable=True),
            sa.Column("duration", sa.Float(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("pixelle_task_id", sa.String(length=100), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if "audit_reports" not in tables:
        op.create_table(
            "audit_reports",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("target_type", sa.String(length=20), nullable=False),
            sa.Column("target_id", sa.String(length=36), nullable=False),
            sa.Column("image_url", sa.Text(), nullable=False),
            sa.Column("auditor_model", sa.String(length=50), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("pass_fail", sa.Boolean(), nullable=False),
            sa.Column("issues_json", sa.JSON(), nullable=True),
            sa.Column("raw_response", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if "reference_data" not in tables:
        op.create_table(
            "reference_data",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("value", sa.String(length=100), nullable=False),
            sa.Column("label", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=200), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("category", "value", name="uq_reference_data_category_value"),
        )
        _create_index_if_missing("ix_reference_data_category", "reference_data", ["category"])

    if "reference_categories" not in tables:
        op.create_table(
            "reference_categories",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("key", sa.String(length=50), nullable=False),
            sa.Column("label", sa.String(length=100), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("key", name="uq_reference_categories_key"),
        )
        _create_index_if_missing("ix_reference_categories_key", "reference_categories", ["key"], unique=True)

    if "ai_models" not in tables:
        op.create_table(
            "ai_models",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("model_type", sa.String(length=20), nullable=False),
            sa.Column("provider", sa.String(length=30), nullable=False),
            sa.Column("base_url", sa.String(length=300), nullable=True),
            sa.Column("api_key", sa.String(length=500), nullable=True),
            sa.Column("api_secret", sa.String(length=500), nullable=True),
            sa.Column("model_name", sa.String(length=100), nullable=True),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("model_type", "provider", "model_name", name="uq_ai_models_type_provider_name"),
        )
        _create_index_if_missing("ix_ai_models_model_type", "ai_models", ["model_type"])


def downgrade() -> None:
    # Data-preserving catch-up migration: existing deployments may already have
    # these core tables from Base.metadata.create_all(), so downgrade must not
    # drop user content that this migration merely registered with Alembic.
    pass
