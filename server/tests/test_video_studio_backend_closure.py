import importlib

import httpx
from fastapi.testclient import TestClient

from app.db_models import SystemSetting
from app.deps import create_access_token
from app.main import app

client = TestClient(app)


def _auth_headers(role: str) -> dict:
    token = create_access_token(f"{role}-user-id", f"{role}-user", role)
    return {"Authorization": f"Bearer {token}"}


def _install_fake_seedance_client(monkeypatch, captured: dict):
    try:
        seedance = importlib.import_module("app.routers.seedance")
    except ModuleNotFoundError:
        return

    class FakeSeedanceClient:
        async def post(self, path, json=None):
            captured["post_path"] = path
            captured["post_json"] = json
            return httpx.Response(200, json={"id": "seedance-task-1"})

        async def get(self, path):
            captured["get_path"] = path
            return httpx.Response(
                200,
                json={
                    "status": "succeeded",
                    "output": {"videos": [{"url": "https://cdn.test/final.mp4"}]},
                },
            )

    monkeypatch.setattr(seedance, "_get_client", lambda api_key: FakeSeedanceClient())


def test_seedance_generate_route_is_registered_and_uses_configured_key(db, monkeypatch):
    captured = {}
    db.add(SystemSetting(key="seedance_api_key", value="seedance-key"))
    db.commit()
    _install_fake_seedance_client(monkeypatch, captured)

    response = client.post(
        "/api/seedance/generate",
        json={
            "prompt": "雨夜街角的电影感开场",
            "aspect_ratio": "9:16",
            "duration": 5,
            "resolution": "720p",
            "image_urls": ["https://cdn.test/ref.png"],
        },
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == "seedance-task-1"
    assert captured["post_path"] == "/contents/generations/tasks"
    assert {"type": "image_url", "image_url": {"url": "https://cdn.test/ref.png"}} in captured["post_json"]["content"]


def test_pixelle_proxy_forwards_api_key_from_system_settings(db, monkeypatch):
    captured = {}
    db.add(SystemSetting(key="pixelle_api_key", value="db-pixelle-key"))
    db.commit()

    class FakePixelleClient:
        async def request(self, method, url, headers=None, content=None):
            captured["headers"] = headers or {}
            return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

    monkeypatch.setattr("app.routers.pixelle._get_proxy_client", lambda db=None: FakePixelleClient())

    response = client.get("/api/pixelle-proxy/openapi.json")

    assert response.status_code == 200
    assert captured["headers"]["X-API-Key"] == "db-pixelle-key"


def test_pixelle_proxy_rejects_non_admin_role(real_auth, monkeypatch):
    class FakePixelleClient:
        async def request(self, *args, **kwargs):
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("app.routers.pixelle._get_proxy_client", lambda db=None: FakePixelleClient())

    response = client.get(
        "/api/pixelle-proxy/openapi.json",
        headers=_auth_headers("operator"),
    )

    assert response.status_code == 403
