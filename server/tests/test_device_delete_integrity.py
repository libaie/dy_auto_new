"""Device deletion must respect history under real, enabled FK constraints."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.db_models import Account, AccountGroup, Base, ChainInstance, ChainTemplate, Channel, ChannelItem, Device, StatsEvent, Task
from app.main import app
from app.routers import devices


@pytest.mark.parametrize("reference", ["stats", "chain", "channel"])
def test_device_with_retained_history_is_rejected_before_disconnect(reference, monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Account(id="fk-account", nickname="synthetic"))
        db.commit()
        db.add(Device(id="fk-device", name="synthetic", device_secret="synthetic-kept", status="online"))
        db.commit()
        db.add(Task(id="fk-task", type="search_like", account_id="fk-account", device_id="fk-device", status="completed", params={}))
        db.commit()
        if reference == "stats":
            history = StatsEvent(task_id="fk-task", device_id="fk-device", account_id="fk-account",
                                 event_type="likes", target_id="synthetic", op_index=0, lease_id="synthetic")
        elif reference == "chain":
            db.add(ChainTemplate(id="fk-template", name="synthetic", steps=[]))
            db.commit()
            history = ChainInstance(template_id="fk-template", account_id="fk-account", device_id="fk-device", total_steps=1)
        else:
            db.add(AccountGroup(id="fk-group", name="synthetic"))
            db.commit()
            db.add(Channel(id="fk-channel", group_id="fk-group", task_type="collect", params_template={}))
            db.commit()
            history = ChannelItem(channel_id="fk-channel", keyword="synthetic", account_id="fk-account", assigned_device_id="fk-device")
        db.add(history)
        db.commit()
        history_type, history_id = type(history), history.id
        monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)
        removed_notice = AsyncMock()
        disconnect = AsyncMock()
        monkeypatch.setattr(devices.pair_ws_manager, "send_to_device", removed_notice)
        monkeypatch.setattr(devices.pair_ws_manager, "disconnect_device", disconnect)
        response = TestClient(app).delete("/api/devices/fk-device")
        assert response.status_code == 409, response.text
        assert "历史" in response.json()["detail"]
        db.rollback()
        assert db.get(Device, "fk-device").device_secret == "synthetic-kept"
        assert db.get(history_type, history_id) is not None
        assert db.get(Task, "fk-task").device_id == "fk-device"
        removed_notice.assert_not_awaited()
        disconnect.assert_not_awaited()
    finally:
        db.close()
        engine.dispose()
