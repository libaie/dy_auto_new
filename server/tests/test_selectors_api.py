"""Selector management CRUD API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_list_selectors(client):
    response = client.get("/api/selectors")
    assert response.status_code == 200
    data = response.json()
    assert "selectors" in data
    assert "version" in data
    assert "total" in data


def test_get_selector_by_action(client):
    response = client.get("/api/selectors/like_button")
    assert response.status_code == 200
    data = response.json()
    assert data["action_name"] == "like_button"
    assert "strategies" in data


def test_get_selector_not_found(client):
    response = client.get("/api/selectors/nonexistent_action")
    assert response.status_code == 404


def test_create_selector(client):
    response = client.post("/api/selectors", json={
        "action_name": "test_action",
        "strategies": [
            {"type": "text", "value": "测试", "priority": 1},
        ],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["action_name"] == "test_action"


def test_update_selector(client):
    # Create first
    client.post("/api/selectors", json={
        "action_name": "update_test",
        "strategies": [{"type": "text", "value": "old", "priority": 1}],
    })

    # Update
    response = client.put("/api/selectors/update_test", json={
        "strategies": [{"type": "text", "value": "new", "priority": 1}],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["strategies"][0]["value"] == "new"


def test_delete_selector(client):
    # Create first
    client.post("/api/selectors", json={
        "action_name": "delete_test",
        "strategies": [{"type": "text", "value": "bye", "priority": 1}],
    })

    # Delete
    response = client.delete("/api/selectors/delete_test")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    # Confirm gone
    response = client.get("/api/selectors/delete_test")
    assert response.status_code == 404


def test_toggle_selector_enabled(client):
    # Create
    client.post("/api/selectors", json={
        "action_name": "toggle_test",
        "strategies": [{"type": "text", "value": "toggle", "priority": 1}],
    })

    # Disable
    response = client.patch("/api/selectors/toggle_test/toggle", json={
        "enabled": False,
    })
    assert response.status_code == 200
    assert response.json()["enabled"] is False
