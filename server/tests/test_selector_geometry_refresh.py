"""A display rotation must not retain the registration-time selector profile."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_models import Device, UISelector
from app.services.selector_service import selector_service

client = TestClient(app)


def test_live_resolution_overrides_registration_without_mutating_device(db):
    device = Device(id="geometry-device", name="Geometry", device_secret="geometry-secret", screen_resolution="1080x2400")
    db.add(device)
    for profile in ("1080x2400", "2400x1080", "default"):
        db.add(UISelector(action_name="geometry_button", resolution_profile=profile, strategies=[{"type": "text", "value": profile}]))
    db.commit()

    response = client.get("/api/device/selectors", params={"resolution": "2400x1080", "version": selector_service.get_version(db)}, headers={"X-Device-Secret": "geometry-secret"})
    assert response.status_code == 200
    assert response.json()["changed"] is True
    profiles = {s["resolution_profile"] for s in response.json()["selectors"] if s["action_name"] == "geometry_button"}
    assert profiles == {"2400x1080", "default"}
    db.refresh(device)
    assert device.screen_resolution == "1080x2400"


@pytest.mark.parametrize("resolution", ["0x2400", "-10x20", "2400", "../default", "default", "1080x0"])
def test_live_resolution_is_a_positive_pixel_size(resolution):
    response = client.get("/api/device/selectors", params={"resolution": resolution}, headers={"X-Device-Secret": "change-me-to-a-random-string"})
    assert response.status_code == 422
