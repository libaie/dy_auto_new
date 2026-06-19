import io

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


SCRIPT_ASSET_ENDPOINTS = {
    "/api/device/selectors": "app.domains.device_operations.script_assets.get_selectors",
    "/api/device/prompt-templates": "app.domains.device_operations.script_assets.get_prompt_templates",
    "/api/device/script-version": "app.domains.device_operations.script_assets.script_version",
    "/api/device/script-download": "app.domains.device_operations.script_assets.script_download",
    "/api/device/script-upload": "app.domains.device_operations.script_assets.script_upload",
    "/api/device/templates": "app.domains.device_operations.script_assets.device_list_templates",
    "/api/device/templates/{filename}": "app.domains.device_operations.script_assets.device_download_template",
    "/api/device/calibrate": "app.domains.device_operations.script_assets.device_calibrate",
}


@pytest.fixture(autouse=True)
def isolate_script_service(tmp_path, monkeypatch):
    from app.services.script_service import script_service

    script_dir = tmp_path / "scripts"
    monkeypatch.setattr(script_service, "_script_dir", script_dir)
    monkeypatch.setattr(script_service, "_version_file", script_dir / "version.txt")


def test_script_asset_routes_are_owned_by_domain_module():
    assert {
        route.path: f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in app.routes
        if isinstance(route, APIRoute) and route.path in SCRIPT_ASSET_ENDPOINTS
    } == SCRIPT_ASSET_ENDPOINTS


def test_selector_and_template_sync_response_shapes():
    with TestClient(app) as client:
        selectors = client.get("/api/device/selectors", headers=HEADERS)
        prompt_templates = client.get("/api/device/prompt-templates", headers=HEADERS)
        templates = client.get("/api/device/templates", headers=HEADERS)

    assert selectors.status_code == 200
    assert set(selectors.json()) == {"version", "selectors", "changed"}
    assert isinstance(selectors.json()["changed"], bool)

    assert prompt_templates.status_code == 200
    assert set(prompt_templates.json()) == {"version", "templates", "changed"}
    assert isinstance(prompt_templates.json()["changed"], bool)

    assert templates.status_code == 200
    assert "templates" in templates.json()


def test_script_package_upload_version_and_download_shapes():
    with TestClient(app) as client:
        version = client.get("/api/device/script-version", headers=HEADERS)
        upload = client.post(
            "/api/device/script-upload",
            files={"file": ("device.zip", io.BytesIO(b"PK\x03\x04zip"), "application/zip")},
            headers=HEADERS,
        )
        download = client.get("/api/device/script-download", headers=HEADERS)

    assert version.status_code == 200
    assert "version" in version.json()

    assert upload.status_code == 200
    assert set(upload.json()) == {"version", "size"}
    assert upload.json()["size"] == 7

    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert download.content
