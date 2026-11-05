"""Regression tests for migration failures and dialect-specific initialization."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, create_mock_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import database
from app.db_models import Base


def migration_config():
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def test_upgrade_has_one_head_containing_both_published_branches():
    script = ScriptDirectory.from_config(migration_config())
    heads = script.get_heads()
    assert len(heads) == 1
    ancestors = {revision.revision for revision in script.walk_revisions()}
    assert {"5e6f708192a3", "f7a8b9c0d1e2"} <= ancestors


@pytest.mark.parametrize("starting_revision", [None, "5e6f708192a3", "f7a8b9c0d1e2"])
def test_upgrade_empty_database_or_either_published_head(tmp_path, monkeypatch, starting_revision):
    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    monkeypatch.setattr(database, "DATABASE_URL", url)
    config = migration_config()
    if starting_revision:
        command.upgrade(config, starting_revision)
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            heads = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        assert len(heads) == 1
        assert heads == ScriptDirectory.from_config(config).get_heads()
        inspector = inspect(engine)
        assert "image_creation_tasks" in inspector.get_table_names()
        assert {
            "idx_production_jobs_plan_stage_status",
            "idx_production_jobs_stage_created_at",
        } <= {index["name"] for index in inspector.get_indexes("production_jobs")}
    finally:
        engine.dispose()


def test_startup_stops_when_migration_fails(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'failed-startup.db'}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "DATABASE_URL", str(engine.url))
    monkeypatch.setattr(database, "_seed_admin_user", lambda: None)
    monkeypatch.setattr(database, "_seed_selector_descriptions", lambda: None)

    def fail_migration(*args, **kwargs):
        raise RuntimeError("migration failed deliberately")

    monkeypatch.setattr(command, "upgrade", fail_migration)
    try:
        with pytest.raises(RuntimeError, match="migration failed deliberately"):
            database.init_db()
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_fresh_startup_creates_versioned_usable_schema(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh-startup.db'}")
    database.configure_engine(engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(database, "DATABASE_URL", str(engine.url))
    monkeypatch.setenv("ADMIN_USERNAME", "startup-regression")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password-not-for-deployment")
    try:
        database.init_db()
        database.init_db()  # Startup must be safe to repeat after migration.
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1
            assert connection.execute(text("SELECT username FROM users")).scalar_one() == "startup-regression"
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    finally:
        engine.dispose()


def test_unversioned_existing_schema_is_preserved_on_migration_failure(tmp_path, monkeypatch):
    """A schema created by the old fallback must not be silently stamped or reset."""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE repair_sentinel (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO repair_sentinel VALUES ('keep existing data')"))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "DATABASE_URL", str(engine.url))
    monkeypatch.setattr(database, "_seed_admin_user", lambda: None)
    monkeypatch.setattr(database, "_seed_selector_descriptions", lambda: None)
    try:
        with pytest.raises(Exception, match="already exists"):
            database.init_db()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT value FROM repair_sentinel")).scalar_one() == "keep existing data"
            assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
    finally:
        engine.dispose()


def test_sqlite_configuration_enforces_foreign_keys():
    engine = create_engine("sqlite:///:memory:")
    try:
        database.configure_engine(engine)
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
    finally:
        engine.dispose()


def test_mysql_configuration_does_not_install_sqlite_connect_hooks():
    # A MySQL mock connection rejects SQLAlchemy engine-only event registration;
    # configuring a non-SQLite dialect must not try to install the PRAGMA hook.
    statements = []
    engine = create_mock_engine("mysql+pymysql://", lambda sql, *args, **kwargs: statements.append(str(sql)))
    database.configure_engine(engine)
    assert statements == []
