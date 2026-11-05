from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db_models import ImageProductionMetric


SERVER_DIR = Path(__file__).resolve().parents[1]


def _alembic_config():
    config = Config(str(SERVER_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    return config


def test_image_production_revision_depends_on_image_creation_workbench():
    config = _alembic_config()
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision("1a2b3c4d5e6f")
    phase3_revision = script.get_revision("2b3c4d5e6f70")
    phase4_revision = script.get_revision("3c4d5e6f7081")

    assert len(script.get_heads()) == 1
    assert revision is not None
    assert revision.down_revision == "f6a7b8c9d0e1"
    assert phase3_revision is not None
    assert phase3_revision.down_revision == "1a2b3c4d5e6f"
    assert phase4_revision is not None
    assert phase4_revision.down_revision == "2b3c4d5e6f70"


def test_image_production_phase4_revision_depends_on_phase3():
    config = _alembic_config()
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision("3c4d5e6f7081")

    assert revision.down_revision == "2b3c4d5e6f70"
    assert len(script.get_heads()) == 1


def test_image_production_tables_exist(test_db):
    inspector = inspect(test_db)

    assert "image_production_strategies" in inspector.get_table_names()
    assert "image_production_strategy_versions" in inspector.get_table_names()
    assert "image_production_policy_versions" in inspector.get_table_names()
    assert "image_selection_previews" in inspector.get_table_names()


def test_image_production_phase4_tables_exist(test_db):
    inspector = inspect(test_db)

    assert "image_production_ab_groups" in inspector.get_table_names()
    assert "image_production_ab_attempts" in inspector.get_table_names()
    assert "image_production_metrics" in inspector.get_table_names()

    group_columns = {column["name"] for column in inspector.get_columns("image_production_ab_groups")}
    assert {
        "id",
        "user_id",
        "idempotency_key",
        "source_request_hash",
        "prompt_snapshot_json",
        "cost_confirmation_json",
        "winner_attempt_id",
        "decision_json",
        "status",
    }.issubset(group_columns)

    attempt_columns = {column["name"] for column in inspector.get_columns("image_production_ab_attempts")}
    assert {
        "id",
        "group_id",
        "task_id",
        "strategy_id",
        "strategy_version",
        "model_id",
        "status",
        "metrics_snapshot_json",
        "human_decision_json",
    }.issubset(attempt_columns)

    metric_columns = {column["name"] for column in inspector.get_columns("image_production_metrics")}
    assert {
        "id",
        "strategy_id",
        "strategy_version",
        "model_id",
        "attempt_count",
        "success_count",
        "failure_count",
        "average_latency_seconds",
        "average_cost_amount",
        "currency",
    }.issubset(metric_columns)

    with test_db.connect() as connection:
        metric_unique_index_sql = connection.execute(
            text(
                "select sql from sqlite_master "
                "where type = 'index' and name = 'uq_image_metric_strategy_version_model'"
            )
        ).scalar()
    assert metric_unique_index_sql is not None
    assert "coalesce" in metric_unique_index_sql.lower()


def test_image_production_metric_strategy_level_rows_are_unique(db):
    db.add(ImageProductionMetric(strategy_id="strategy-1", strategy_version=1, model_id=None))
    db.commit()

    db.add(ImageProductionMetric(strategy_id="strategy-1", strategy_version=1, model_id=None))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_image_creation_task_strategy_columns_exist(test_db):
    columns = {column["name"] for column in inspect(test_db).get_columns("image_creation_tasks")}

    assert {
        "strategy_id",
        "strategy_version",
        "strategy_snapshot_json",
        "selection_explanation_json",
        "selection_preview_id",
        "selection_preview_request_hash",
        "fallback_trace_json",
        "queue_job_id",
        "capacity_lease_id",
        "ab_test_group_id",
    }.issubset(columns)


def test_image_production_alembic_upgrade_and_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{db_path}"
    import app.database as database_module

    monkeypatch.setattr(database_module, "DATABASE_URL", database_url)
    config = _alembic_config()

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "image_production_strategies" in inspector.get_table_names()
    assert "image_production_cost_events" in inspector.get_table_names()
    assert "image_production_ab_groups" in inspector.get_table_names()
    assert "image_production_ab_attempts" in inspector.get_table_names()
    assert "image_production_metrics" in inspector.get_table_names()
    with engine.connect() as connection:
        metric_unique_index_sql = connection.execute(
            text(
                "select sql from sqlite_master "
                "where type = 'index' and name = 'uq_image_metric_strategy_version_model'"
            )
        ).scalar()
    assert metric_unique_index_sql is not None
    assert "coalesce" in metric_unique_index_sql.lower()
    assert "strategy_id" in {column["name"] for column in inspector.get_columns("image_creation_tasks")}
    assert "idx_image_tasks_strategy" in {index["name"] for index in inspector.get_indexes("image_creation_tasks")}

    cost_columns = {
        column["name"]: column
        for column in inspector.get_columns("image_production_cost_events")
    }
    assert cost_columns["event_key"]["type"].length == 220

    cost_foreign_keys = inspector.get_foreign_keys("image_production_cost_events")
    assert any(
        fk["constrained_columns"] == ["task_id"]
        and fk["referred_table"] == "image_creation_tasks"
        for fk in cost_foreign_keys
    )
    assert any(
        fk["constrained_columns"] == ["asset_id"]
        and fk["referred_table"] == "image_creation_assets"
        for fk in cost_foreign_keys
    )

    cost_unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("image_production_cost_events")
    }
    assert "uq_image_cost_event_key" in cost_unique_constraints

    cost_indexes = {
        index["name"]
        for index in inspector.get_indexes("image_production_cost_events")
    }
    assert {
        "idx_image_cost_events_event_type",
        "idx_image_cost_events_strategy",
        "idx_image_cost_events_created",
    }.issubset(cost_indexes)
    engine.dispose()

    command.downgrade(config, "2b3c4d5e6f70")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "image_production_ab_groups" not in inspector.get_table_names()
    assert "image_production_ab_attempts" not in inspector.get_table_names()
    assert "image_production_metrics" not in inspector.get_table_names()
    assert "image_production_cost_events" in inspector.get_table_names()
    engine.dispose()

    command.downgrade(config, "1a2b3c4d5e6f")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "image_production_cost_events" not in inspector.get_table_names()
    assert "image_production_strategies" in inspector.get_table_names()
    assert "strategy_id" in {column["name"] for column in inspector.get_columns("image_creation_tasks")}
    engine.dispose()

    command.downgrade(config, "f6a7b8c9d0e1")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "image_production_strategies" not in inspector.get_table_names()
    assert "strategy_id" not in {column["name"] for column in inspector.get_columns("image_creation_tasks")}
    engine.dispose()
