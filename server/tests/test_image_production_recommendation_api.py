from fastapi.testclient import TestClient

from app.config import bj_now
from app.db.models import ImageCreationTask, ImageProductionMetric
from app.main import app
from app.domains.image_generation import image_production_router as router_module
client = TestClient(app)


def _task(db, *, task_id, strategy_id="strategy-1", strategy_version=1, model_id="model-1"):
    task = ImageCreationTask(
        id=task_id,
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        prompt=f"prompt {task_id}",
        count=1,
        target_count=1,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        model_id=model_id,
        created_at=bj_now(),
        completed_at=bj_now(),
    )
    db.add(task)
    return task


def test_refresh_strategy_metrics_route_returns_refreshed_payload(monkeypatch):
    calls = []

    def fake_refresh_all_image_strategy_metrics(db, strategy_id=None, strategy_version=None):
        calls.append((strategy_id, strategy_version))
        return {
            "refreshed_count": 1,
            "keys": [
                {
                    "strategy_id": strategy_id,
                    "strategy_version": strategy_version,
                    "model_id": "model-1",
                }
            ],
        }

    monkeypatch.setattr(
        router_module,
        "refresh_all_image_strategy_metrics",
        fake_refresh_all_image_strategy_metrics,
    )

    resp = client.post(
        "/api/image-production/strategies/metrics/refresh",
        json={"strategy_id": "strategy-1", "strategy_version": 2},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "refreshed": {
            "refreshed_count": 1,
            "keys": [
                {
                    "strategy_id": "strategy-1",
                    "strategy_version": 2,
                    "model_id": "model-1",
                }
            ],
        },
    }
    assert calls == [("strategy-1", 2)]


def test_refresh_strategy_metrics_route_persists_metrics(db):
    _task(db, task_id="api-refresh-task-1", strategy_id="strategy-api", strategy_version=3)
    _task(db, task_id="api-refresh-task-2", strategy_id="strategy-api", strategy_version=3)
    db.commit()

    resp = client.post(
        "/api/image-production/strategies/metrics/refresh",
        json={"strategy_id": "strategy-api", "strategy_version": 3},
    )

    assert resp.status_code == 200
    assert resp.json()["refreshed"]["refreshed_count"] == 1
    db.expire_all()
    metric = (
        db.query(ImageProductionMetric)
        .filter(ImageProductionMetric.strategy_id == "strategy-api")
        .filter(ImageProductionMetric.strategy_version == 3)
        .filter(ImageProductionMetric.model_id == "model-1")
        .one_or_none()
    )
    assert metric is not None
    assert metric.attempt_count == 2


def test_strategy_recommendation_route_returns_payload(monkeypatch):
    expected = {
        "strategy_id": "strategy-1",
        "strategy_version": 1,
        "metrics": {"attempt_count": 10},
        "quality_score": 92,
        "confidence": "high",
        "status": "recommended",
        "recommendations": [{"code": "KEEP_STRATEGY"}],
        "automatic_mutation_allowed": False,
    }
    calls = []

    def fake_strategy_recommendation_payload(db, strategy_id):
        calls.append(strategy_id)
        return expected

    monkeypatch.setattr(
        router_module,
        "strategy_recommendation_payload",
        fake_strategy_recommendation_payload,
    )

    resp = client.get("/api/image-production/strategies/strategy-1/recommendations")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "recommendation": expected}
    assert calls == ["strategy-1"]
