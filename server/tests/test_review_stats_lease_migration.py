"""Upgrade a handcrafted pre-lease table; never derive the old schema from ORM."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app import database
from app.db_models import StatsEvent
from app.models import StatsIncrementRequest


def config():
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / 'alembic.ini'))
    cfg.set_main_option('script_location', str(root / 'alembic'))
    return cfg


def test_stats_lease_fields_keep_legacy_requests_compatible():
    legacy = StatsIncrementRequest(task_id='t', account_id='a', task_type='search_comment')
    leased = StatsIncrementRequest(task_id='t', account_id='a', task_type='search_comment', lease_id='lease-one')
    assert getattr(legacy, 'lease_id', 'missing') is None
    assert getattr(leased, 'lease_id', None) == 'lease-one'
    assert 'lease_id' in StatsEvent.__table__.columns


def test_upgrade_legacy_stats_events_preserves_data_and_scopes_idempotency(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'legacy-stats.db'}"
    monkeypatch.setattr(database, 'DATABASE_URL', url)
    engine = create_engine(url)
    database.configure_engine(engine)
    try:
        with engine.begin() as connection:
            for parent in ('tasks', 'devices', 'accounts'):
                connection.execute(text(f'CREATE TABLE {parent} (id VARCHAR(36) PRIMARY KEY)'))
            for parent, identity in [('tasks', 't'), ('devices', 'd'), ('accounts', 'a')]:
                connection.execute(text(f'INSERT INTO {parent} VALUES (:id)'), {'id': identity})
            connection.execute(text('''CREATE TABLE stats_events (
                id VARCHAR(36) PRIMARY KEY NOT NULL,
                task_id VARCHAR(36) NOT NULL REFERENCES tasks(id),
                device_id VARCHAR(36) NOT NULL REFERENCES devices(id),
                account_id VARCHAR(36) NOT NULL REFERENCES accounts(id),
                event_type VARCHAR(30) NOT NULL,
                target_id VARCHAR(200) NOT NULL,
                op_index INTEGER NOT NULL,
                count INTEGER NOT NULL,
                created_at DATETIME NOT NULL,
                CONSTRAINT uq_stats_event_idempotent UNIQUE
                    (task_id, device_id, event_type, target_id, op_index)
            )'''))
            connection.execute(text('CREATE INDEX ix_stats_events_task_id ON stats_events (task_id)'))
            connection.execute(text("INSERT INTO stats_events VALUES ('old', 't', 'd', 'a', 'search_comment', 'target', 0, 2, '2026-11-05 08:00:00')"))
        cfg = config()
        command.stamp(cfg, '6f708192a3b4')
        command.upgrade(cfg, 'head')
        inspector = inspect(engine)
        columns = {c['name']: c for c in inspector.get_columns('stats_events')}
        assert 'lease_id' in columns
        assert columns['lease_id']['nullable'] is False
        assert len(inspector.get_foreign_keys('stats_events')) == 3
        assert 'ix_stats_events_task_id' in {i['name'] for i in inspector.get_indexes('stats_events')}
        unique = next(c for c in inspector.get_unique_constraints('stats_events') if c['name'] == 'uq_stats_event_idempotent')
        assert 'lease_id' in unique['column_names']
        with engine.begin() as connection:
            row = connection.execute(text('SELECT id, lease_id, count, target_id FROM stats_events')).one()
            assert tuple(row) == ('old', '', 2, 'target')
            for event_id, lease in [('new-1', 'lease-one'), ('new-2', 'lease-two')]:
                connection.execute(text("""INSERT INTO stats_events
                    (id,task_id,device_id,account_id,event_type,target_id,op_index,count,created_at,lease_id)
                    VALUES (:id,'t','d','a','search_comment','target',0,1,'2026-11-05 08:00:00',:lease)"""),
                    {'id': event_id, 'lease': lease})
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text("""INSERT INTO stats_events
                    (id,task_id,device_id,account_id,event_type,target_id,op_index,count,created_at,lease_id)
                    VALUES ('duplicate','t','d','a','search_comment','target',0,1,'2026-11-05 08:00:00','lease-one')"""))
        with engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM stats_events')).scalar_one() == 3
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '7a8192a3b4c5'
            assert connection.execute(text('PRAGMA foreign_keys')).scalar_one() == 1
        # A downgrade must refuse cross-lease collisions before changing data.
        with pytest.raises(RuntimeError, match='distinct leases'):
            command.downgrade(cfg, '6f708192a3b4')
        assert 'lease_id' in {c['name'] for c in inspect(engine).get_columns('stats_events')}
        with engine.begin() as connection:
            assert connection.execute(text('SELECT count(*) FROM stats_events')).scalar_one() == 3
            connection.execute(text("DELETE FROM stats_events WHERE id != 'old'"))
        command.downgrade(cfg, '6f708192a3b4')
        assert 'lease_id' not in {c['name'] for c in inspect(engine).get_columns('stats_events')}
        with engine.connect() as connection:
            assert connection.execute(text('SELECT id,count FROM stats_events')).one() == ('old', 2)
    finally:
        engine.dispose()


def test_stats_lease_upgrade_skips_absent_legacy_table(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'absent-stats.db'}"
    monkeypatch.setattr(database, 'DATABASE_URL', url)
    cfg = config()
    command.stamp(cfg, '6f708192a3b4')
    command.upgrade(cfg, 'head')
    engine = create_engine(url)
    try:
        assert 'stats_events' not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '7a8192a3b4c5'
    finally:
        engine.dispose()
