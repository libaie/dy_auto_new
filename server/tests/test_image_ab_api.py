from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import image_production as router_module
from app.services.image_creation_errors import image_error


client = TestClient(app)


def _ab_payload(**overrides):
    payload = {
        "mode": "text_to_image",
        "prompt": "api ab",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": ["strategy-a", "strategy-b"],
        "count": 1,
    }
    payload.update(overrides)
    return payload


def test_ab_preview_rejects_single_strategy(monkeypatch):
    def fake_preview(db, payload, user_id=None):
        assert payload["strategy_ids"] == ["strategy-a"]
        assert user_id == "test-user-id"
        raise image_error(
            422,
            "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID",
            "A/B comparison requires two to four unique strategies.",
            "Select two to four image production strategies.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "preview_ab_group", fake_preview, raising=False)

    resp = client.post(
        "/api/image-production/ab-tests/preview",
        json=_ab_payload(strategy_ids=["strategy-a"]),
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID"


def test_ab_preview_route_returns_preview(monkeypatch):
    def fake_preview(db, payload, user_id=None):
        assert payload["strategy_ids"] == ["strategy-a", "strategy-b"]
        assert payload["model_id"] == "selected-model"
        assert user_id == "test-user-id"
        return {
            "ok": True,
            "request_hash": "hash-api",
            "strategy_count": 2,
            "total_cost_estimate": {
                "amount": 3.0,
                "currency": "CNY",
                "cost_limit_exceeded": False,
            },
            "previews": [],
        }

    monkeypatch.setattr(router_module, "preview_ab_group", fake_preview, raising=False)

    resp = client.post(
        "/api/image-production/ab-tests/preview",
        json=_ab_payload(model_id="selected-model"),
    )

    assert resp.status_code == 200
    assert resp.json()["request_hash"] == "hash-api"
    assert resp.json()["total_cost_estimate"]["amount"] == 3.0


def test_ab_create_route_returns_serialized_group_and_passes_user_scope(monkeypatch):
    async def fake_create(db, payload, user_id=None):
        assert payload["preview_request_hash"] == "hash-api"
        assert payload["cost_confirmation"] is True
        assert payload["idempotency_key"] == "ab-api-key"
        assert payload["model_id"] == "selected-model"
        assert user_id == "test-user-id"
        return SimpleNamespace(id="ab-group-1", status="running")

    def fake_serialize(db, group):
        return {
            "id": group.id,
            "status": group.status,
            "attempts": [{"id": "attempt-1", "status": "creating"}],
        }

    monkeypatch.setattr(router_module, "create_ab_group", fake_create, raising=False)
    monkeypatch.setattr(router_module, "serialize_ab_group", fake_serialize, raising=False)

    resp = client.post(
        "/api/image-production/ab-tests",
        json=_ab_payload(
            preview_request_hash="hash-api",
            cost_confirmation=True,
            idempotency_key="ab-api-key",
            model_id="selected-model",
        ),
    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["ab_group"]["id"] == "ab-group-1"
    assert resp.json()["ab_group"]["attempts"][0]["id"] == "attempt-1"


def test_ab_create_route_propagates_cost_limit_error(monkeypatch):
    async def fake_create(db, payload, user_id=None):
        assert user_id == "test-user-id"
        raise image_error(
            409,
            "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED",
            "A/B comparison exceeds the configured group cost limit.",
            "Reduce count, choose cheaper strategies, or adjust policy.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "create_ab_group", fake_create, raising=False)

    resp = client.post(
        "/api/image-production/ab-tests",
        json=_ab_payload(
            count=2,
            preview_request_hash="hash-api",
            cost_confirmation=True,
        ),
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED"


def test_ab_winner_route_propagates_unapproved_attempt_error_and_passes_user_scope(monkeypatch):
    def fake_winner(db, group_id, attempt_id, decision, user_id=None):
        assert group_id == "ab-group-1"
        assert attempt_id == "attempt-1"
        assert decision == {"reason": "best", "notes": ""}
        assert user_id == "test-user-id"
        raise image_error(
            409,
            "IMAGE_AB_TEST_ATTEMPT_NOT_READY",
            "Winner attempt must have at least one approved image asset.",
            "Approve an image asset before choosing the winner.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "adopt_ab_winner", fake_winner, raising=False)

    resp = client.post(
        "/api/image-production/ab-tests/ab-group-1/winner/attempt-1",
        json={"reason": "best"},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_ATTEMPT_NOT_READY"


def test_ab_group_read_missing_group_propagates_not_found_and_passes_user_scope(monkeypatch):
    def fake_get(db, group_id, user_id=None):
        assert group_id == "missing"
        assert user_id == "test-user-id"
        raise image_error(
            404,
            "IMAGE_AB_TEST_GROUP_NOT_FOUND",
            "A/B group was not found.",
            "Reload A/B comparisons.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "get_ab_group", fake_get, raising=False)

    resp = client.get("/api/image-production/ab-tests/missing")

    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_GROUP_NOT_FOUND"


def test_ab_refresh_route_returns_serialized_group_and_passes_user_scope(monkeypatch):
    def fake_refresh(db, group_id, user_id=None):
        assert group_id == "ab-group-1"
        assert user_id == "test-user-id"
        return SimpleNamespace(id=group_id, status="completed")

    def fake_serialize(db, group):
        return {"id": group.id, "status": group.status, "attempts": []}

    monkeypatch.setattr(router_module, "refresh_ab_group", fake_refresh, raising=False)
    monkeypatch.setattr(router_module, "serialize_ab_group", fake_serialize, raising=False)

    resp = client.post("/api/image-production/ab-tests/ab-group-1/refresh")

    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "ab_group": {"id": "ab-group-1", "status": "completed", "attempts": []},
    }


def test_ab_winner_recommendation_route_returns_recommendation_and_passes_user_scope(monkeypatch):
    def fake_recommend(db, group_id, user_id=None):
        assert group_id == "ab-group-1"
        assert user_id == "test-user-id"
        return {
            "group_id": group_id,
            "eligible": True,
            "code": "WINNER_RECOMMENDED",
            "recommended_attempt_id": "attempt-1",
            "automatic_adoption_allowed": False,
            "attempt_scores": [],
        }

    monkeypatch.setattr(router_module, "recommend_ab_winner", fake_recommend, raising=False)

    resp = client.get("/api/image-production/ab-tests/ab-group-1/winner-recommendation")

    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "recommendation": {
            "group_id": "ab-group-1",
            "eligible": True,
            "code": "WINNER_RECOMMENDED",
            "recommended_attempt_id": "attempt-1",
            "automatic_adoption_allowed": False,
            "attempt_scores": [],
        },
    }


def test_ab_no_winner_route_returns_serialized_group_and_passes_user_scope(monkeypatch):
    def fake_no_winner(db, group_id, decision, user_id=None):
        assert group_id == "ab-group-1"
        assert decision == {"reason": "none acceptable", "notes": "rerun needed"}
        assert user_id == "test-user-id"
        return SimpleNamespace(id=group_id, status="no_winner")

    def fake_serialize(db, group):
        return {"id": group.id, "status": group.status, "attempts": []}

    monkeypatch.setattr(router_module, "mark_ab_no_winner", fake_no_winner, raising=False)
    monkeypatch.setattr(router_module, "serialize_ab_group", fake_serialize, raising=False)

    resp = client.post(
        "/api/image-production/ab-tests/ab-group-1/no-winner",
        json={"reason": "none acceptable", "notes": "rerun needed"},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "ab_group": {"id": "ab-group-1", "status": "no_winner", "attempts": []},
    }
