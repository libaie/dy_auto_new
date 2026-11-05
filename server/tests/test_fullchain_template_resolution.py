"""Template sync must fall back to the authenticated device's display profile."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db_models import Device
from app.main import app
from app.services.template_service import template_service


@pytest.mark.parametrize("explicit_resolution", [None, "1080x2400"])
def test_device_template_list_uses_explicit_or_registered_resolution(db, monkeypatch, explicit_resolution):
    tag = str(uuid.uuid4())
    device = Device(id=tag, name="Synthetic template device", device_secret=tag,
                    screen_resolution="720x1600", user_id="test-user-id")
    db.add(device)
    db.commit()
    seen = []

    def list_templates(*, resolution):
        seen.append(resolution)
        return [{"filename": "synthetic.png", "md5": "synthetic-hash"}]

    monkeypatch.setattr(template_service, "list_templates", list_templates)
    try:
        response = TestClient(app).get(
            "/api/device/templates", headers={"X-Device-Secret": tag},
            params={"resolution": explicit_resolution} if explicit_resolution else {},
        )
        assert response.status_code == 200, response.text
        assert seen == [explicit_resolution or "720x1600"]
        assert response.json()["templates"][0]["filename"] == "synthetic.png"
    finally:
        db.query(Device).filter(Device.id == tag).delete(synchronize_session=False)
        db.commit()
