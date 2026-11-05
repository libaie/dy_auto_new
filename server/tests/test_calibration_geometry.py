"""Calibration binds a visual asset to the observed selector and app version."""
import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_models import UISelector
from app.services.selector_service import selector_service

client = TestClient(app)
HEADERS = {"X-Device-Secret": "change-me-to-a-random-string"}


@pytest.fixture
def templates(tmp_path, monkeypatch):
    from app.services import template_service
    monkeypatch.setattr(template_service, "TEMPLATE_DIR", tmp_path)
    template_service.template_service._md5_cache.clear()
    return tmp_path


def source(db, *, action=None, platform="38.6.0", resolution="default", strategies=None):
    item = UISelector(action_name=action or f"calibration_{uuid.uuid4().hex[:12]}", platform_version=platform,
                      resolution_profile=resolution, version=3,
                      strategies=strategies or [{"type": "text", "value": "搜索", "priority": 1}])
    db.add(item)
    db.commit()
    return item


def payload(item, **overrides):
    result = {"action_name": item.action_name, "filename": "observed.png",
              "data": base64.b64encode(b"\x89PNG\r\n\x1a\nobserved-icon").decode(),
              "source_selector_id": item.id, "source_selector_version": item.version,
              "platform_version": "38.7.0", "source_resolution": "540x1200", "source_density": 1.5}
    result.update(overrides)
    return result


def test_calibration_uses_exact_source_and_adds_an_image_fallback(db, templates):
    old = source(db, platform="38.5.0", strategies=[{"type": "text", "value": "old"}])
    selected = source(db, action=old.action_name)
    response = client.post("/api/device/calibrate", json={"resolution": "1080x2400", "templates": [payload(selected)]}, headers=HEADERS)
    assert response.status_code == 200
    target = db.query(UISelector).filter_by(action_name=selected.action_name, platform_version="38.7.0", resolution_profile="1080x2400").one()
    assert target.strategies[0]["value"] == "搜索"
    image = next(s for s in target.strategies if s.get("type") == "image")
    assert image["source_resolution"] == "540x1200"
    assert image["source_density"] == 1.5
    assert (templates / "1080x2400" / image["template"]).is_file()
    assert image["template"] != "observed.png"  # immutable content name


def test_recalibration_updates_only_the_requested_app_version(db, templates):
    selected = source(db)
    other = source(db, action=selected.action_name, platform="38.5.0", resolution="1080x2400", strategies=[{"type": "image", "template": "old.png"}])
    target = source(db, action=selected.action_name, platform="38.7.0", resolution="1080x2400", strategies=[{"type": "image", "template": "current.png"}])
    response = client.post("/api/device/calibrate", json={"resolution": "1080x2400", "templates": [payload(selected)]}, headers=HEADERS)
    assert response.status_code == 200
    db.refresh(target)
    db.refresh(other)
    assert target.strategies[0]["template"] != "current.png"
    assert target.version == 4
    assert other.strategies[0]["template"] == "old.png"


def test_stale_calibration_is_rejected_before_assets_or_selectors_are_written(db, templates):
    selected = source(db)
    revision = selector_service.get_version(db)
    response = client.post("/api/device/calibrate", json={"resolution": "1080x2400", "templates": [payload(selected, source_selector_version=1)]}, headers=HEADERS)
    assert response.status_code == 409
    assert list(templates.rglob("*.png")) == []
    assert selector_service.get_version(db) == revision


def test_ambiguous_legacy_calibration_does_not_choose_an_arbitrary_version(db, templates):
    selected = source(db)
    source(db, action=selected.action_name, platform="38.5.0")
    item = payload(selected)
    for key in ("source_selector_id", "source_selector_version", "platform_version"):
        item.pop(key)
    response = client.post("/api/device/calibrate", json={"resolution": "1080x2400", "templates": [item]}, headers=HEADERS)
    assert response.status_code == 409
    assert list(templates.rglob("*.png")) == []


def test_invalid_item_does_not_partially_publish_a_batch(db, templates):
    selected = source(db)
    invalid = source(db)
    response = client.post("/api/device/calibrate", json={"resolution": "1080x2400", "templates": [payload(selected), payload(invalid, data="not base64!")]}, headers=HEADERS)
    assert response.status_code == 400
    assert list(templates.rglob("*.png")) == []
    assert db.query(UISelector).filter_by(action_name=selected.action_name, resolution_profile="1080x2400").count() == 0


def test_legacy_unambiguous_calibration_remains_supported(db, templates):
    selected = source(db, platform="default")
    item = {"action_name": selected.action_name, "filename": "legacy.png", "data": payload(selected)["data"]}
    response = client.post("/api/device/calibrate", json={"resolution": "720x1600", "templates": [item]}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["uploaded"] == 1
    target = db.query(UISelector).filter_by(action_name=selected.action_name, resolution_profile="720x1600").one()
    assert any(s.get("type") == "image" for s in target.strategies)
