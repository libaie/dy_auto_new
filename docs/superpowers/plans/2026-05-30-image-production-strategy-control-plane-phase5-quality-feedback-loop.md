# Image Production Strategy Control Plane Phase 5 Quality Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Phase 4 strategy metrics and A/B comparison records into an operator-visible quality feedback loop with refreshable metrics, strategy recommendations, and human-approved A/B winner suggestions.

**Architecture:** Keep `POST /api/image-creation/tasks` as the only image execution path and keep strategy edits human-approved. Phase 5 adds read-only recommendation services, manual/operational metrics refresh entry points, and compact frontend panels that explain what the system recommends without mutating strategies automatically.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest, Vue 3, Vitest, existing dy_auto image production services.

---

## Source Material

- Spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-28-image-production-strategy-control-plane-design.md`
- Phase 4 plan: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-29-image-production-strategy-control-plane-phase4-final-execution.md`
- Existing backend router: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Existing metrics service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_metrics_service.py`
- Existing A/B service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_ab_test_service.py`
- Existing strategy UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`
- Existing image workbench UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`

## Scope

Phase 5 implements:

- Batch metrics refresh for strategy/version/model combinations already present in image creation tasks.
- Strategy recommendation payloads based on persisted `ImageProductionMetric` rows.
- A/B winner recommendation payloads based on terminal attempts, approved assets, cost, latency, and pass-rate snapshots.
- Strategy Center UI controls for refreshing metrics and reading recommendations.
- Image Workbench A/B panel support for showing a suggested winner while keeping the current manual winner/no-winner decision buttons.

Phase 5 does not implement:

- Fully autonomous strategy mutation.
- Provider-online E2E runs that spend real image-generation credits.
- A standalone analytics product with its own navigation and chart suite.
- Pixel-level visual diff or zoom gallery.
- Changes to video generation, Pixelle, Seedance, or the image execution provider path.

## File Structure

### Backend

- Modify: `server/app/services/image_production_metrics_service.py`
  - Add reusable aggregate metric serialization.
  - Add batch refresh across observed task strategy/version/model keys.
- Create: `server/app/services/image_production_recommendation_service.py`
  - Build strategy recommendation payloads from strategy rows and metric rows.
  - Compute deterministic A/B winner recommendation payloads from A/B attempts.
- Modify: `server/app/services/image_ab_test_service.py`
  - Expose `recommend_ab_winner()` as the public A/B recommendation entry point.
- Modify: `server/app/routers/image_production.py`
  - Add metrics refresh, strategy recommendations, and A/B winner recommendation endpoints.
- Create: `server/scripts/refresh_image_strategy_metrics.py`
  - CLI-compatible refresh entry point for Windows Task Scheduler or another external scheduler.
- Modify: `server/tests/test_image_production_metrics_service.py`
  - Cover aggregate metrics and batch refresh behavior.
- Create: `server/tests/test_image_production_recommendation_service.py`
  - Cover strategy recommendation and A/B winner recommendation scoring.
- Modify: `server/tests/test_image_ab_service.py`
  - Cover public A/B recommendation integration if needed by current fixtures.
- Modify: `server/tests/test_image_ab_api.py`
  - Cover new A/B recommendation route.
- Create: `server/tests/test_image_production_recommendation_api.py`
  - Cover strategy recommendation and metrics refresh routes.

### Frontend

- Modify: `web/src/api/imageProduction.js`
  - Add wrappers for metrics refresh, strategy recommendations, and A/B winner recommendations.
- Modify: `web/src/views/ImageProductionStrategiesPage.vue`
  - Show a compact recommendation column/panel.
  - Add a refresh metrics button.
- Modify: `web/src/views/ImageCreationPage.vue`
  - Show suggested A/B winner and reasons beside existing manual decision actions.
- Modify: `web/src/__tests__/image-production-strategy-page.test.js`
  - Cover metrics refresh and recommendations UI.
- Modify: `web/src/__tests__/image-creation-page.test.js`
  - Cover A/B recommended winner UI and manual adoption remaining explicit.

## Data Contracts

### Metrics Refresh Response

```json
{
  "ok": true,
  "refreshed": {
    "refreshed_count": 2,
    "keys": [
      {
        "strategy_id": "strategy-1",
        "strategy_version": 1,
        "model_id": "model-1"
      }
    ]
  }
}
```

### Strategy Recommendation Response

```json
{
  "ok": true,
  "recommendation": {
    "strategy_id": "strategy-1",
    "strategy_version": 2,
    "quality_score": 74,
    "confidence": "low",
    "status": "cautious",
    "metrics": {
      "attempt_count": 4,
      "success_rate": 0.75,
      "ai_pass_rate": 0.5,
      "human_pass_rate": 0.25,
      "repaint_count": 1,
      "average_latency_seconds": 12.5,
      "average_cost_amount": 1.2,
      "currency": "CNY",
      "low_sample": true
    },
    "recommendations": [
      {
        "code": "LOW_SAMPLE",
        "severity": "info",
        "title": "Sample is still small",
        "description": "Collect at least 5 attempts before trusting this strategy score.",
        "action": "continue_collecting"
      }
    ],
    "automatic_mutation_allowed": false
  }
}
```

### A/B Winner Recommendation Response

```json
{
  "ok": true,
  "winner_recommendation": {
    "group_id": "ab-group-1",
    "eligible": true,
    "recommended_attempt_id": "attempt-1",
    "confidence": "medium",
    "reason": "Only this attempt has approved assets and a completed task.",
    "scores": [
      {
        "attempt_id": "attempt-1",
        "score": 88,
        "approved_asset_ready": true,
        "status": "completed",
        "reasons": ["approved asset ready", "completed task"]
      }
    ],
    "automatic_adoption_allowed": false
  }
}
```

## Task 1: Metrics Aggregation And Batch Refresh

**Files:**

- Modify: `server/app/services/image_production_metrics_service.py`
- Modify: `server/tests/test_image_production_metrics_service.py`
- Modify: `server/app/routers/image_production.py`
- Create: `server/scripts/refresh_image_strategy_metrics.py`
- Create: `server/tests/test_image_production_recommendation_api.py`

- [ ] **Step 1: Add failing aggregate and batch-refresh service tests**

Append these imports in `server/tests/test_image_production_metrics_service.py`:

```python
from app.services.image_production_metrics_service import (
    aggregate_strategy_metrics_payload,
    refresh_all_image_strategy_metrics,
)
```

Append these tests to `server/tests/test_image_production_metrics_service.py`:

```python
def test_aggregate_strategy_metrics_payload_weights_by_attempt_count(db):
    metric_a = ImageProductionMetric(
        strategy_id="strategy-a",
        strategy_version=1,
        model_id="model-a",
        attempt_count=2,
        success_count=1,
        failure_count=1,
        ai_pass_count=1,
        human_pass_count=1,
        repaint_count=1,
        average_latency_seconds=10,
        average_cost_amount=2,
        currency="CNY",
    )
    metric_b = ImageProductionMetric(
        strategy_id="strategy-a",
        strategy_version=1,
        model_id="model-b",
        attempt_count=6,
        success_count=6,
        failure_count=0,
        ai_pass_count=3,
        human_pass_count=2,
        repaint_count=0,
        average_latency_seconds=20,
        average_cost_amount=4,
        currency="CNY",
    )
    db.add_all([metric_a, metric_b])
    db.commit()

    payload = aggregate_strategy_metrics_payload([metric_a, metric_b])

    assert payload["attempt_count"] == 8
    assert payload["success_count"] == 7
    assert payload["failure_count"] == 1
    assert payload["success_rate"] == 0.875
    assert payload["ai_pass_rate"] == 0.5
    assert payload["human_pass_rate"] == 0.375
    assert payload["repaint_count"] == 1
    assert payload["average_latency_seconds"] == 17.5
    assert payload["average_cost_amount"] == 3.5
    assert payload["currency"] == "CNY"
    assert payload["low_sample"] is False


def test_refresh_all_image_strategy_metrics_refreshes_observed_keys(db):
    _task(db, task_id="batch-task-1", strategy_id="strategy-a", strategy_version=1, model_id="model-a")
    _task(db, task_id="batch-task-2", strategy_id="strategy-a", strategy_version=1, model_id="model-b")
    _task(db, task_id="batch-task-3", strategy_id="strategy-b", strategy_version=2, model_id=None)
    db.commit()

    result = refresh_all_image_strategy_metrics(db)

    assert result["refreshed_count"] == 3
    assert {
        (item["strategy_id"], item["strategy_version"], item["model_id"])
        for item in result["keys"]
    } == {
        ("strategy-a", 1, "model-a"),
        ("strategy-a", 1, "model-b"),
        ("strategy-b", 2, None),
    }
    assert db.query(ImageProductionMetric).count() == 3


def test_refresh_all_image_strategy_metrics_can_filter_strategy(db):
    _task(db, task_id="batch-task-4", strategy_id="strategy-a", strategy_version=1, model_id="model-a")
    _task(db, task_id="batch-task-5", strategy_id="strategy-b", strategy_version=1, model_id="model-b")
    db.commit()

    result = refresh_all_image_strategy_metrics(db, strategy_id="strategy-a")

    assert result["refreshed_count"] == 1
    assert result["keys"] == [{
        "strategy_id": "strategy-a",
        "strategy_version": 1,
        "model_id": "model-a",
    }]
```

- [ ] **Step 2: Run the service tests and verify they fail for missing functions**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_metrics_service.py -v -p no:cacheprovider
```

Expected: FAIL with an import error or missing attribute error for `aggregate_strategy_metrics_payload` and `refresh_all_image_strategy_metrics`.

- [ ] **Step 3: Implement aggregate metrics and batch refresh**

In `server/app/services/image_production_metrics_service.py`, add these functions below `strategy_metrics_payload()`:

```python
def _weighted_metric_average(metrics: list[ImageProductionMetric], field: str) -> float:
    total_attempts = sum(max(metric.attempt_count or 0, 0) for metric in metrics)
    if total_attempts == 0:
        return 0.0
    total = sum(
        float(getattr(metric, field) or 0.0) * max(metric.attempt_count or 0, 0)
        for metric in metrics
    )
    return round(total / total_attempts, 4)


def aggregate_strategy_metrics_payload(metrics: list[ImageProductionMetric]) -> dict[str, Any]:
    if not metrics:
        return strategy_metrics_payload(None)

    attempt_count = sum(metric.attempt_count or 0 for metric in metrics)
    success_count = sum(metric.success_count or 0 for metric in metrics)
    failure_count = sum(metric.failure_count or 0 for metric in metrics)
    ai_pass_count = sum(metric.ai_pass_count or 0 for metric in metrics)
    human_pass_count = sum(metric.human_pass_count or 0 for metric in metrics)
    repaint_count = sum(metric.repaint_count or 0 for metric in metrics)
    currencies = {metric.currency for metric in metrics if metric.currency}
    updated_at = max((metric.updated_at for metric in metrics if metric.updated_at), default=None)
    attempts = max(attempt_count, 1)
    return {
        "attempt_count": attempt_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_count / attempts, 4),
        "ai_pass_rate": round(ai_pass_count / attempts, 4),
        "human_pass_rate": round(human_pass_count / attempts, 4),
        "repaint_count": repaint_count,
        "average_latency_seconds": _weighted_metric_average(metrics, "average_latency_seconds"),
        "average_cost_amount": _weighted_metric_average(metrics, "average_cost_amount"),
        "currency": next(iter(currencies)) if len(currencies) == 1 else "MIXED" if currencies else "CNY",
        "low_sample": attempt_count < 5,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def refresh_all_image_strategy_metrics(
    db: Session,
    strategy_id: str | None = None,
    strategy_version: int | None = None,
) -> dict[str, Any]:
    key_query = (
        db.query(
            ImageCreationTask.strategy_id,
            ImageCreationTask.strategy_version,
            ImageCreationTask.model_id,
        )
        .filter(ImageCreationTask.strategy_id.isnot(None))
        .filter(ImageCreationTask.strategy_version.isnot(None))
        .distinct()
    )
    if strategy_id:
        key_query = key_query.filter(ImageCreationTask.strategy_id == strategy_id)
    if strategy_version is not None:
        key_query = key_query.filter(ImageCreationTask.strategy_version == strategy_version)

    refreshed_keys: list[dict[str, Any]] = []
    for row in key_query.all():
        metric = refresh_image_strategy_metrics(
            db,
            row.strategy_id,
            row.strategy_version,
            row.model_id,
        )
        refreshed_keys.append({
            "strategy_id": metric.strategy_id,
            "strategy_version": metric.strategy_version,
            "model_id": metric.model_id,
        })

    return {
        "refreshed_count": len(refreshed_keys),
        "keys": refreshed_keys,
    }
```

- [ ] **Step 4: Replace router-local aggregate metric logic with the service helper**

In `server/app/routers/image_production.py`, add the import:

```python
from app.services.image_production_metrics_service import (
    aggregate_strategy_metrics_payload,
    refresh_all_image_strategy_metrics,
)
```

Replace `_strategy_payload_with_metric()` with:

```python
def _strategy_payload_with_metric(
    strategy: ImageProductionStrategy,
    metrics: list[ImageProductionMetric],
) -> dict:
    payload = strategy_payload(strategy)
    payload["metrics"] = aggregate_strategy_metrics_payload(metrics)
    return payload
```

Leave `_weighted_average()` and `_aggregate_strategy_metrics()` in place only if another local function still calls them after this change. If neither is referenced, remove those two unused helpers in the same patch.

- [ ] **Step 5: Add the metrics refresh route test**

Create `server/tests/test_image_production_recommendation_api.py` with:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.routers import image_production as router_module


client = TestClient(app)


def test_refresh_strategy_metrics_route_returns_refreshed_keys(monkeypatch):
    def fake_refresh_all(db, strategy_id=None, strategy_version=None):
        assert strategy_id == "strategy-1"
        assert strategy_version == 2
        return {
            "refreshed_count": 1,
            "keys": [{
                "strategy_id": "strategy-1",
                "strategy_version": 2,
                "model_id": "model-1",
            }],
        }

    monkeypatch.setattr(router_module, "refresh_all_image_strategy_metrics", fake_refresh_all, raising=False)

    resp = client.post(
        "/api/image-production/strategies/metrics/refresh",
        json={"strategy_id": "strategy-1", "strategy_version": 2},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "refreshed": {
            "refreshed_count": 1,
            "keys": [{
                "strategy_id": "strategy-1",
                "strategy_version": 2,
                "model_id": "model-1",
            }],
        },
    }
```

- [ ] **Step 6: Add the metrics refresh endpoint**

In `server/app/routers/image_production.py`, add this request model near the other Pydantic models:

```python
class MetricsRefreshRequest(BaseModel):
    strategy_id: str | None = None
    strategy_version: int | None = None
```

Add this route before the existing dynamic `@router.get("/strategies/{strategy_id}")` route:

```python
@router.post("/strategies/metrics/refresh")
def refresh_strategy_metrics(
    body: MetricsRefreshRequest,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    refreshed = refresh_all_image_strategy_metrics(
        db,
        strategy_id=body.strategy_id,
        strategy_version=body.strategy_version,
    )
    db.commit()
    return {"ok": True, "refreshed": refreshed}
```

- [ ] **Step 7: Add a CLI-compatible refresh script**

Create `server/scripts/refresh_image_strategy_metrics.py`:

```python
from __future__ import annotations

from app.database import SessionLocal
from app.services.image_production_metrics_service import refresh_all_image_strategy_metrics


def main() -> int:
    db = SessionLocal()
    try:
        refreshed = refresh_all_image_strategy_metrics(db)
        db.commit()
        print(
            "refreshed_count={count}".format(
                count=refreshed["refreshed_count"],
            )
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run Task 1 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_metrics_service.py tests/test_image_production_recommendation_api.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/image_production_metrics_service.py server/app/routers/image_production.py server/scripts/refresh_image_strategy_metrics.py server/tests/test_image_production_metrics_service.py server/tests/test_image_production_recommendation_api.py
git commit -m "feat: add image strategy metrics refresh loop"
```

## Task 2: Strategy Recommendation Service And API

**Files:**

- Create: `server/app/services/image_production_recommendation_service.py`
- Create: `server/tests/test_image_production_recommendation_service.py`
- Modify: `server/app/routers/image_production.py`
- Modify: `server/tests/test_image_production_recommendation_api.py`

- [ ] **Step 1: Add failing strategy recommendation service tests**

Create `server/tests/test_image_production_recommendation_service.py`:

```python
from app.db_models import ImageProductionMetric, ImageProductionStrategy
from app.services.image_production_recommendation_service import strategy_recommendation_payload


def _strategy(db, strategy_id="strategy-1", version=1, status="active"):
    strategy = ImageProductionStrategy(
        id=strategy_id,
        slug=strategy_id,
        name=f"Strategy {strategy_id}",
        destination_role="image_to_video_input",
        supported_modes_json=["image_to_image"],
        fallback_model_ids_json=[],
        common_parameters_json={},
        provider_options_json={},
        status=status,
        version=version,
    )
    db.add(strategy)
    db.flush()
    return strategy


def _metric(db, *, strategy_id="strategy-1", version=1, attempts=8, success=7, ai_pass=6, human_pass=5, repaint=1, latency=8.0, cost=1.2):
    metric = ImageProductionMetric(
        strategy_id=strategy_id,
        strategy_version=version,
        model_id="model-1",
        attempt_count=attempts,
        success_count=success,
        failure_count=max(attempts - success, 0),
        ai_pass_count=ai_pass,
        human_pass_count=human_pass,
        repaint_count=repaint,
        average_latency_seconds=latency,
        average_cost_amount=cost,
        currency="CNY",
    )
    db.add(metric)
    db.flush()
    return metric


def test_strategy_recommendation_marks_low_sample_as_cautious(db):
    strategy = _strategy(db)
    _metric(db, attempts=3, success=3, ai_pass=2, human_pass=1, repaint=0)
    db.commit()

    payload = strategy_recommendation_payload(db, strategy.id)

    assert payload["strategy_id"] == strategy.id
    assert payload["strategy_version"] == 1
    assert payload["status"] == "cautious"
    assert payload["confidence"] == "low"
    assert payload["metrics"]["low_sample"] is True
    assert payload["automatic_mutation_allowed"] is False
    assert [item["code"] for item in payload["recommendations"]] == ["LOW_SAMPLE"]


def test_strategy_recommendation_warns_on_failures_and_repaints(db):
    strategy = _strategy(db)
    _metric(db, attempts=10, success=5, ai_pass=4, human_pass=3, repaint=4, latency=18.0, cost=2.5)
    db.commit()

    payload = strategy_recommendation_payload(db, strategy.id)

    codes = {item["code"] for item in payload["recommendations"]}
    assert payload["status"] == "cautious"
    assert payload["confidence"] == "medium"
    assert "HIGH_FAILURE_RATE" in codes
    assert "HIGH_REPAINT_RATE" in codes
    assert payload["quality_score"] < 70


def test_strategy_recommendation_marks_strong_strategy_recommended(db):
    strategy = _strategy(db)
    _metric(db, attempts=12, success=12, ai_pass=11, human_pass=9, repaint=0, latency=5.0, cost=0.8)
    db.commit()

    payload = strategy_recommendation_payload(db, strategy.id)

    assert payload["status"] == "recommended"
    assert payload["confidence"] == "high"
    assert payload["quality_score"] >= 85
    assert payload["recommendations"][0]["code"] == "KEEP_STRATEGY"
```

- [ ] **Step 2: Run the service tests and verify they fail for the missing module**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_recommendation_service.py -v -p no:cacheprovider
```

Expected: FAIL with `ModuleNotFoundError` for `app.services.image_production_recommendation_service`.

- [ ] **Step 3: Implement strategy recommendation service**

Create `server/app/services/image_production_recommendation_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db_models import (
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionMetric,
    ImageProductionStrategy,
)
from app.services.image_creation_errors import image_error
from app.services.image_production_metrics_service import aggregate_strategy_metrics_payload


MIN_RELIABLE_SAMPLE_SIZE = 5
TERMINAL_AB_STATUSES = {"completed", "failed", "cancelled", "completed_with_warnings"}
SUCCESS_AB_STATUSES = {"completed", "completed_with_warnings"}


def _strategy_or_404(db: Session, strategy_id: str) -> ImageProductionStrategy:
    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if not strategy:
        raise image_error(
            404,
            "IMAGE_STRATEGY_NOT_FOUND",
            "Image production strategy was not found.",
            "Reload strategies and try again.",
            retryable=False,
            affected_ids=[strategy_id],
        )
    return strategy


def _score_from_metrics(metrics: dict[str, Any]) -> int:
    score = 100
    if metrics["attempt_count"] == 0:
        return 0
    score -= int((1 - metrics["success_rate"]) * 35)
    score -= int(max(0, 0.7 - metrics["ai_pass_rate"]) * 20)
    score -= int(max(0, 0.5 - metrics["human_pass_rate"]) * 15)
    repaint_rate = metrics["repaint_count"] / max(metrics["attempt_count"], 1)
    score -= int(repaint_rate * 20)
    if metrics["average_latency_seconds"] > 15:
        score -= 8
    if metrics["average_cost_amount"] > 3:
        score -= 8
    if metrics["low_sample"]:
        score -= 10
    return max(0, min(100, score))


def _confidence(metrics: dict[str, Any], score: int) -> str:
    if metrics["attempt_count"] < MIN_RELIABLE_SAMPLE_SIZE:
        return "low"
    if metrics["attempt_count"] >= 10 and score >= 80:
        return "high"
    return "medium"


def _status(metrics: dict[str, Any], score: int) -> str:
    if metrics["attempt_count"] == 0:
        return "cautious"
    if metrics["low_sample"] or score < 75:
        return "cautious"
    return "recommended"


def _recommendation_items(metrics: dict[str, Any], score: int) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if metrics["low_sample"]:
        items.append({
            "code": "LOW_SAMPLE",
            "severity": "info",
            "title": "Sample is still small",
            "description": "Collect at least 5 attempts before trusting this strategy score.",
            "action": "continue_collecting",
        })

    failure_rate = 1 - metrics["success_rate"]
    if metrics["attempt_count"] >= MIN_RELIABLE_SAMPLE_SIZE and failure_rate >= 0.25:
        items.append({
            "code": "HIGH_FAILURE_RATE",
            "severity": "warning",
            "title": "Failure rate is high",
            "description": "Review model selection, provider options, and fallback strategy before wider use.",
            "action": "review_model_and_fallbacks",
        })

    repaint_rate = metrics["repaint_count"] / max(metrics["attempt_count"], 1)
    if metrics["attempt_count"] >= MIN_RELIABLE_SAMPLE_SIZE and repaint_rate >= 0.25:
        items.append({
            "code": "HIGH_REPAINT_RATE",
            "severity": "warning",
            "title": "Repaint rate is high",
            "description": "Generated images often require repair. Tighten prompt templates or review policy.",
            "action": "review_prompt_and_review_policy",
        })

    if metrics["attempt_count"] >= MIN_RELIABLE_SAMPLE_SIZE and metrics["human_pass_rate"] < 0.4:
        items.append({
            "code": "LOW_HUMAN_PASS_RATE",
            "severity": "warning",
            "title": "Human pass rate is low",
            "description": "Manual reviewers are blocking many outputs. Inspect recent failures before scaling.",
            "action": "inspect_review_failures",
        })

    if not items:
        items.append({
            "code": "KEEP_STRATEGY",
            "severity": "success",
            "title": "Strategy is performing well",
            "description": "Current metrics support continued use with human-approved changes only.",
            "action": "keep_strategy",
        })
    return items


def strategy_recommendation_payload(db: Session, strategy_id: str) -> dict[str, Any]:
    strategy = _strategy_or_404(db, strategy_id)
    metric_rows = (
        db.query(ImageProductionMetric)
        .filter(ImageProductionMetric.strategy_id == strategy.id)
        .filter(ImageProductionMetric.strategy_version == strategy.version)
        .all()
    )
    metrics = aggregate_strategy_metrics_payload(metric_rows)
    score = _score_from_metrics(metrics)
    return {
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "strategy_name": strategy.name,
        "quality_score": score,
        "confidence": _confidence(metrics, score),
        "status": _status(metrics, score),
        "metrics": metrics,
        "recommendations": _recommendation_items(metrics, score),
        "automatic_mutation_allowed": False,
    }
```

The A/B helper imports in this file are used in Task 3. Keep them in the import block now so Task 3 can extend the same service without moving imports.

- [ ] **Step 4: Add the strategy recommendation route test**

Append this test to `server/tests/test_image_production_recommendation_api.py`:

```python
def test_strategy_recommendation_route_returns_payload(monkeypatch):
    def fake_recommendation(db, strategy_id):
        assert strategy_id == "strategy-1"
        return {
            "strategy_id": "strategy-1",
            "strategy_version": 1,
            "strategy_name": "Strategy 1",
            "quality_score": 74,
            "confidence": "medium",
            "status": "cautious",
            "metrics": {"attempt_count": 8, "low_sample": False},
            "recommendations": [{"code": "HIGH_FAILURE_RATE"}],
            "automatic_mutation_allowed": False,
        }

    monkeypatch.setattr(router_module, "strategy_recommendation_payload", fake_recommendation, raising=False)

    resp = client.get("/api/image-production/strategies/strategy-1/recommendations")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["recommendation"]["strategy_id"] == "strategy-1"
    assert resp.json()["recommendation"]["automatic_mutation_allowed"] is False
```

- [ ] **Step 5: Add the strategy recommendation endpoint**

In `server/app/routers/image_production.py`, add the import:

```python
from app.services.image_production_recommendation_service import strategy_recommendation_payload
```

Add this route before the dynamic `@router.get("/strategies/{strategy_id}")` route:

```python
@router.get("/strategies/{strategy_id}/recommendations")
def strategy_recommendations(
    strategy_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    return {
        "ok": True,
        "recommendation": strategy_recommendation_payload(db, strategy_id),
    }
```

- [ ] **Step 6: Run Task 2 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_recommendation_service.py tests/test_image_production_recommendation_api.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/image_production_recommendation_service.py server/app/routers/image_production.py server/tests/test_image_production_recommendation_service.py server/tests/test_image_production_recommendation_api.py
git commit -m "feat: add image strategy recommendations"
```

## Task 3: A/B Winner Recommendation Service And API

**Files:**

- Modify: `server/app/services/image_production_recommendation_service.py`
- Modify: `server/app/services/image_ab_test_service.py`
- Modify: `server/tests/test_image_production_recommendation_service.py`
- Modify: `server/tests/test_image_ab_api.py`
- Modify: `server/app/routers/image_production.py`

- [ ] **Step 1: Add failing A/B winner recommendation tests**

Append these imports to `server/tests/test_image_production_recommendation_service.py`:

```python
from app.db_models import ImageCreationAsset, ImageCreationTask, ImageProductionAbAttempt, ImageProductionAbGroup
from app.services.image_production_recommendation_service import ab_winner_recommendation_payload
```

Append these helpers and tests:

```python
def _ab_group(db, group_id="ab-group-1", status="completed"):
    group = ImageProductionAbGroup(
        id=group_id,
        user_id="test-user-id",
        source_request_hash="hash-1",
        prompt_snapshot_json={"prompt": "compare"},
        cost_confirmation_json={},
        status=status,
    )
    db.add(group)
    db.flush()
    return group


def _ab_task(db, task_id, status="completed", strategy_id="strategy-1", model_id="model-1"):
    task = ImageCreationTask(
        id=task_id,
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status=status,
        prompt=f"prompt {task_id}",
        count=1,
        target_count=1,
        strategy_id=strategy_id,
        strategy_version=1,
        model_id=model_id,
    )
    db.add(task)
    db.flush()
    return task


def _ab_attempt(db, *, attempt_id, group_id="ab-group-1", task_id=None, strategy_id="strategy-1", status="completed", metrics=None):
    attempt = ImageProductionAbAttempt(
        id=attempt_id,
        group_id=group_id,
        task_id=task_id,
        strategy_id=strategy_id,
        strategy_version=1,
        model_id="model-1",
        status=status,
        metrics_snapshot_json=metrics or {},
    )
    db.add(attempt)
    db.flush()
    return attempt


def _approved_asset(db, task_id):
    asset = ImageCreationAsset(
        task_id=task_id,
        url="https://img.example/approved.png",
        status="approved",
        audit_status="approved",
    )
    db.add(asset)
    db.flush()
    return asset


def test_ab_winner_recommendation_selects_only_approved_completed_attempt(db):
    _ab_group(db)
    task_a = _ab_task(db, "task-a", strategy_id="strategy-a")
    task_b = _ab_task(db, "task-b", strategy_id="strategy-b")
    _approved_asset(db, task_a.id)
    _ab_attempt(db, attempt_id="attempt-a", task_id=task_a.id, strategy_id="strategy-a")
    _ab_attempt(db, attempt_id="attempt-b", task_id=task_b.id, strategy_id="strategy-b")
    db.commit()

    payload = ab_winner_recommendation_payload(db, "ab-group-1", user_id="test-user-id")

    assert payload["eligible"] is True
    assert payload["recommended_attempt_id"] == "attempt-a"
    assert payload["automatic_adoption_allowed"] is False
    assert payload["scores"][0]["attempt_id"] == "attempt-a"
    assert payload["scores"][0]["approved_asset_ready"] is True


def test_ab_winner_recommendation_requires_terminal_attempts(db):
    _ab_group(db, status="running")
    task_a = _ab_task(db, "task-running", status="running", strategy_id="strategy-a")
    _approved_asset(db, task_a.id)
    _ab_attempt(db, attempt_id="attempt-running", task_id=task_a.id, strategy_id="strategy-a", status="running")
    db.commit()

    payload = ab_winner_recommendation_payload(db, "ab-group-1", user_id="test-user-id")

    assert payload["eligible"] is False
    assert payload["recommended_attempt_id"] is None
    assert payload["reason_code"] == "ATTEMPTS_NOT_TERMINAL"


def test_ab_winner_recommendation_returns_none_when_no_approved_assets(db):
    _ab_group(db)
    task_a = _ab_task(db, "task-a", strategy_id="strategy-a")
    task_b = _ab_task(db, "task-b", strategy_id="strategy-b")
    _ab_attempt(db, attempt_id="attempt-a", task_id=task_a.id, strategy_id="strategy-a")
    _ab_attempt(db, attempt_id="attempt-b", task_id=task_b.id, strategy_id="strategy-b")
    db.commit()

    payload = ab_winner_recommendation_payload(db, "ab-group-1", user_id="test-user-id")

    assert payload["eligible"] is False
    assert payload["recommended_attempt_id"] is None
    assert payload["reason_code"] == "NO_APPROVED_ASSET"
```

- [ ] **Step 2: Run the A/B recommendation tests and verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_recommendation_service.py -v -p no:cacheprovider
```

Expected: FAIL with missing `ab_winner_recommendation_payload`.

- [ ] **Step 3: Implement A/B winner recommendation scoring**

Append this code to `server/app/services/image_production_recommendation_service.py`:

```python
def _ab_group_or_404(db: Session, group_id: str, user_id: str | None) -> ImageProductionAbGroup:
    group = db.query(ImageProductionAbGroup).filter(ImageProductionAbGroup.id == group_id).first()
    if not group or group.user_id != user_id:
        raise image_error(
            404,
            "IMAGE_AB_TEST_GROUP_NOT_FOUND",
            "A/B group was not found.",
            "Reload A/B comparisons.",
            retryable=False,
            affected_ids=[group_id],
        )
    return group


def _attempts_for_group(db: Session, group_id: str) -> list[ImageProductionAbAttempt]:
    return (
        db.query(ImageProductionAbAttempt)
        .filter(ImageProductionAbAttempt.group_id == group_id)
        .order_by(ImageProductionAbAttempt.created_at.asc(), ImageProductionAbAttempt.id.asc())
        .all()
    )


def _approved_asset_ready(db: Session, attempt: ImageProductionAbAttempt) -> bool:
    if not attempt.task_id:
        return False
    from app.db_models import ImageCreationAsset

    return (
        db.query(ImageCreationAsset.id)
        .filter(ImageCreationAsset.task_id == attempt.task_id)
        .filter(ImageCreationAsset.status == "approved")
        .first()
        is not None
    )


def _attempt_metric_value(attempt: ImageProductionAbAttempt, key: str, default: float = 0.0) -> float:
    metrics = (attempt.metrics_snapshot_json or {}).get("metrics") or {}
    try:
        return float(metrics.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _ab_attempt_score(db: Session, attempt: ImageProductionAbAttempt) -> dict[str, Any]:
    approved = _approved_asset_ready(db, attempt)
    reasons: list[str] = []
    score = 0
    if approved:
        score += 55
        reasons.append("approved asset ready")
    if attempt.status in SUCCESS_AB_STATUSES:
        score += 20
        reasons.append("completed task")
    if attempt.status == "completed_with_warnings":
        score -= 5
        reasons.append("completed with warnings")
    if attempt.status == "failed":
        score -= 40
        reasons.append("failed task")

    success_rate = _attempt_metric_value(attempt, "success_rate")
    ai_pass_rate = _attempt_metric_value(attempt, "ai_pass_rate")
    human_pass_rate = _attempt_metric_value(attempt, "human_pass_rate")
    repaint_count = _attempt_metric_value(attempt, "repaint_count")
    average_cost = _attempt_metric_value(attempt, "average_cost_amount")
    average_latency = _attempt_metric_value(attempt, "average_latency_seconds")
    score += int(success_rate * 10)
    score += int(ai_pass_rate * 6)
    score += int(human_pass_rate * 6)
    score -= min(int(repaint_count * 3), 12)
    if average_latency and average_latency <= 10:
        score += 3
        reasons.append("fast enough")
    if average_cost and average_cost <= 2:
        score += 3
        reasons.append("cost controlled")

    return {
        "attempt_id": attempt.id,
        "strategy_id": attempt.strategy_id,
        "strategy_version": attempt.strategy_version,
        "model_id": attempt.model_id,
        "status": attempt.status,
        "approved_asset_ready": approved,
        "score": max(0, min(100, score)),
        "reasons": reasons,
    }


def _empty_ab_recommendation(group_id: str, reason_code: str, reason: str, scores: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "eligible": False,
        "recommended_attempt_id": None,
        "confidence": "none",
        "reason_code": reason_code,
        "reason": reason,
        "scores": scores or [],
        "automatic_adoption_allowed": False,
    }


def ab_winner_recommendation_payload(db: Session, group_id: str, user_id: str | None = None) -> dict[str, Any]:
    group = _ab_group_or_404(db, group_id, user_id)
    if group.winner_attempt_id or group.status in {"winner_selected", "no_winner"}:
        return _empty_ab_recommendation(
            group.id,
            "DECISION_EXISTS",
            "This A/B group already has a recorded decision.",
        )

    attempts = _attempts_for_group(db, group.id)
    if not attempts:
        return _empty_ab_recommendation(group.id, "NO_ATTEMPTS", "This A/B group has no attempts.")

    scores = [_ab_attempt_score(db, attempt) for attempt in attempts]
    statuses = {attempt.status for attempt in attempts}
    if not statuses.issubset(TERMINAL_AB_STATUSES):
        return _empty_ab_recommendation(
            group.id,
            "ATTEMPTS_NOT_TERMINAL",
            "Wait for all A/B attempts to finish, then refresh the comparison.",
            scores,
        )

    eligible_scores = [score for score in scores if score["approved_asset_ready"] and score["status"] in SUCCESS_AB_STATUSES]
    if not eligible_scores:
        return _empty_ab_recommendation(
            group.id,
            "NO_APPROVED_ASSET",
            "No attempt has an approved image asset ready for manual winner selection.",
            scores,
        )

    ranked = sorted(eligible_scores, key=lambda item: (-item["score"], item["attempt_id"]))
    winner = ranked[0]
    margin = winner["score"] - (ranked[1]["score"] if len(ranked) > 1 else 0)
    confidence = "high" if margin >= 20 else "medium" if margin >= 8 else "low"
    return {
        "group_id": group.id,
        "eligible": True,
        "recommended_attempt_id": winner["attempt_id"],
        "confidence": confidence,
        "reason_code": "RECOMMENDED_WINNER",
        "reason": "Recommended from approved asset availability, terminal status, quality metrics, cost, and latency.",
        "scores": sorted(scores, key=lambda item: (-item["score"], item["attempt_id"])),
        "automatic_adoption_allowed": False,
    }
```

- [ ] **Step 4: Expose public A/B service function**

In `server/app/services/image_ab_test_service.py`, add this import:

```python
from app.services.image_production_recommendation_service import ab_winner_recommendation_payload
```

Add this function near the other public A/B functions:

```python
def recommend_ab_winner(db: Session, group_id: str, user_id: str | None = None) -> dict[str, Any]:
    return ab_winner_recommendation_payload(db, group_id, user_id=user_id)
```

- [ ] **Step 5: Add A/B recommendation route test**

Append this test to `server/tests/test_image_ab_api.py`:

```python
def test_ab_winner_recommendation_route_returns_suggestion(monkeypatch):
    def fake_recommend(db, group_id, user_id=None):
        assert group_id == "ab-group-1"
        assert user_id == "test-user-id"
        return {
            "group_id": "ab-group-1",
            "eligible": True,
            "recommended_attempt_id": "attempt-1",
            "confidence": "medium",
            "reason_code": "RECOMMENDED_WINNER",
            "reason": "recommended",
            "scores": [{"attempt_id": "attempt-1", "score": 88}],
            "automatic_adoption_allowed": False,
        }

    monkeypatch.setattr(router_module, "recommend_ab_winner", fake_recommend, raising=False)

    resp = client.get("/api/image-production/ab-tests/ab-group-1/winner-recommendation")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["winner_recommendation"]["recommended_attempt_id"] == "attempt-1"
    assert resp.json()["winner_recommendation"]["automatic_adoption_allowed"] is False
```

- [ ] **Step 6: Add A/B winner recommendation route**

In `server/app/routers/image_production.py`, include `recommend_ab_winner` in the import from `image_ab_test_service`:

```python
from app.services.image_ab_test_service import (
    adopt_ab_winner,
    create_ab_group,
    get_ab_group,
    mark_ab_no_winner,
    preview_ab_group,
    recommend_ab_winner,
    refresh_ab_group,
    serialize_ab_group,
)
```

Add this route near the existing A/B routes:

```python
@router.get("/ab-tests/{group_id}/winner-recommendation")
def ab_winner_recommendation(
    group_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    return {
        "ok": True,
        "winner_recommendation": recommend_ab_winner(db, group_id, user_id=_auth_user_id(user)),
    }
```

- [ ] **Step 7: Run Task 3 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_recommendation_service.py tests/test_image_ab_api.py tests/test_image_ab_service.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/image_production_recommendation_service.py server/app/services/image_ab_test_service.py server/app/routers/image_production.py server/tests/test_image_production_recommendation_service.py server/tests/test_image_ab_api.py server/tests/test_image_ab_service.py
git commit -m "feat: recommend image ab winners"
```

## Task 4: Strategy Center Recommendation UI

**Files:**

- Modify: `web/src/api/imageProduction.js`
- Modify: `web/src/views/ImageProductionStrategiesPage.vue`
- Modify: `web/src/__tests__/image-production-strategy-page.test.js`

- [ ] **Step 1: Add failing frontend tests for metrics refresh and recommendations**

In `web/src/__tests__/image-production-strategy-page.test.js`, extend the hoisted mocks:

```javascript
const mocks = vi.hoisted(() => ({
  listImageProductionStrategies: vi.fn(),
  archiveImageProductionStrategy: vi.fn(),
  updateImageProductionStrategy: vi.fn(),
  refreshImageProductionMetrics: vi.fn(),
  getImageProductionStrategyRecommendations: vi.fn(),
  listModels: vi.fn(),
}))
```

Extend the `vi.mock('../api/imageProduction.js', ...)` block:

```javascript
vi.mock('../api/imageProduction.js', () => ({
  listImageProductionStrategies: mocks.listImageProductionStrategies,
  archiveImageProductionStrategy: mocks.archiveImageProductionStrategy,
  updateImageProductionStrategy: mocks.updateImageProductionStrategy,
  refreshImageProductionMetrics: mocks.refreshImageProductionMetrics,
  getImageProductionStrategyRecommendations: mocks.getImageProductionStrategyRecommendations,
}))
```

Add defaults in `beforeEach()`:

```javascript
api.refreshImageProductionMetrics.mockResolvedValue({
  data: { ok: true, refreshed: { refreshed_count: 1, keys: [] } },
})
api.getImageProductionStrategyRecommendations.mockResolvedValue({
  data: {
    ok: true,
    recommendation: {
      strategy_id: 'strategy-1',
      strategy_version: 1,
      quality_score: 86,
      confidence: 'high',
      status: 'recommended',
      metrics: { attempt_count: 12, low_sample: false },
      recommendations: [{ code: 'KEEP_STRATEGY', title: '策略表现稳定', severity: 'success' }],
      automatic_mutation_allowed: false,
    },
  },
})
```

Append these tests:

```javascript
it('refreshes metrics from the strategy center without changing strategy config', async () => {
  const wrapper = mount(Page)
  await flushPromises()

  await wrapper.get('[data-testid="refresh-image-metrics"]').trigger('click')
  await flushPromises()

  expect(api.refreshImageProductionMetrics).toHaveBeenCalledWith({})
  expect(api.listImageProductionStrategies).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain('已刷新 1 组指标')
})

it('loads and displays recommendation for one strategy', async () => {
  const wrapper = mount(Page)
  await flushPromises()

  await wrapper.get('[data-testid="show-strategy-recommendation-strategy-1"]').trigger('click')
  await flushPromises()

  expect(api.getImageProductionStrategyRecommendations).toHaveBeenCalledWith('strategy-1')
  expect(wrapper.text()).toContain('质量评分 86')
  expect(wrapper.text()).toContain('策略表现稳定')
  expect(wrapper.text()).toContain('策略变更仍需人工确认')
})
```

- [ ] **Step 2: Run frontend strategy page test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-production-strategy-page.test.js --run
```

Expected: FAIL because the API wrappers and UI selectors do not exist.

- [ ] **Step 3: Add frontend API wrappers**

In `web/src/api/imageProduction.js`, append:

```javascript
export function refreshImageProductionMetrics(payload = {}) {
  return client.post('/image-production/strategies/metrics/refresh', payload)
}

export function getImageProductionStrategyRecommendations(strategyId) {
  return client.get(`/image-production/strategies/${strategyId}/recommendations`)
}
```

- [ ] **Step 4: Update strategy page imports and state**

In `web/src/views/ImageProductionStrategiesPage.vue`, extend the import from `../api/imageProduction.js`:

```javascript
import {
  archiveImageProductionStrategy,
  getImageProductionStrategyRecommendations,
  listImageProductionStrategies,
  refreshImageProductionMetrics,
  updateImageProductionStrategy,
} from '../api/imageProduction.js'
```

Add these refs near the existing page state:

```javascript
const metricsMessage = ref('')
const recommendationLoadingId = ref('')
const recommendationError = ref('')
const activeRecommendation = ref(null)
```

Add these functions in the script:

```javascript
function recommendationStatusLabel(status) {
  if (status === 'recommended') return '推荐使用'
  if (status === 'cautious') return '谨慎观察'
  if (status === 'disabled') return '建议停用'
  return '待评估'
}

async function refreshMetrics() {
  metricsMessage.value = ''
  error.value = ''
  try {
    const response = await refreshImageProductionMetrics({})
    const refreshed = response?.data?.refreshed || {}
    metricsMessage.value = `已刷新 ${refreshed.refreshed_count || 0} 组指标`
    await loadStrategies()
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function showRecommendation(strategyId) {
  recommendationLoadingId.value = strategyId
  recommendationError.value = ''
  activeRecommendation.value = null
  try {
    const response = await getImageProductionStrategyRecommendations(strategyId)
    activeRecommendation.value = response?.data?.recommendation || null
  } catch (e) {
    recommendationError.value = normalizeError(e)
  } finally {
    recommendationLoadingId.value = ''
  }
}
```

- [ ] **Step 5: Add strategy page UI controls**

In the strategy page header action area, keep the existing refresh strategy button and add this button next to it:

```vue
<button
  type="button"
  data-testid="refresh-image-metrics"
  class="min-h-11 border border-emerald-500/40 px-4 py-2 text-sm font-medium text-emerald-100 hover:bg-emerald-950/40"
  @click="refreshMetrics"
>
  刷新质量指标
</button>
```

Below the existing error paragraph, add:

```vue
<p
  v-if="metricsMessage"
  data-testid="image-metrics-message"
  class="mb-4 border border-emerald-500/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100"
>
  {{ metricsMessage }}
</p>
```

In each strategy row action group, add:

```vue
<button
  type="button"
  :data-testid="`show-strategy-recommendation-${strategy.id}`"
  class="min-h-11 border border-cyan-500/40 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-950/40"
  :disabled="recommendationLoadingId === strategy.id"
  @click="showRecommendation(strategy.id)"
>
  {{ recommendationLoadingId === strategy.id ? '分析中' : '质量建议' }}
</button>
```

Below the strategy table section, add:

```vue
<section
  v-if="activeRecommendation || recommendationError"
  data-testid="strategy-recommendation-panel"
  class="mt-4 border border-slate-800 bg-slate-950/70 p-4"
>
  <p v-if="recommendationError" class="text-sm text-rose-300">{{ recommendationError }}</p>
  <div v-else-if="activeRecommendation">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold">策略质量建议</h2>
        <p class="mt-1 text-sm text-slate-400">
          {{ activeRecommendation.strategy_name || activeRecommendation.strategy_id }} · v{{ activeRecommendation.strategy_version }}
        </p>
      </div>
      <div class="text-right">
        <p class="text-sm text-slate-400">{{ recommendationStatusLabel(activeRecommendation.status) }}</p>
        <p class="text-xl font-semibold text-slate-100">质量评分 {{ activeRecommendation.quality_score }}</p>
      </div>
    </div>
    <div class="mt-4 grid gap-3 md:grid-cols-2">
      <article
        v-for="item in activeRecommendation.recommendations || []"
        :key="item.code"
        class="border border-slate-800 bg-slate-900/60 p-3 text-sm"
      >
        <p class="font-medium text-slate-100">{{ item.title }}</p>
        <p class="mt-1 text-slate-400">{{ item.description }}</p>
      </article>
    </div>
    <p class="mt-4 text-xs text-amber-200">策略变更仍需人工确认</p>
  </div>
</section>
```

- [ ] **Step 6: Run Task 4 frontend test**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-production-strategy-page.test.js --run
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/api/imageProduction.js web/src/views/ImageProductionStrategiesPage.vue web/src/__tests__/image-production-strategy-page.test.js
git commit -m "feat: show image strategy quality recommendations"
```

## Task 5: A/B Recommendation UI In Image Workbench

**Files:**

- Modify: `web/src/api/imageProduction.js`
- Modify: `web/src/views/ImageCreationPage.vue`
- Modify: `web/src/__tests__/image-creation-page.test.js`

- [ ] **Step 1: Add failing A/B recommendation UI tests**

In `web/src/__tests__/image-creation-page.test.js`, extend the image production API mock with:

```javascript
getImageAbWinnerRecommendation: mocks.getImageAbWinnerRecommendation,
```

Add `getImageAbWinnerRecommendation: vi.fn()` to the hoisted mocks.

Set the default in `beforeEach()`:

```javascript
api.getImageAbWinnerRecommendation.mockResolvedValue({
  data: {
    ok: true,
    winner_recommendation: {
      group_id: 'ab-group-1',
      eligible: true,
      recommended_attempt_id: 'attempt-a',
      confidence: 'medium',
      reason_code: 'RECOMMENDED_WINNER',
      reason: '推荐此方案进入人工确认',
      scores: [
        {
          attempt_id: 'attempt-a',
          score: 88,
          approved_asset_ready: true,
          status: 'completed',
          reasons: ['approved asset ready'],
        },
      ],
      automatic_adoption_allowed: false,
    },
  },
})
```

Append this test:

```javascript
it('shows ab winner recommendation but keeps manual winner action explicit', async () => {
  const wrapper = mountPage()
  await flushPromises()

  await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
  await flushPromises()

  wrapper.vm.abGroup = {
    id: 'ab-group-1',
    status: 'completed',
    attempts: [
      { id: 'attempt-a', status: 'completed', approved_asset_ready: true },
      { id: 'attempt-b', status: 'completed', approved_asset_ready: false },
    ],
  }
  await wrapper.vm.$nextTick()

  await wrapper.get('[data-testid="ab-load-recommendation"]').trigger('click')
  await flushPromises()

  expect(api.getImageAbWinnerRecommendation).toHaveBeenCalledWith('ab-group-1')
  expect(wrapper.text()).toContain('推荐胜出方案')
  expect(wrapper.text()).toContain('attempt-a')
  expect(wrapper.text()).toContain('仍需人工确认')
  expect(wrapper.find('[data-testid="ab-choose-winner-attempt-a"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run ImageCreationPage test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-page.test.js --run
```

Expected: FAIL because the A/B recommendation API wrapper and UI controls do not exist.

- [ ] **Step 3: Add A/B winner recommendation API wrapper**

In `web/src/api/imageProduction.js`, append:

```javascript
export function getImageAbWinnerRecommendation(groupId) {
  return client.get(`/image-production/ab-tests/${groupId}/winner-recommendation`)
}
```

- [ ] **Step 4: Add ImageCreationPage state and loader**

In `web/src/views/ImageCreationPage.vue`, extend the import from `../api/imageProduction.js`:

```javascript
import {
  chooseImageAbNoWinner,
  chooseImageAbWinner,
  createImageAbTest,
  getImageAbTest,
  getImageAbWinnerRecommendation,
  listImageProductionStrategies,
  previewImageAbTest,
  previewImageSelection,
  promoteImageAssetToVideo,
  refreshImageAbTest,
} from '../api/imageProduction.js'
```

Add these refs near existing A/B refs:

```javascript
const abWinnerRecommendation = ref(null)
const abRecommendationLoading = ref(false)
const abRecommendationError = ref('')
```

Add this function near existing A/B functions:

```javascript
async function loadAbWinnerRecommendation() {
  if (!abGroup.value?.id) return
  abRecommendationLoading.value = true
  abRecommendationError.value = ''
  abWinnerRecommendation.value = null
  try {
    const response = await getImageAbWinnerRecommendation(abGroup.value.id)
    abWinnerRecommendation.value = response?.data?.winner_recommendation || null
  } catch (e) {
    abRecommendationError.value = normalizeError(e)
  } finally {
    abRecommendationLoading.value = false
  }
}
```

In `refreshAbComparison()`, after assigning the refreshed group, clear stale recommendation state:

```javascript
abWinnerRecommendation.value = null
abRecommendationError.value = ''
```

- [ ] **Step 5: Add A/B recommendation UI**

Inside the A/B panel action area, below the existing refresh button, add:

```vue
<button
  v-if="abGroup?.id"
  type="button"
  data-testid="ab-load-recommendation"
  class="w-full border border-cyan-500/60 px-3 py-2 text-sm text-cyan-100 hover:bg-cyan-950 disabled:cursor-not-allowed disabled:opacity-50"
  :disabled="abRecommendationLoading"
  @click="loadAbWinnerRecommendation"
>
  {{ abRecommendationLoading ? '分析中' : '生成胜出建议' }}
</button>
```

Below the A/B status live block, add:

```vue
<div
  v-if="abWinnerRecommendation || abRecommendationError"
  data-testid="ab-winner-recommendation"
  class="border border-cyan-500/30 bg-cyan-950/20 p-3 text-sm"
>
  <p v-if="abRecommendationError" class="text-rose-300">{{ abRecommendationError }}</p>
  <div v-else-if="abWinnerRecommendation">
    <p class="font-medium text-cyan-100">推荐胜出方案</p>
    <p class="mt-1 text-slate-300">
      {{ abWinnerRecommendation.recommended_attempt_id || '暂无推荐' }}
    </p>
    <p class="mt-1 text-xs text-slate-400">{{ abWinnerRecommendation.reason }}</p>
    <p class="mt-2 text-xs text-amber-200">仍需人工确认</p>
  </div>
</div>
```

- [ ] **Step 6: Run Task 5 frontend test**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-page.test.js --run
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/api/imageProduction.js web/src/views/ImageCreationPage.vue web/src/__tests__/image-creation-page.test.js
git commit -m "feat: show ab winner recommendations"
```

## Task 6: Regression Verification And Plan Closure

**Files:**

- Verify only; no source files should be changed in this task.

- [ ] **Step 1: Run backend image production regression tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py tests/test_image_production_metrics_service.py tests/test_image_production_recommendation_service.py tests/test_image_production_recommendation_api.py tests/test_image_ab_service.py tests/test_image_ab_api.py tests/test_image_production_migration.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run image creation backend regression tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_api.py tests/test_image_creation_strategy_snapshot.py tests/test_image_selection_preview_service.py tests/test_image_production_strategy_service.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 3: Run frontend image production regression tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/image-production-strategy-page.test.js --run
```

Expected: PASS.

- [ ] **Step 4: Run placeholder scan for this plan**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
$patterns = @("T"+"BD", "TO"+"DO", "implement"+" later", "fill"+" in", "Add appropriate", "Write tests for the above", "Similar to Task")
rg -n ($patterns -join "|") docs/superpowers/plans/2026-05-30-image-production-strategy-control-plane-phase5-quality-feedback-loop.md
```

Expected: no output.

- [ ] **Step 5: Inspect worktree scope**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short server/app/services/image_production_metrics_service.py server/app/services/image_production_recommendation_service.py server/app/services/image_ab_test_service.py server/app/routers/image_production.py server/scripts/refresh_image_strategy_metrics.py server/tests/test_image_production_metrics_service.py server/tests/test_image_production_recommendation_service.py server/tests/test_image_production_recommendation_api.py server/tests/test_image_ab_api.py server/tests/test_image_ab_service.py web/src/api/imageProduction.js web/src/views/ImageProductionStrategiesPage.vue web/src/views/ImageCreationPage.vue web/src/__tests__/image-production-strategy-page.test.js web/src/__tests__/image-creation-page.test.js
```

Expected: only files intentionally touched by this plan are listed.

- [ ] **Step 6: Commit verification notes if test files changed during cleanup**

If Task 6 required a small source or test correction, commit it:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/image_production_metrics_service.py server/app/services/image_production_recommendation_service.py server/app/services/image_ab_test_service.py server/app/routers/image_production.py server/scripts/refresh_image_strategy_metrics.py server/tests/test_image_production_metrics_service.py server/tests/test_image_production_recommendation_service.py server/tests/test_image_production_recommendation_api.py server/tests/test_image_ab_api.py server/tests/test_image_ab_service.py web/src/api/imageProduction.js web/src/views/ImageProductionStrategiesPage.vue web/src/views/ImageCreationPage.vue web/src/__tests__/image-production-strategy-page.test.js web/src/__tests__/image-creation-page.test.js
git commit -m "test: verify image production feedback loop"
```

If Task 6 required no file changes, record the exact commands and PASS counts in the final implementation report.

## Product Acceptance Criteria

- Strategy Center can refresh pre-aggregated image strategy metrics without scanning tasks on page load.
- Strategy Center shows a human-readable recommendation for a strategy with score, confidence, status, reason cards, and an explicit note that strategy changes still require human approval.
- Image Workbench A/B panel can request a suggested winner after attempts finish.
- Suggested A/B winner does not automatically call the existing winner endpoint.
- Existing manual winner and no-winner flows remain unchanged.
- Backend recommendation APIs return deterministic payloads that tests can assert without live providers.
- No real provider calls are required for the regression suite.

## Self-Review

### Spec Coverage

- Human-approved strategy changes: covered by `automatic_mutation_allowed: false` and UI copy.
- Performance metrics: covered by aggregate metrics and refresh route.
- Recommended/cautious labels: covered by strategy recommendation status.
- A/B winner feedback: covered by A/B winner recommendation API and UI.
- Standalone analytics dashboard: intentionally kept outside this phase; compact panels satisfy the next operational need without a second analytics product.
- Provider-online E2E: intentionally kept outside this phase; tests remain deterministic and cost-free.

### Type Consistency

- Backend strategy recommendation function: `strategy_recommendation_payload(db, strategy_id)`.
- Backend A/B recommendation function: `ab_winner_recommendation_payload(db, group_id, user_id=None)`.
- Public A/B service wrapper: `recommend_ab_winner(db, group_id, user_id=None)`.
- Frontend strategy API wrapper: `getImageProductionStrategyRecommendations(strategyId)`.
- Frontend metrics API wrapper: `refreshImageProductionMetrics(payload = {})`.
- Frontend A/B API wrapper: `getImageAbWinnerRecommendation(groupId)`.

### Execution Recommendation

Use `superpowers:subagent-driven-development` for implementation. Task 1 should run first because Task 2 relies on aggregate metrics. Tasks 4 and 5 can be split across frontend subagents after Tasks 2 and 3 pass.
