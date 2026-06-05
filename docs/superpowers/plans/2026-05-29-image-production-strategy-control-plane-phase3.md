# Image Production Strategy Control Plane Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not create git commits unless the user explicitly asks; use `git status --short` and test evidence as checkpoints.

**Goal:** Add Phase 3 review gates, cost confirmation, capacity visibility, and reviewed image-to-video promotion on top of the completed Phase 2 explainability/fallback layer.

**Architecture:** Keep `POST /api/image-creation/tasks` as the authoritative execution path. Add a small policy runtime service that resolves review/cost/capacity policy snapshots from existing strategy policy references, use it in selection preview and task creation, and keep downstream video promotion blocked unless image assets pass the required review gate.

**Autoplan revision:** Product, design, engineering, and DX review found four issues that must be corrected before implementation: structured image errors currently cannot carry `details`/`rescue_actions`, task creation must resolve `model_config` before policy cost estimation, queued tasks must have a real manual dispatch path instead of a fake blocked endpoint, and the frontend must separate pre-submit risk, production status, and asset review instead of adding more fields into one overloaded panel.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Vitest, existing dy_auto API clients and Tailwind utility classes.

---

## Source Material

- Design spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-28-image-production-strategy-control-plane-design.md`
- Completed Phase 2 plan: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-28-image-production-strategy-control-plane-phase2.md`
- Existing policy table: `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- Existing selection preview service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_selection_preview_service.py`
- Existing image creation service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Existing image asset bridge: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_asset_bridge_service.py`
- Existing image creation UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Existing strategy center UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`

## Current State Assumption

Phase 2 is complete and verified:

- Selection preview returns selected model, rejected candidates, fallback candidates, warnings, and rescue actions.
- Task creation persists strategy snapshot, rich selection explanation, `fallback_trace_json`, and task timeline.
- Pixelle submit/sync failures leave visible failed tasks with fallback retry actions.
- Image creation trust rail shows explainability and fallback confirmation.
- Strategy center supports default/fallback model editing with optimistic version payloads.

This plan does not repeat Phase 1 or Phase 2 work.

## Scope

In scope for Phase 3:

- Review policy runtime from `ImageProductionPolicyVersion.snapshot_json`.
- Cost estimate beyond count-only local estimate.
- High-cost confirmation that is not silently auto-confirmed by the frontend.
- Capacity preview and admission using image task queue/lease fields already present on `ImageCreationTask`.
- Queue depth and estimated wait display in selection preview, task payload, and the image creation trust rail.
- Real manual dispatch for queued image tasks: re-check capacity, acquire a lease, submit to Pixelle, and persist provider task ids.
- Review gate metadata on generated image assets.
- Promotion to video asset only after the required gate passes.
- Review backlog and blocked asset rescue actions in the image creation UI.
- Image production cost event ledger for image tasks and assets.

Out of scope for Phase 3:

- A/B strategy groups, A/B attempts, and winner adoption. That belongs to Phase 4.
- Automatic strategy mutation from cost or review metrics.
- Fully autonomous fallback execution without human confirmation.
- A background worker daemon for queued image tasks. Phase 3 adds queue/admission state plus a real manual dispatch service; wiring that service to a scheduler can be done after this vertical slice.

## File Structure

### Backend

- Modify `server/app/services/image_creation_errors.py`
  - Adds structured `details` and `rescue_actions` support to image error payloads.
  - Keeps all existing call sites backward compatible.
- Create `server/app/services/image_production_policy_runtime.py`
  - Resolves cost, capacity, and review policy snapshots.
  - Produces cost/time/capacity/review gate previews.
  - Applies high-cost and capacity admission decisions.
- Create `server/app/services/image_production_cost_service.py`
  - Writes image task cost events and derives actual cost from provider responses.
- Create `server/app/services/image_review_gate_service.py`
  - Computes review gate state for generated assets and promotion.
  - Produces blocked asset rescue actions.
- Modify `server/app/db_models.py`
  - Add `ImageProductionCostEvent`.
- Create Alembic migration `server/alembic/versions/2b3c4d5e6f70_image_production_phase3_controls.py`
  - Adds `image_production_cost_events`.
- Modify `server/app/services/image_selection_preview_service.py`
  - Adds cost/time/capacity/review gate fields to preview responses.
- Modify `server/app/services/image_creation_service.py`
  - Uses Phase 3 policy runtime in task creation.
  - Stops relying on count-only `_estimate_cost`.
  - Records cost event and review gate metadata.
  - Adds `dispatch_queued_image_task` for real manual queue dispatch.
  - Surfaces capacity and review state in `task_payload` and `asset_payload`.
- Modify `server/app/services/image_asset_bridge_service.py`
  - Blocks promotion when review gate is not passed and returns rescue actions.
- Modify `server/app/routers/image_creation.py`
  - Adds queue dispatch endpoint that calls the real manual dispatch service.

### Frontend

- Modify `web/src/views/ImageCreationPage.vue`
  - Splits Phase 3 visibility into pre-submit risk, post-submit production state, and asset review cards.
  - Requires explicit high-cost confirmation before submit.
  - Applies the same cost-confirmation behavior to repaint/edit-again entry points.
  - Shows queue status in the task panel.
  - Shows review cards with approve/reject/repaint/promote actions.
- Modify `web/src/api/imageCreation.js`
  - Adds `dispatchQueuedImageTask`.
- Modify `web/src/api/imageProduction.js`
  - Existing `promoteImageAssetToVideo` remains the promotion API.
- Modify `web/src/__tests__/image-creation-page.test.js`
  - Adds high-cost confirmation, capacity state, review backlog, blocked promotion, and queue display tests.

## Naming Contract

Cost preview:

```json
{
  "amount": 2.5,
  "currency": "CNY",
  "estimate_source": "policy",
  "requires_confirmation": true,
  "confirmation_threshold": 2.0,
  "units": { "images": 2, "unit_cost": 1.25 }
}
```

Capacity preview:

```json
{
  "mode": "admission_control",
  "status": "available",
  "max_concurrent": 2,
  "active_count": 1,
  "queued_count": 0,
  "queue_depth": 0,
  "estimated_wait_seconds": 0,
  "admission_action": "submit_now"
}
```

Review gate preview:

```json
{
  "required": true,
  "manual_required": true,
  "ai_required": false,
  "status": "manual_review_pending",
  "policy_version_id": "policy-id",
  "reason": "image_to_video_input requires manual approval before video promotion"
}
```

Task creation blocked by capacity:

```json
{
  "ok": false,
  "error_code": "IMAGE_CAPACITY_BLOCKED",
  "repair_action": "Wait for capacity or enable queueing for this strategy.",
  "rescue_actions": [
    { "type": "wait_for_capacity", "label": "Wait and retry later." },
    { "type": "reduce_queue", "label": "Finish or cancel existing image tasks." }
  ],
  "capacity": { "status": "blocked" }
}
```

Task creation queued by capacity:

```json
{
  "ok": true,
  "task": {
    "status": "queued",
    "queue_job_id": "uuid",
    "pixelle_task_id": null,
    "capacity": { "status": "queued", "admission_action": "queue" }
  }
}
```

Image error extension:

```json
{
  "ok": false,
  "error_code": "IMAGE_REVIEW_GATE_BLOCKED",
  "message": "Image asset has not passed the required review gate.",
  "repair_action": "Approve the image asset or repaint it before promotion.",
  "retryable": false,
  "affected_ids": ["asset-id"],
  "details": { "review_gate": { "status": "manual_review_pending" } },
  "rescue_actions": [
    { "type": "manual_review_required", "label": "Approve or reject this image before video promotion." }
  ]
}
```

## Task 0: Align Structured Image Error Contract

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_errors.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_errors.py`

- [ ] **Step 1: Write failing tests for structured details and rescue actions**

Create `server/tests/test_image_creation_errors.py`:

```python
from app.services.image_creation_errors import image_error


def test_image_error_carries_details_and_rescue_actions():
    exc = image_error(
        409,
        "IMAGE_REVIEW_GATE_BLOCKED",
        "Blocked.",
        "Approve or repaint.",
        retryable=False,
        affected_ids=["asset-1"],
        details={"review_gate": {"status": "manual_review_pending"}},
        rescue_actions=[{"type": "manual_review_required", "label": "Approve asset."}],
    )

    assert exc.status_code == 409
    assert exc.detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert exc.detail["affected_ids"] == ["asset-1"]
    assert exc.detail["details"]["review_gate"]["status"] == "manual_review_pending"
    assert exc.detail["rescue_actions"][0]["type"] == "manual_review_required"


def test_image_error_keeps_existing_payload_shape():
    exc = image_error(400, "IMAGE_PROMPT_REQUIRED", "Prompt is required.", "Enter a prompt.")

    assert exc.detail["ok"] is False
    assert exc.detail["repair_route"] is None
    assert exc.detail["retryable"] is True
    assert exc.detail["affected_ids"] == []
    assert "details" not in exc.detail
    assert "rescue_actions" not in exc.detail
```

- [ ] **Step 2: Run error contract tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_errors.py -v
```

Expected: FAIL because `image_error` does not accept `details` or `rescue_actions`.

- [ ] **Step 3: Extend `image_error` without breaking existing call sites**

Modify `server/app/services/image_creation_errors.py`:

```python
from typing import Any

from fastapi import HTTPException


def image_error(
    status_code: int,
    error_code: str,
    message: str,
    repair_action: str,
    repair_route: str | None = None,
    retryable: bool = True,
    affected_ids: list[str] | None = None,
    details: dict[str, Any] | None = None,
    rescue_actions: list[dict[str, Any]] | None = None,
) -> HTTPException:
    payload: dict[str, Any] = {
        "ok": False,
        "error_code": error_code,
        "message": message,
        "repair_action": repair_action,
        "repair_route": repair_route,
        "retryable": retryable,
        "affected_ids": affected_ids or [],
    }
    if details:
        payload["details"] = details
    if rescue_actions:
        payload["rescue_actions"] = rescue_actions
    return HTTPException(status_code=status_code, detail=payload)
```

- [ ] **Step 4: Run error contract tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_errors.py -v
```

Expected: PASS.

## Task 1: Add Backend Policy Runtime

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_policy_runtime.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_policy_runtime.py`

- [ ] **Step 1: Write failing tests for cost, capacity, and review policy previews**

Create `server/tests/test_image_production_policy_runtime.py`:

```python
from app.db_models import ImageCreationTask, ImageProductionPolicyVersion, ImageProductionStrategy
from app.services.image_production_policy_runtime import (
    estimate_image_cost,
    preview_image_capacity,
    preview_review_gate,
)


def _policy(db, policy_type, snapshot):
    row = ImageProductionPolicyVersion(
        policy_type=policy_type,
        name=f"{policy_type}-phase3",
        version=1,
        snapshot_json=snapshot,
        status="active",
    )
    db.add(row)
    db.commit()
    return row


def _strategy(db, *, cost_policy=None, capacity_policy=None, review_policy=None):
    row = ImageProductionStrategy(
        slug="phase3-strategy",
        name="Phase 3 Strategy",
        destination_role="image_to_video_input",
        supported_modes_json=["text_to_image"],
        common_parameters_json={},
        provider_options_json={},
        fallback_model_ids_json=[],
        cost_policy_version_id=cost_policy.id if cost_policy else None,
        capacity_policy_version_id=capacity_policy.id if capacity_policy else None,
        review_policy_version_id=review_policy.id if review_policy else None,
        status="active",
        version=1,
    )
    db.add(row)
    db.commit()
    return row


def test_estimate_image_cost_uses_policy_threshold(db):
    cost_policy = _policy(db, "cost", {
        "unit_cost": 1.25,
        "currency": "CNY",
        "confirmation_threshold": 2.0,
        "latency_seconds_per_image": 8,
    })
    strategy = _strategy(db, cost_policy=cost_policy)

    result = estimate_image_cost(db, payload={"count": 2}, strategy=strategy, model_config={"provider": "mock"})

    assert result["amount"] == 2.5
    assert result["currency"] == "CNY"
    assert result["estimate_source"] == "policy"
    assert result["requires_confirmation"] is True
    assert result["confirmation_threshold"] == 2.0
    assert result["units"] == {"images": 2, "unit_cost": 1.25}
    assert result["policy_version_id"] == cost_policy.id
    assert result["time_estimate"] == {"estimated_seconds": 16, "estimate_source": "policy"}


def test_preview_image_capacity_counts_active_tasks(db):
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": True,
    })
    strategy = _strategy(db, capacity_policy=capacity_policy)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="busy",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id="model-1",
        capacity_lease_id="lease-running",
    ))
    db.commit()

    result = preview_image_capacity(db, strategy=strategy, model_id="model-1")

    assert result["status"] == "queued"
    assert result["active_count"] == 1
    assert result["queue_depth"] == 1
    assert result["estimated_wait_seconds"] == 30
    assert result["admission_action"] == "queue"


def test_preview_review_gate_requires_manual_for_video_input(db):
    review_policy = _policy(db, "review", {
        "manual_required_for": ["image_to_video_input"],
        "ai_required_for": ["character_anchor_image"],
    })
    strategy = _strategy(db, review_policy=review_policy)

    result = preview_review_gate(db, strategy=strategy, destination_role="image_to_video_input")

    assert result["required"] is True
    assert result["manual_required"] is True
    assert result["ai_required"] is False
    assert result["status"] == "manual_review_pending"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py -v
```

Expected: FAIL because `image_production_policy_runtime.py` does not exist.

- [ ] **Step 3: Implement policy runtime**

Create `server/app/services/image_production_policy_runtime.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db_models import ImageCreationTask, ImageProductionPolicyVersion, ImageProductionStrategy


DEFAULT_COST_POLICY = {
    "unit_cost": 1.0,
    "currency": "CNY",
    "confirmation_threshold": 1.0,
    "latency_seconds_per_image": 10,
}
DEFAULT_CAPACITY_POLICY = {
    "mode": "preview_only",
    "max_concurrent": 1,
    "average_task_seconds": 30,
    "queue_when_full": False,
}
DEFAULT_REVIEW_POLICY = {
    "manual_required_for": ["image_to_video_input"],
    "ai_required_for": [],
}


def _policy_snapshot(
    db: Session,
    policy_id: str | None,
    policy_type: str,
    default_snapshot: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    if not policy_id:
        return dict(default_snapshot), None
    row = (
        db.query(ImageProductionPolicyVersion)
        .filter(ImageProductionPolicyVersion.id == policy_id)
        .filter(ImageProductionPolicyVersion.policy_type == policy_type)
        .first()
    )
    if not row:
        return dict(default_snapshot), None
    snapshot = dict(default_snapshot)
    snapshot.update(row.snapshot_json or {})
    return snapshot, row.id


def _count_images(payload: dict[str, Any]) -> int:
    try:
        return max(1, int(payload.get("count") or 1))
    except (TypeError, ValueError):
        return 1


def estimate_image_cost(
    db: Session,
    *,
    payload: dict[str, Any],
    strategy: ImageProductionStrategy | None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy, policy_id = _policy_snapshot(
        db,
        strategy.cost_policy_version_id if strategy else None,
        "cost",
        DEFAULT_COST_POLICY,
    )
    model_cost = ((model_config or {}).get("config") or {}).get("cost_profile") or {}
    unit_cost = float(model_cost.get("unit_cost", policy.get("unit_cost", 1.0)))
    currency = str(model_cost.get("currency", policy.get("currency", "CNY")))
    count = _count_images(payload)
    amount = round(unit_cost * count, 4)
    threshold = float(policy.get("confirmation_threshold", 1.0))
    latency = int(policy.get("latency_seconds_per_image", 10)) * count
    return {
        "amount": amount,
        "currency": currency,
        "estimate_source": "policy",
        "requires_confirmation": amount > threshold,
        "confirmation_threshold": threshold,
        "units": {"images": count, "unit_cost": unit_cost},
        "policy_version_id": policy_id,
        "time_estimate": {"estimated_seconds": latency, "estimate_source": "policy"},
    }


def preview_image_capacity(
    db: Session,
    *,
    strategy: ImageProductionStrategy | None,
    model_id: str | None,
) -> dict[str, Any]:
    policy, policy_id = _policy_snapshot(
        db,
        strategy.capacity_policy_version_id if strategy else None,
        "capacity",
        DEFAULT_CAPACITY_POLICY,
    )
    max_concurrent = max(1, int(policy.get("max_concurrent") or 1))
    average_task_seconds = max(1, int(policy.get("average_task_seconds") or 30))
    query = db.query(ImageCreationTask).filter(ImageCreationTask.status.in_(["queued", "running"]))
    if strategy:
        query = query.filter(ImageCreationTask.strategy_id == strategy.id)
    if model_id:
        query = query.filter(ImageCreationTask.model_id == model_id)
    active_count = query.filter(ImageCreationTask.status == "running").count()
    queued_count = query.filter(ImageCreationTask.status == "queued").count()
    full = active_count >= max_concurrent
    queue_when_full = bool(policy.get("queue_when_full"))
    status = "available"
    admission_action = "submit_now"
    queue_depth = queued_count
    if full and queue_when_full:
        status = "queued"
        admission_action = "queue"
        queue_depth = queued_count + 1
    elif full:
        status = "blocked"
        admission_action = "block"
        queue_depth = queued_count
    return {
        "mode": policy.get("mode", "preview_only"),
        "status": status,
        "max_concurrent": max_concurrent,
        "active_count": active_count,
        "queued_count": queued_count,
        "queue_depth": queue_depth,
        "estimated_wait_seconds": queue_depth * average_task_seconds if status in {"queued", "blocked"} else 0,
        "admission_action": admission_action,
        "policy_version_id": policy_id,
    }


def preview_review_gate(
    db: Session,
    *,
    strategy: ImageProductionStrategy | None,
    destination_role: str | None,
) -> dict[str, Any]:
    policy, policy_id = _policy_snapshot(
        db,
        strategy.review_policy_version_id if strategy else None,
        "review",
        DEFAULT_REVIEW_POLICY,
    )
    role = destination_role or (strategy.destination_role if strategy else "")
    manual_required = role in set(policy.get("manual_required_for") or [])
    ai_required = role in set(policy.get("ai_required_for") or [])
    required = manual_required or ai_required
    if manual_required:
        status = "manual_review_pending"
    elif ai_required:
        status = "ai_review_pending"
    else:
        status = "not_required"
    return {
        "required": required,
        "manual_required": manual_required,
        "ai_required": ai_required,
        "status": status,
        "policy_version_id": policy_id,
        "reason": f"{role} requires review before video promotion" if required else "No review gate required for this role",
    }
```

- [ ] **Step 4: Run policy runtime tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py -v
```

Expected: PASS.

## Task 2: Add Cost Event Ledger

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_cost_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_cost_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\alembic\versions\2b3c4d5e6f70_image_production_phase3_controls.py`

- [ ] **Step 1: Write failing tests for estimate and actual cost events**

Create `server/tests/test_image_production_cost_service.py`:

```python
from app.db_models import ImageCreationTask, ImageProductionCostEvent
from app.services.image_production_cost_service import record_actual_cost_event, record_estimated_cost_event


def _task(db):
    row = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="cost task",
        count=2,
        target_count=2,
        provider="seedance",
        model_id="model-1",
        provider_task_id="provider-task-1",
        estimated_cost_json={"amount": 2.5, "currency": "CNY", "units": {"images": 2}},
    )
    db.add(row)
    db.commit()
    return row


def test_record_estimated_cost_event_is_idempotent(db):
    task = _task(db)

    first = record_estimated_cost_event(db, task)
    second = record_estimated_cost_event(db, task)

    assert first.id == second.id
    rows = db.query(ImageProductionCostEvent).filter(ImageProductionCostEvent.task_id == task.id).all()
    assert len(rows) == 1
    assert rows[0].event_type == "estimate"
    assert rows[0].estimated_cost == 2.5


def test_record_actual_cost_event_reads_provider_usage(db):
    task = _task(db)
    task.provider_task_id = "x" * 120
    task.provider_response_json = {"usage": {"actual_cost": 3.0, "currency": "CNY", "images": 2}}
    db.commit()

    event = record_actual_cost_event(db, task)

    assert event.event_type == "actual"
    assert event.actual_cost == 3.0
    assert event.units_json["images"] == 2
    assert len(event.event_key) > 160


def test_record_actual_cost_event_skips_when_usage_has_no_cost(db):
    task = _task(db)
    task.provider_response_json = {"usage": {"images": 2}}
    db.commit()

    assert record_actual_cost_event(db, task) is None
    assert db.query(ImageProductionCostEvent).filter(ImageProductionCostEvent.task_id == task.id).count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_cost_service.py -v
```

Expected: FAIL because `ImageProductionCostEvent` and service do not exist.

- [ ] **Step 3: Add SQLAlchemy model**

Modify `server/app/db_models.py` near image production models:

```python
class ImageProductionCostEvent(Base):
    __tablename__ = "image_production_cost_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_key = Column(String(220), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(String(36), ForeignKey("image_creation_assets.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(30), nullable=False)
    stage = Column(String(40), nullable=False, default="image_generation")
    strategy_id = Column(String(36), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    model_id = Column(String(120), nullable=True)
    provider = Column(String(80), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    estimate_source = Column(String(40), nullable=False, default="policy")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_image_cost_event_key"),
        Index("idx_image_cost_events_task", "task_id"),
        Index("idx_image_cost_events_event_type", "event_type"),
        Index("idx_image_cost_events_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_cost_events_created", "created_at"),
    )
```

- [ ] **Step 4: Add migration**

Create `server/alembic/versions/2b3c4d5e6f70_image_production_phase3_controls.py`:

```python
from alembic import op
import sqlalchemy as sa


revision = "2b3c4d5e6f70"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_production_cost_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=220), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False, server_default="image_generation"),
        sa.Column("strategy_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_version", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actual_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("units_json", sa.JSON(), nullable=True),
        sa.Column("estimate_source", sa.String(length=40), nullable=False, server_default="policy"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["image_creation_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["image_creation_assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_image_cost_event_key"),
    )
    op.create_index("idx_image_cost_events_task", "image_production_cost_events", ["task_id"])
    op.create_index("idx_image_cost_events_event_type", "image_production_cost_events", ["event_type"])
    op.create_index("idx_image_cost_events_strategy", "image_production_cost_events", ["strategy_id", "strategy_version"])
    op.create_index("idx_image_cost_events_created", "image_production_cost_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_image_cost_events_created", table_name="image_production_cost_events")
    op.drop_index("idx_image_cost_events_strategy", table_name="image_production_cost_events")
    op.drop_index("idx_image_cost_events_event_type", table_name="image_production_cost_events")
    op.drop_index("idx_image_cost_events_task", table_name="image_production_cost_events")
    op.drop_table("image_production_cost_events")
```

This plan uses current Alembic head `1a2b3c4d5e6f` as the down revision.

- [ ] **Step 5: Implement cost event service**

Create `server/app/services/image_production_cost_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db_models import ImageCreationTask, ImageProductionCostEvent


def _usage_from_provider_response(task: ImageCreationTask) -> dict[str, Any]:
    response = task.provider_response_json or {}
    usage = response.get("usage") if isinstance(response, dict) else {}
    if isinstance(usage, dict) and usage:
        return usage
    stored_usage = task.usage_json or {}
    return stored_usage if isinstance(stored_usage, dict) else {}


def _event_key(task: ImageCreationTask, event_type: str) -> str:
    if event_type == "actual":
        return f"{task.id}:actual:{task.provider_task_id or task.pixelle_task_id or 'current'}"
    return f"{task.id}:{event_type}"


def _existing(db: Session, event_key: str) -> ImageProductionCostEvent | None:
    return (
        db.query(ImageProductionCostEvent)
        .filter(ImageProductionCostEvent.event_key == event_key)
        .first()
    )


def record_estimated_cost_event(db: Session, task: ImageCreationTask) -> ImageProductionCostEvent:
    event_key = _event_key(task, "estimate")
    existing = _existing(db, event_key)
    if existing:
        return existing
    estimate = task.estimated_cost_json or {}
    event = ImageProductionCostEvent(
        event_key=event_key,
        task_id=task.id,
        event_type="estimate",
        stage="image_generation",
        strategy_id=task.strategy_id,
        strategy_version=task.strategy_version,
        model_id=task.model_id,
        provider=task.provider,
        provider_task_id=task.provider_task_id,
        estimated_cost=float(estimate.get("amount") or 0.0),
        actual_cost=0.0,
        currency=estimate.get("currency") or "CNY",
        units_json=estimate.get("units") or {},
        estimate_source=estimate.get("estimate_source") or "policy",
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing(db, event_key)
        if existing:
            return existing
        raise
    db.refresh(event)
    return event


def record_actual_cost_event(db: Session, task: ImageCreationTask) -> ImageProductionCostEvent | None:
    event_key = _event_key(task, "actual")
    existing = _existing(db, event_key)
    if existing:
        return existing
    usage = _usage_from_provider_response(task)
    actual_cost = usage.get("actual_cost") or usage.get("cost")
    if actual_cost is None:
        return None
    event = ImageProductionCostEvent(
        event_key=event_key,
        task_id=task.id,
        event_type="actual",
        stage="image_generation",
        strategy_id=task.strategy_id,
        strategy_version=task.strategy_version,
        model_id=task.model_id,
        provider=task.provider,
        provider_task_id=task.provider_task_id,
        estimated_cost=float((task.estimated_cost_json or {}).get("amount") or 0.0),
        actual_cost=float(actual_cost),
        currency=usage.get("currency") or (task.estimated_cost_json or {}).get("currency") or "CNY",
        units_json=usage,
        estimate_source=(task.estimated_cost_json or {}).get("estimate_source") or "policy",
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing(db, event_key)
        if existing:
            return existing
        raise
    db.refresh(event)
    return event
```

- [ ] **Step 6: Run cost service tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_cost_service.py -v
```

Expected: PASS.

## Task 3: Integrate Policy Runtime Into Preview And Task Creation

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_selection_preview_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_creation.py`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_selection_preview_service.py`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_strategy_snapshot.py`

- [ ] **Step 1: Add failing selection preview test for Phase 3 trust fields**

Append to `server/tests/test_image_selection_preview_service.py`:

```python
def test_selection_preview_returns_cost_capacity_and_review_gate(db):
    model = _seed_image_model(
        db,
        name="Phase3 Model",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    cost = ImageProductionPolicyVersion(
        policy_type="cost",
        name="phase3-cost",
        version=1,
        snapshot_json={"unit_cost": 2.0, "confirmation_threshold": 3.0, "latency_seconds_per_image": 5},
        status="active",
    )
    capacity = ImageProductionPolicyVersion(
        policy_type="capacity",
        name="phase3-capacity",
        version=1,
        snapshot_json={"mode": "admission_control", "max_concurrent": 1, "queue_when_full": True},
        status="active",
    )
    review = ImageProductionPolicyVersion(
        policy_type="review",
        name="phase3-review",
        version=1,
        snapshot_json={"manual_required_for": ["image_to_video_input"]},
        status="active",
    )
    db.add_all([cost, capacity, review])
    db.commit()
    strategy = _strategy(
        db,
        default_model_id=model.id,
        supported_modes=["text_to_image"],
        destination_role="image_to_video_input",
    )
    strategy.cost_policy_version_id = cost.id
    strategy.capacity_policy_version_id = capacity.id
    strategy.review_policy_version_id = review.id
    db.commit()

    result = create_selection_preview(db, {
        "mode": "text_to_image",
        "destination_role": "image_to_video_input",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 2,
        "provider_options": {},
    })

    assert result["cost_estimate"]["amount"] == 4.0
    assert result["cost_estimate"]["requires_confirmation"] is True
    assert result["time_estimate"]["estimated_seconds"] == 10
    assert result["capacity"]["status"] == "available"
    assert result["review_gate"]["manual_required"] is True
```

Add imports at the top if they do not already exist:

```python
from app.db_models import ImageCreationTask, ImageProductionPolicyVersion
```

- [ ] **Step 2: Run the new preview test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_selection_preview_service.py::test_selection_preview_returns_cost_capacity_and_review_gate -v
```

Expected: FAIL because preview does not expose `capacity`, `review_gate`, or policy-based cost/time.

- [ ] **Step 3: Integrate runtime fields into selection preview**

Modify `server/app/services/image_selection_preview_service.py`:

```python
from app.services.image_production_policy_runtime import (
    estimate_image_cost,
    preview_image_capacity,
    preview_review_gate,
)
```

After selected model is resolved, build:

```python
    cost_estimate = estimate_image_cost(
        db,
        payload=payload,
        strategy=strategy,
        model_config={"provider": selected.provider, "config": selected.config_json or {}},
    )
    capacity = preview_image_capacity(
        db,
        strategy=strategy,
        model_id=selected.id,
    )
    review_gate = preview_review_gate(
        db,
        strategy=strategy,
        destination_role=payload.get("destination_role") or (strategy.destination_role if strategy else None),
    )
```

Then response must include:

```python
        "cost_estimate": cost_estimate,
        "time_estimate": cost_estimate["time_estimate"],
        "capacity": capacity,
        "review_gate": review_gate,
```

For fallback-blocked responses, include conservative fields:

```python
            fallback_cost_estimate = estimate_image_cost(
                db,
                payload=payload,
                strategy=strategy,
                model_config=None,
            )
```

Then include:

```python
            "cost_estimate": fallback_cost_estimate,
            "capacity": preview_image_capacity(db, strategy=strategy, model_id=None),
            "review_gate": preview_review_gate(db, strategy=strategy, destination_role=payload.get("destination_role")),
            "time_estimate": fallback_cost_estimate["time_estimate"],
```

Remove the old local `_cost_estimate()` call path from fallback-blocked and successful preview responses so Phase 3 preview never returns count-only cost.

- [ ] **Step 4: Add failing task creation tests for high-cost confirmation and queued capacity**

Append to `server/tests/test_image_creation_strategy_snapshot.py`:

```python
def test_create_image_task_requires_explicit_high_cost_confirmation(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    cost = ImageProductionPolicyVersion(
        policy_type="cost",
        name="high-cost",
        version=1,
        snapshot_json={"unit_cost": 3.0, "confirmation_threshold": 2.0},
        status="active",
    )
    db.add(cost)
    db.commit()
    strategy.cost_policy_version_id = cost.id
    db.commit()

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run before cost confirmation")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "expensive image",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "provider_options": {"watermark": True},
        "cost_confirmation": False,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_COST_CONFIRMATION_REQUIRED"


def test_create_image_task_queues_when_capacity_full(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    capacity = ImageProductionPolicyVersion(
        policy_type="capacity",
        name="queue-capacity",
        version=1,
        snapshot_json={"mode": "admission_control", "max_concurrent": 1, "queue_when_full": True},
        status="active",
    )
    db.add(capacity)
    db.commit()
    strategy.capacity_policy_version_id = capacity.id
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="running",
        status="running",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=model.id,
        capacity_lease_id="lease-existing",
    ))
    db.commit()

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for queued task")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "queued image",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    task = resp.json()["task"]
    assert task["status"] == "queued"
    assert task["capacity"]["admission_action"] == "queue"
    assert task["pixelle_task_id"] is None


def test_create_image_task_blocks_when_capacity_full_without_queue(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    capacity = ImageProductionPolicyVersion(
        policy_type="capacity",
        name="block-capacity",
        version=1,
        snapshot_json={"mode": "admission_control", "max_concurrent": 1, "queue_when_full": False},
        status="active",
    )
    db.add(capacity)
    db.commit()
    strategy.capacity_policy_version_id = capacity.id
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="running",
        status="running",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=model.id,
        capacity_lease_id="lease-existing",
    ))
    db.commit()

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run when capacity blocks")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "blocked image",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_CAPACITY_BLOCKED"
    assert resp.json()["detail"]["details"]["capacity"]["admission_action"] == "block"


def test_dispatch_queued_image_task_submits_to_pixelle(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="queued dispatch",
        status="queued",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_scene_key="image_generation",
        model_scene="image_generation",
        model_id=model.id,
        queue_job_id="queue-job-1",
        request_json={"capacity": {"admission_action": "queue"}},
        pixelle_payload_json={
            "external_task_id": "external-queued",
            "mode": "text_to_image",
            "capability_key": "text_to_image",
            "output_mode": "single",
            "prompt": "queued dispatch",
            "negative_prompt": "",
            "source_image_url": "",
            "reference_images": [],
            "count": 1,
            "size": "",
            "output_format": "",
            "response_format": "",
            "provider_options": {"watermark": True},
            "context": {},
        },
    )
    db.add(task)
    db.commit()

    async def fake_submit(**kwargs):
        assert kwargs["mode"] == "text_to_image"
        return {"stage_task_id": "pixelle-dispatch-1"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post(f"/api/image-creation/tasks/{task.id}/dispatch")

    assert resp.status_code == 200
    payload = resp.json()["task"]
    assert payload["status"] == "running"
    assert payload["pixelle_task_id"] == "pixelle-dispatch-1"
    assert payload["queue_job_id"] is None


def test_dispatch_queued_image_task_requires_saved_pixelle_payload(db):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="queued dispatch without payload",
        status="queued",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_scene_key="image_generation",
        model_scene="image_generation",
        model_id=model.id,
        queue_job_id="queue-job-missing-payload",
        request_json={"capacity": {"admission_action": "queue"}},
        pixelle_payload_json={},
    )
    db.add(task)
    db.commit()

    resp = client.post(f"/api/image-creation/tasks/{task.id}/dispatch")

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "IMAGE_QUEUE_PAYLOAD_MISSING"
    assert detail["affected_ids"] == [task.id]


def test_create_image_task_rechecks_capacity_before_lease(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    calls = []

    def fake_capacity(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            return {"status": "available", "admission_action": "submit_now", "queue_depth": 0, "estimated_wait_seconds": 0}
        return {"status": "queued", "admission_action": "queue", "queue_depth": 1, "estimated_wait_seconds": 30}

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run after second capacity check queued the task")

    monkeypatch.setattr("app.services.image_creation_service.preview_image_capacity", fake_capacity)
    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "capacity recheck image",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    task = resp.json()["task"]
    assert len(calls) == 2
    assert task["status"] == "queued"
    assert task["queue_job_id"]
    assert task["capacity"]["admission_action"] == "queue"
```

Add imports:

```python
from app.db_models import ImageProductionPolicyVersion
```

- [ ] **Step 5: Run task creation tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_strategy_snapshot.py::test_create_image_task_requires_explicit_high_cost_confirmation tests/test_image_creation_strategy_snapshot.py::test_create_image_task_queues_when_capacity_full tests/test_image_creation_strategy_snapshot.py::test_create_image_task_blocks_when_capacity_full_without_queue tests/test_image_creation_strategy_snapshot.py::test_dispatch_queued_image_task_submits_to_pixelle tests/test_image_creation_strategy_snapshot.py::test_dispatch_queued_image_task_requires_saved_pixelle_payload tests/test_image_creation_strategy_snapshot.py::test_create_image_task_rechecks_capacity_before_lease -v
```

Expected: FAIL because task creation still uses count-only cost, submits even when capacity is full, and does not have real queued dispatch.

- [ ] **Step 6: Modify image task creation**

In `server/app/services/image_creation_service.py`, import:

```python
from app.services.image_production_cost_service import record_estimated_cost_event, record_actual_cost_event
from app.services.image_production_policy_runtime import estimate_image_cost, preview_image_capacity, preview_review_gate
```

Move the existing `resolve_image_model_for_capability(...)`, selection-explanation, provider-limit, provider-option, and selection-preview-resolution validation block so it runs before cost estimation. Phase 3 cost estimation may read model config cost metadata, so this order is required:

```python
    try:
        model_config = resolve_image_model_for_capability(db, scene_key, capability_key, payload.get("model_id"))
    except RuntimeModelConfigError as exc:
        raise image_error(
            400,
            "IMAGE_CAPABILITY_UNSUPPORTED",
            str(exc),
            "Choose a compatible model or change mode.",
            "/ai-config",
            retryable=False,
        ) from exc

    if selection_preview:
        selection_explanation = _selection_explanation_from_preview(selection_preview, selection_explanation)
    else:
        selection_explanation = _selection_explanation_from_resolution(
            db,
            fallback=selection_explanation,
            scene_key=scene_key,
            capability_key=capability_key,
            requested_model_id=requested_model_id,
            strategy=strategy,
        )
    if selection_explanation is not None:
        selection_explanation["selected_model_id"] = model_config.get("model_id")
        selection_explanation["resolved_scene_key"] = scene_key
        selection_explanation["resolved_capability_key"] = capability_key
    _validate_provider_limits(payload, model_config)

    provider_options = dict(payload.get("provider_options") or {})
    if payload.get("watermark") is not None:
        provider_options.setdefault("watermark", payload.get("watermark"))
    provider_options = _validate_provider_options(provider_options, model_config)
    _validate_selection_preview_resolution(
        payload,
        selection_preview,
        requested_model_id=requested_model_id,
        requested_destination_role=requested_destination_role,
        hash_payload=hash_payload,
        strategy=strategy,
        model_config=model_config,
        provider_options=provider_options,
    )
```

Then replace:

```python
    estimated_cost = _estimate_cost(payload)
```

with:

```python
    estimated_cost = estimate_image_cost(db, payload=payload, strategy=strategy, model_config=model_config)
```

Keep the existing confirmation shape, but now use the policy flag:

```python
    if estimated_cost.get("requires_confirmation") and not payload.get("cost_confirmation"):
        raise image_error(
            409,
            "IMAGE_COST_CONFIRMATION_REQUIRED",
            "Image request cost requires confirmation.",
            "Confirm the task cost or reduce count/options.",
            retryable=False,
            details={"cost_estimate": estimated_cost},
        )
```

Before creating the task, compute capacity/review state:

```python
    capacity = preview_image_capacity(db, strategy=strategy, model_id=model_config.get("model_id"))
    review_gate = preview_review_gate(
        db,
        strategy=strategy,
        destination_role=payload.get("destination_role"),
    )
```

If capacity policy blocks instead of queues, return HTTP 409 and do not persist a dead task:

```python
    if capacity["admission_action"] == "block":
        raise image_error(
            409,
            "IMAGE_CAPACITY_BLOCKED",
            "Image generation capacity is full.",
            "Wait for capacity or enable queueing for this strategy.",
            retryable=True,
            details={"capacity": capacity},
            rescue_actions=[
                {"type": "wait_for_capacity", "label": "Wait and retry later."},
                {"type": "reduce_queue", "label": "Finish or cancel existing image tasks."},
            ],
        )
```

Before assigning a submit-now `capacity_lease_id`, re-run capacity in the same DB session after pending writes are flushed. If that second check no longer returns `submit_now`, follow the latest decision (`queue` or `block`). Phase 3 does not introduce a distributed lock, but it must avoid a stale pre-flush decision inside one request.

Use an intermediate status so the current task does not count against itself during the second admission check:

```python
        status="admission_pending",
        capacity_lease_id=None,
        queue_job_id=None,
```

This replaces the current `status="queued"` assignment in the task constructor.

After `db.flush()`, re-run `preview_image_capacity(...)`. Then apply the latest decision:

```python
    capacity = preview_image_capacity(db, strategy=strategy, model_id=model_config.get("model_id"))
    task.request_json = {
        **(task.request_json or {}),
        "capacity": capacity,
        "review_gate": review_gate,
    }
    if capacity["admission_action"] == "block":
        db.rollback()
        raise image_error(
            409,
            "IMAGE_CAPACITY_BLOCKED",
            "Image generation capacity is full.",
            "Wait for capacity or enable queueing for this strategy.",
            retryable=True,
            details={"capacity": capacity},
            rescue_actions=[
                {"type": "wait_for_capacity", "label": "Wait and retry later."},
                {"type": "reduce_queue", "label": "Finish or cancel existing image tasks."},
            ],
        )
    if capacity["admission_action"] == "queue":
        task.status = "queued"
        task.queue_job_id = str(uuid.uuid4())
    else:
        task.status = "queued"
        task.capacity_lease_id = str(uuid.uuid4())
```

The submit-now task is still `queued` until Pixelle accepts it and the service changes it to `running`. The presence of `capacity_lease_id` distinguishes an admitted task from a waiting queued task.

When creating the task, add to JSON fields:

```python
        estimated_cost_json=estimated_cost,
        review_policy=review_gate.get("status"),
```

Add `uuid` import if missing:

```python
import uuid
```

Do not add a second post-flush capacity block later in the function; the re-check block above is the source of truth for `task.request_json`, `task.status`, `queue_job_id`, and `capacity_lease_id`.

After the durable task commit, record the estimate event before any queue return or Pixelle submit:

```python
    record_estimated_cost_event(db, task)
    if capacity["admission_action"] == "queue":
        return task
```

In `sync_image_task`, after task reaches complete statuses and before final commit:

```python
    record_actual_cost_event(db, task)
```

Update `task_payload` to expose:

```python
        "queue_job_id": task.queue_job_id,
        "capacity_lease_id": task.capacity_lease_id,
        "capacity": (task.request_json or {}).get("capacity") or {},
        "review_gate": (task.request_json or {}).get("review_gate") or {},
        "time_estimate": (task.estimated_cost_json or {}).get("time_estimate") or {},
```

- [ ] **Step 7: Add real manual dispatch service and endpoint for queued tasks**

In `server/app/services/image_creation_service.py`, add:

```python
async def dispatch_queued_image_task(db: Session, task_id: str) -> ImageCreationTask:
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()
    if not task:
        raise image_error(404, "IMAGE_TASK_NOT_FOUND", "Image creation task not found.", "Reload the task list.", retryable=False)
    if task.status != "queued" or task.pixelle_task_id:
        raise image_error(409, "IMAGE_TASK_NOT_DISPATCHABLE", "Only queued image tasks without provider task id can be dispatched.", "Reload the task.", retryable=False)

    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == task.strategy_id).first() if task.strategy_id else None
    try:
        model_config = resolve_image_model_for_capability(
            db,
            task.model_scene_key or task.model_scene or MODE_TO_SCENE_CAPABILITY.get(task.mode, ("image_generation", "", ""))[0],
            task.capability_key,
            task.model_id,
        )
    except RuntimeModelConfigError as exc:
        raise image_error(
            400,
            "IMAGE_CAPABILITY_UNSUPPORTED",
            str(exc),
            "Choose a compatible model or change mode.",
            "/ai-config",
            retryable=False,
            affected_ids=[task.id],
        ) from exc
    if not isinstance(task.pixelle_payload_json, dict) or not task.pixelle_payload_json:
        raise image_error(
            409,
            "IMAGE_QUEUE_PAYLOAD_MISSING",
            "Queued image task is missing its provider payload.",
            "Create a new image task from the same request.",
            retryable=False,
            affected_ids=[task.id],
        )
    capacity = preview_image_capacity(db, strategy=strategy, model_id=model_config.get("model_id"))
    task.request_json = {**(task.request_json or {}), "capacity": capacity}
    if capacity["admission_action"] != "submit_now":
        db.commit()
        db.refresh(task)
        return task

    pixelle_payload = dict(task.pixelle_payload_json or {})
    pixelle_payload.pop("model_config", None)
    task.capacity_lease_id = str(uuid.uuid4())
    task.queue_job_id = None
    db.commit()
    db.refresh(task)

    try:
        result = await submit_image_create(db=db, model_config=model_config, **pixelle_payload)
    except Exception as exc:
        safe_message = _redact_provider_error(exc)
        task.status = "failed"
        task.capacity_lease_id = None
        task.error_code = "PIXELLE_IMAGE_DISPATCH_FAILED"
        task.error_message = safe_message
        task.repair_action = "Open the task and retry with the suggested fallback model."
        task.fallback_trace_json = _fallback_trace(
            db,
            strategy=strategy,
            scene_key=task.model_scene_key or task.model_scene or "image_generation",
            capability_key=task.capability_key,
            error_code="PIXELLE_IMAGE_DISPATCH_FAILED",
            message=safe_message,
        )
        db.commit()
        raise image_error(
            502,
            "PIXELLE_IMAGE_DISPATCH_FAILED",
            "Pixelle image dispatch failed after the queued task snapshot was saved.",
            "Open the task and retry with the suggested fallback model.",
            retryable=True,
            affected_ids=[task.id],
        ) from exc

    task.provider_response_json = result
    task.pixelle_task_id = result.get("stage_task_id") or result.get("task_id") or result.get("id")
    task.provider_task_id = task.pixelle_task_id
    task.status = "running"
    db.commit()
    db.refresh(task)
    return task
```

In `server/app/routers/image_creation.py`, import `dispatch_queued_image_task` and add:

```python
@router.post("/tasks/{task_id}/dispatch")
async def dispatch_task(task_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    task = await dispatch_queued_image_task(db, task_id)
    return {"ok": True, "task": task_payload(task), "assets": []}
```

This endpoint is manual in Phase 3, not a hidden daemon. It must genuinely submit an admitted queued task to Pixelle, otherwise the UI must only offer refresh/status actions and not call it dispatch.

- [ ] **Step 8: Run backend preview and creation tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_selection_preview_service.py tests/test_image_creation_strategy_snapshot.py -v
```

Expected: PASS.

## Task 4: Add Review Gate Service And Strengthen Image-To-Video Bridge

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_review_gate_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_asset_bridge_service.py`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_asset_bridge.py`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_strategy_snapshot.py`

- [ ] **Step 1: Write failing review gate tests**

Append to `server/tests/test_image_asset_bridge.py`:

```python
def test_promote_blocks_manual_review_pending_asset(db):
    ctx = _video_run_context(db)
    task, asset = _image_asset_context(db, status="review_pending")
    asset.manual_review_status = "pending"
    asset.metadata_json = {
        "review_gate": {
            "required": True,
            "manual_required": True,
            "status": "manual_review_pending",
        }
    }
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        promote_image_asset_to_video_asset(db, asset.id, {
            "run_id": ctx["run"].id,
            "frame_id": "frame-1",
            "user_id": ctx["user_id"],
        })

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert exc_info.value.detail["rescue_actions"][0]["type"] == "manual_review_required"


def test_promote_blocks_ai_review_pending_asset_even_when_manual_approved(db):
    ctx = _video_run_context(db)
    task, asset = _image_asset_context(db, status="approved")
    asset.manual_review_status = "approved"
    asset.audit_status = "pending"
    asset.metadata_json = {
        "review_gate": {
            "required": True,
            "manual_required": True,
            "ai_required": True,
            "status": "ai_review_pending",
        }
    }
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        promote_image_asset_to_video_asset(db, asset.id, {
            "run_id": ctx["run"].id,
            "frame_id": "frame-1",
            "user_id": ctx["user_id"],
        })

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"


def test_asset_payload_promote_action_requires_video_target(db):
    task, asset = _image_asset_context(db, status="approved")
    asset.manual_review_status = "approved"
    asset.audit_status = "approved"
    asset.metadata_json = {"review_gate": {"required": True, "manual_required": True, "status": "approved"}}
    asset.destination_context_json = {}
    db.commit()

    payload = asset_payload(asset)

    assert "promote_to_video_asset" not in payload["allowed_actions"]

    asset.destination_context_json = {"video_run_id": "run-1", "frame_id": "frame-1"}
    db.commit()

    payload = asset_payload(asset)

    assert "promote_to_video_asset" in payload["allowed_actions"]
```

Use the existing helper names in `test_image_asset_bridge.py`. If the helper names differ, adapt only the helper call site; keep the assertion contract unchanged. Import `asset_payload` from `app.services.image_creation_service` if this test file does not already import it.

- [ ] **Step 2: Run bridge test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_asset_bridge.py::test_promote_blocks_manual_review_pending_asset -v
```

Expected: FAIL because bridge only checks `asset.status == "approved"` and does not return structured rescue actions.

- [ ] **Step 3: Implement review gate service**

Create `server/app/services/image_review_gate_service.py`:

```python
from __future__ import annotations

from typing import Any

from app.db_models import ImageCreationAsset, ImageCreationTask


def asset_review_gate(task: ImageCreationTask | None, asset: ImageCreationAsset) -> dict[str, Any]:
    gate = {}
    if task and isinstance(task.request_json, dict):
        gate = dict(task.request_json.get("review_gate") or {})
    gate.update((asset.metadata_json or {}).get("review_gate") or {})
    if not gate:
        gate = {
            "required": asset.destination_role == "image_to_video_input",
            "manual_required": asset.destination_role == "image_to_video_input",
            "ai_required": False,
            "status": "manual_review_pending" if asset.destination_role == "image_to_video_input" else "not_required",
        }
    manual_ok = not gate.get("manual_required") or asset.manual_review_status == "approved"
    ai_ok = not gate.get("ai_required") or asset.audit_status == "approved"
    if asset.status == "approved" and manual_ok and ai_ok:
        gate["status"] = "approved"
    elif asset.status in {"rejected", "blocked"}:
        gate["status"] = "blocked"
    return gate


def review_gate_passed(task: ImageCreationTask | None, asset: ImageCreationAsset) -> bool:
    gate = asset_review_gate(task, asset)
    if not gate.get("required"):
        return True
    if gate.get("manual_required") and asset.manual_review_status != "approved":
        return False
    if gate.get("ai_required") and asset.audit_status != "approved":
        return False
    return asset.status == "approved" and gate.get("status") == "approved"


def review_gate_rescue_actions(asset: ImageCreationAsset) -> list[dict[str, Any]]:
    return [
        {
            "type": "manual_review_required",
            "label": "Approve or reject this image before video promotion.",
            "asset_id": asset.id,
        },
        {
            "type": "repaint_image",
            "label": "Create a corrected image from this asset.",
            "asset_id": asset.id,
        },
    ]
```

- [ ] **Step 4: Persist review gate metadata on generated assets**

Modify `_persist_stage_asset` in `server/app/services/image_creation_service.py` before `db.add(ImageCreationAsset(...))`:

```python
    review_gate = (task.request_json or {}).get("review_gate") or {}
    asset_status = "review_pending" if review_gate.get("required") else "approved"
    metadata = {
        **(item.get("metadata") or {}),
        "review_gate": review_gate,
        "strategy_snapshot": task.strategy_snapshot_json or {},
        "selection_explanation": task.selection_explanation_json or {},
    }
```

Then use:

```python
        status=asset_status,
        audit_status=review_gate.get("status"),
        manual_review_status="pending" if review_gate.get("manual_required") else None,
        metadata_json=metadata,
```

Update `asset_payload` to include:

```python
        "review_gate": (asset.metadata_json or {}).get("review_gate") or {},
        "allowed_actions": _asset_allowed_actions(asset),
```

Add helper near `asset_payload`:

```python
def _asset_allowed_actions(asset: ImageCreationAsset) -> list[str]:
    actions = ["copy_as_new_task"]
    if asset.status in {"review_pending", "manual_review_pending"}:
        actions.extend(["approve", "reject", "repaint"])
    context = asset.destination_context_json or {}
    has_video_target = bool((context.get("video_run_id") or context.get("run_id")) and context.get("frame_id"))
    if asset.status == "approved" and has_video_target:
        actions.append("promote_to_video_asset")
    if asset.status in {"rejected", "blocked"}:
        actions.append("repaint")
    return actions
```

If an approved asset has no `video_run_id`/`run_id` plus `frame_id` in `destination_context_json`, do not expose `promote_to_video_asset`; the Phase 3 UI has no frame picker and must not guess a video target.

Update `review_image_asset` so human review changes gate metadata consistently:

```python
    metadata = dict(asset.metadata_json or {})
    gate = dict(metadata.get("review_gate") or {})
    if action == "approve":
        asset.manual_review_status = "approved"
        if gate.get("ai_required") and asset.audit_status != "approved":
            asset.status = "review_pending"
            gate["status"] = "ai_review_pending"
        else:
            asset.status = "approved"
            if not gate.get("ai_required"):
                asset.audit_status = "approved"
            else:
                asset.audit_status = asset.audit_status or "approved"
            gate["status"] = "approved"
    else:
        asset.status = "rejected"
        asset.audit_status = "rejected"
        asset.manual_review_status = "rejected"
        gate["status"] = "blocked"
    metadata["review_gate"] = gate
    asset.metadata_json = metadata
```

Do not leave the old unconditional `asset.audit_status = asset.status` assignment in place, because it makes human approval accidentally satisfy an AI-required gate.

- [ ] **Step 5: Strengthen bridge promotion gate**

Modify `server/app/services/image_asset_bridge_service.py`:

```python
from app.services.image_review_gate_service import asset_review_gate, review_gate_passed, review_gate_rescue_actions
```

Replace the current `asset.status != "approved"` block with:

```python
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == asset.task_id).first()
    if not review_gate_passed(task, asset):
        raise image_error(
            409,
            "IMAGE_REVIEW_GATE_BLOCKED",
            "Image asset has not passed the required review gate.",
            "Approve the image asset or repaint it before promotion.",
            retryable=False,
            affected_ids=[asset.id],
            rescue_actions=review_gate_rescue_actions(asset),
            details={"review_gate": asset_review_gate(task, asset)},
        )
```

Remove the later duplicate task lookup if the function already has `task`.

- [ ] **Step 6: Run bridge and creation tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_asset_bridge.py tests/test_image_creation_strategy_snapshot.py -v
```

Expected: PASS.

## Task 5: Add Frontend Phase 3 Trust Rail And Review Cards

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\api\imageCreation.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-page.test.js`

- [ ] **Step 1: Add failing frontend tests for high-cost confirmation and capacity/review display**

Append to `web/src/__tests__/image-creation-page.test.js`:

```javascript
it('requires explicit high-cost confirmation before submitting', async () => {
  mocks.previewImageSelection.mockResolvedValueOnce({
    data: {
      selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
      selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
      cost_estimate: {
        amount: 4,
        currency: 'CNY',
        requires_confirmation: true,
        confirmation_threshold: 3,
      },
      time_estimate: { estimated_seconds: 20 },
      capacity: { status: 'available', queue_depth: 0, estimated_wait_seconds: 0 },
      review_gate: { manual_required: true, status: 'manual_review_pending' },
      selection_preview_id: 'preview-high-cost',
      request_hash: 'hash-high-cost',
    },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像')
  await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
  await flushPromises()

  expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('4 CNY')
  expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('预计 20 秒')
  expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('需要人工确认成本')
  expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()

  await wrapper.get('[data-testid="confirm-image-cost"]').trigger('click')
  await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
  await flushPromises()

  expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
    cost_confirmation: true,
  }))
})

it('shows queued capacity state from selection preview', async () => {
  mocks.previewImageSelection.mockResolvedValueOnce({
    data: {
      selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
      selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
      cost_estimate: { amount: 1, currency: 'CNY', requires_confirmation: false },
      time_estimate: { estimated_seconds: 10 },
      capacity: {
        status: 'queued',
        queue_depth: 3,
        estimated_wait_seconds: 90,
        admission_action: 'queue',
      },
      review_gate: { manual_required: false, status: 'not_required' },
      selection_preview_id: 'preview-queue',
      request_hash: 'hash-queue',
    },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('排队图像')
  await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
  await flushPromises()

  const rail = wrapper.get('[data-testid="image-trust-rail"]')
  expect(rail.text()).toContain('将进入队列')
  expect(rail.text()).toContain('前方 3 个任务')
  expect(rail.text()).toContain('预计等待 90 秒')
})

it('resets high-cost confirmation when the request changes', async () => {
  mocks.previewImageSelection.mockResolvedValueOnce({
    data: {
      selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
      selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
      cost_estimate: { amount: 4, currency: 'CNY', requires_confirmation: true, confirmation_threshold: 3 },
      time_estimate: { estimated_seconds: 20 },
      capacity: { status: 'available' },
      review_gate: { manual_required: true, status: 'manual_review_pending' },
      selection_preview_id: 'preview-high-cost',
      request_hash: 'hash-high-cost',
    },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像')
  await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
  await flushPromises()
  await wrapper.get('[data-testid="confirm-image-cost"]').trigger('click')
  await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像已修改')
  await flushPromises()

  expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
})

it('shows asset actions from allowed_actions and promotes approved assets', async () => {
  mocks.getImageTask.mockResolvedValueOnce({
    data: {
      task: { id: 'task-1', status: 'completed' },
      assets: [
        {
          id: 'asset-approved',
          url: 'https://img.example/a.png',
          status: 'approved',
          version: 1,
          allowed_actions: ['promote_to_video_asset', 'copy_as_new_task'],
          review_gate: { status: 'approved' },
          destination_context: { video_run_id: 'run-1', frame_id: 'frame-1' },
        },
        {
          id: 'asset-pending',
          url: 'https://img.example/b.png',
          status: 'review_pending',
          version: 1,
          allowed_actions: ['approve', 'reject', 'repaint'],
          review_gate: { status: 'manual_review_pending' },
        },
      ],
    },
  })
  mocks.promoteImageAssetToVideo.mockResolvedValueOnce({ data: { ok: true } })
  const wrapper = await mountPage()

  await loadTask(wrapper, 'task-1')
  await flushPromises()

  expect(wrapper.find('[data-testid="promote-asset-asset-approved"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="promote-asset-asset-pending"]').exists()).toBe(false)

  await wrapper.get('[data-testid="promote-asset-asset-approved"]').trigger('click')
  await flushPromises()

  expect(mocks.promoteImageAssetToVideo).toHaveBeenCalledWith('asset-approved', expect.objectContaining({
    run_id: 'run-1',
    frame_id: 'frame-1',
  }))
})

it('does not show promote action when approved asset has no video target', async () => {
  mocks.getImageTask.mockResolvedValueOnce({
    data: {
      task: { id: 'task-1', status: 'completed' },
      assets: [
        {
          id: 'asset-approved-no-target',
          url: 'https://img.example/a.png',
          status: 'approved',
          version: 1,
          allowed_actions: ['copy_as_new_task'],
          review_gate: { status: 'approved' },
          destination_context: {},
        },
      ],
    },
  })
  const wrapper = await mountPage()

  await loadTask(wrapper, 'task-1')
  await flushPromises()

  expect(wrapper.find('[data-testid="promote-asset-asset-approved-no-target"]').exists()).toBe(false)
})

it('does not silently confirm cost for repaint/edit-again requests', async () => {
  const wrapper = await mountPage()
  await wrapper.get('[data-testid="edit-asset-asset-1"]').trigger('click')
  await flushPromises()

  expect(mocks.editImageAsset).toHaveBeenCalledWith('asset-1', expect.objectContaining({
    cost_confirmation: false,
  }))
})

it('shows review backlog counts and empty state per filter', async () => {
  mocks.getImageTask.mockResolvedValueOnce({
    data: {
      task: { id: 'task-1', status: 'completed' },
      assets: [
        { id: 'asset-pending', url: 'https://img.example/b.png', status: 'review_pending', version: 1, allowed_actions: ['approve', 'reject', 'repaint'], review_gate: { status: 'manual_review_pending' } },
      ],
    },
  })
  const wrapper = await mountPage()

  await loadTask(wrapper, 'task-1')
  await flushPromises()

  expect(wrapper.get('[data-testid="review-filter-needs_review"]').text()).toContain('1')
  expect(wrapper.get('[data-testid="review-filter-approved"]').text()).toContain('0')

  await wrapper.get('[data-testid="review-filter-approved"]').trigger('click')
  await flushPromises()

  expect(wrapper.get('[data-testid="image-review-empty-state"]').text()).toContain('当前没有已通过资产')
})

it('shows queued task status before manual dispatch', async () => {
  mocks.getImageTask.mockResolvedValueOnce({
    data: {
      task: {
        id: 'queued-task',
        status: 'queued',
        queue_job_id: 'queue-1',
        pixelle_task_id: null,
        capacity: { status: 'queued', queue_depth: 2, estimated_wait_seconds: 60 },
      },
      assets: [],
    },
  })
  const wrapper = await mountPage()

  await loadTask(wrapper, 'queued-task')
  await flushPromises()

  expect(wrapper.get('[data-testid="image-queue-status"]').text()).toContain('前方 2 个任务')
  expect(wrapper.get('[data-testid="dispatch-queued-image-task"]').text()).toContain('手动调度')
})
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js
```

Expected: FAIL because cost confirmation button and capacity/review display do not exist.

- [ ] **Step 3: Add API client for queued dispatch**

Modify `web/src/api/imageCreation.js`:

```javascript
export function dispatchQueuedImageTask(taskId) {
  return client.post(`/image-creation/tasks/${taskId}/dispatch`)
}
```

Keep using the existing `promoteImageAssetToVideo` API from `web/src/api/imageProduction.js`; do not duplicate this API in `imageCreation.js`.

- [ ] **Step 4: Update ImageCreationPage state**

In `web/src/views/ImageCreationPage.vue`, import the new API:

```javascript
  dispatchQueuedImageTask,
```

Also import the bridge API:

```javascript
import { promoteImageAssetToVideo } from '../api/imageProduction.js'
```

Add state:

```javascript
const costConfirmed = ref(false)
const reviewAssetFilter = ref('needs_review')
```

Add computed values:

```javascript
const previewCapacity = computed(() => selectionPreview.value?.capacity || {})
const previewReviewGate = computed(() => selectionPreview.value?.review_gate || {})
const previewTimeEstimate = computed(() => selectionPreview.value?.time_estimate || {})
const costConfirmationRequired = computed(() => Boolean(selectionPreview.value?.cost_estimate?.requires_confirmation && !costConfirmed.value))
const costEstimateLabel = computed(() => {
  const cost = selectionPreview.value?.cost_estimate
  if (!cost) return '-'
  return `${cost.amount ?? 0} ${cost.currency || 'CNY'}`
})
const capacityStatusLabel = computed(() => {
  if (previewCapacity.value.status === 'queued') return `将进入队列，前方 ${previewCapacity.value.queue_depth || 0} 个任务`
  if (previewCapacity.value.status === 'blocked') return '当前产能已满'
  return '可立即提交'
})
const selectedModelLabel = computed(() => selectionPreview.value?.selected_model?.name || '尚未选择模型')
const strategyVersionLabel = computed(() => {
  const strategy = selectionPreview.value?.strategy
  if (!strategy) return '未绑定图像策略'
  return `${strategy.name || '图像策略'} v${strategy.version || 1}`
})
const activeFilterClass = 'border border-cyan-400 bg-cyan-950/40 px-3 py-1 text-xs text-cyan-50'
const idleFilterClass = 'border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-900'
const assetReviewCounts = computed(() => ({
  needs_review: assets.value.filter(asset => ['review_pending', 'manual_review_pending'].includes(asset.status)).length,
  approved: assets.value.filter(asset => asset.status === 'approved').length,
  blocked: assets.value.filter(asset => ['blocked', 'rejected'].includes(asset.status)).length,
  all: assets.value.length,
}))
const reviewGateLabel = computed(() => {
  if (previewReviewGate.value.manual_required) return '需要人工审查'
  if (previewReviewGate.value.ai_required) return '需要 AI 审查'
  return '无需额外审查'
})
const timeEstimateLabel = computed(() => {
  const seconds = previewTimeEstimate.value.estimated_seconds
  return seconds ? `预计 ${seconds} 秒` : '-'
})
```

Update `canSubmit`:

```javascript
const canSubmit = computed(() => Boolean(form.prompt.trim())
  && !sourceError.value
  && !referenceError.value
  && !countError.value
  && !previewBlocked.value
  && !costConfirmationRequired.value)
```

Update `createDisabledReason`:

```javascript
  if (costConfirmationRequired.value) return '当前预计成本较高，需要先确认成本后才能创建任务。'
```

Update `buildPayload` so cost confirmation is no longer always true:

```javascript
    cost_confirmation: costConfirmed.value,
```

Update `editAgain` so repaint/edit requests do not bypass cost gates:

```javascript
      cost_confirmation: false,
```

If the edit endpoint returns `IMAGE_COST_CONFIRMATION_REQUIRED`, surface the normalized error in the same error area and leave the user in the workbench so they can preview/confirm before resubmitting. Do not silently retry with `cost_confirmation: true`.

Reset confirmation when preview changes:

```javascript
function resetSelectionPreview() {
  selectionPreviewRequestToken.value += 1
  selectionPreview.value = null
  costConfirmed.value = false
  previewError.value = ''
  previewLoading.value = false
}
```

- [ ] **Step 5: Split trust rail into clear Phase 3 groups**

Do not keep appending unrelated fields to one summary grid. The right panel should read in this order:

1. `提交前检查` - cost, time, capacity admission, high-cost confirmation.
2. `生产路径` - selected model, strategy version, queue depth/wait, fallback state.
3. `审查门禁` - manual/AI gate requirements and whether video promotion will be blocked.

Inside `data-testid="image-trust-rail"`, add grouped markup similar to:

```html
<div class="grid gap-3">
  <section class="border border-slate-800 bg-slate-950/50 p-3">
    <p class="text-xs font-semibold text-slate-300">提交前检查</p>
    <dl class="mt-3 grid gap-2 text-xs">
      <div class="flex items-center justify-between gap-3">
        <dt class="text-slate-500">预计成本</dt>
        <dd class="text-slate-100">{{ costEstimateLabel }}</dd>
      </div>
      <div class="flex items-center justify-between gap-3">
        <dt class="text-slate-500">预计耗时</dt>
        <dd class="text-slate-100">{{ timeEstimateLabel }}</dd>
      </div>
      <div class="flex items-center justify-between gap-3">
        <dt class="text-slate-500">产能</dt>
        <dd class="text-slate-100">{{ capacityStatusLabel }}</dd>
      </div>
    </dl>
    <p v-if="previewCapacity.estimated_wait_seconds" class="mt-2 text-xs text-slate-400">
      预计等待 {{ previewCapacity.estimated_wait_seconds }} 秒
    </p>
  </section>

  <section class="border border-slate-800 bg-slate-950/50 p-3">
    <p class="text-xs font-semibold text-slate-300">生产路径</p>
    <p class="mt-2 text-xs text-slate-400">{{ selectedModelLabel }}</p>
    <p class="mt-1 text-xs text-slate-400">{{ strategyVersionLabel }}</p>
  </section>

  <section class="border border-slate-800 bg-slate-950/50 p-3">
    <p class="text-xs font-semibold text-slate-300">审查门禁</p>
    <p class="mt-2 text-xs text-slate-100">{{ reviewGateLabel }}</p>
    <p v-if="previewReviewGate.required" class="mt-1 text-xs text-slate-400">
      生成后必须通过对应审查，才能推广到视频生产。
    </p>
  </section>
</div>
```

Place high-cost confirmation immediately above or next to the main submit CTA, not only deep inside the side panel. On mobile widths, keep this block directly below the header action area so the operator never has to scroll to understand why submit is disabled:

```html
<div
  v-if="selectionPreview?.cost_estimate?.requires_confirmation"
  data-testid="image-submit-confirmation"
  class="border border-amber-500/40 bg-amber-950/30 p-3"
>
  <p class="text-amber-100">当前预计成本较高，需要人工确认成本。</p>
  <p class="mt-1 text-xs text-amber-200">
    阈值 {{ selectionPreview.cost_estimate.confirmation_threshold }} {{ selectionPreview.cost_estimate.currency || 'CNY' }}
  </p>
  <button
    type="button"
    data-testid="confirm-image-cost"
    class="mt-3 min-h-11 border border-amber-300/70 px-3 py-2 text-xs text-amber-50 hover:bg-amber-900/50"
    @click="costConfirmed = true"
  >
    {{ costConfirmed ? '已确认成本' : '确认成本并创建任务' }}
  </button>
</div>
```

- [ ] **Step 6: Add review backlog, action-gated asset cards, promotion, and queue dispatch**

Add a compact backlog filter above the asset grid:

```html
<div class="flex flex-wrap gap-2" data-testid="image-review-backlog-filter">
  <button
    type="button"
    data-testid="review-filter-needs_review"
    :aria-pressed="reviewAssetFilter === 'needs_review'"
    :class="reviewAssetFilter === 'needs_review' ? activeFilterClass : idleFilterClass"
    @click="reviewAssetFilter = 'needs_review'"
  >
    待审 {{ assetReviewCounts.needs_review }}
  </button>
  <button
    type="button"
    data-testid="review-filter-approved"
    :aria-pressed="reviewAssetFilter === 'approved'"
    :class="reviewAssetFilter === 'approved' ? activeFilterClass : idleFilterClass"
    @click="reviewAssetFilter = 'approved'"
  >
    已通过 {{ assetReviewCounts.approved }}
  </button>
  <button
    type="button"
    data-testid="review-filter-blocked"
    :aria-pressed="reviewAssetFilter === 'blocked'"
    :class="reviewAssetFilter === 'blocked' ? activeFilterClass : idleFilterClass"
    @click="reviewAssetFilter = 'blocked'"
  >
    阻断/驳回 {{ assetReviewCounts.blocked }}
  </button>
  <button
    type="button"
    data-testid="review-filter-all"
    :aria-pressed="reviewAssetFilter === 'all'"
    :class="reviewAssetFilter === 'all' ? activeFilterClass : idleFilterClass"
    @click="reviewAssetFilter = 'all'"
  >
    全部 {{ assetReviewCounts.all }}
  </button>
</div>
```

Drive the displayed grid from `filteredAssets`, not raw `assets`:

```javascript
const filteredAssets = computed(() => {
  if (reviewAssetFilter.value === 'all') return assets.value
  if (reviewAssetFilter.value === 'approved') return assets.value.filter(asset => asset.status === 'approved')
  if (reviewAssetFilter.value === 'blocked') return assets.value.filter(asset => ['blocked', 'rejected'].includes(asset.status))
  return assets.value.filter(asset => ['review_pending', 'manual_review_pending'].includes(asset.status))
})

function assetAllowed(asset, action) {
  return Array.isArray(asset.allowed_actions) && asset.allowed_actions.includes(action)
}

const reviewAssetFilterLabel = computed(() => {
  if (reviewAssetFilter.value === 'approved') return '已通过'
  if (reviewAssetFilter.value === 'blocked') return '阻断或驳回'
  if (reviewAssetFilter.value === 'all') return ''
  return '待审'
})
```

Update the asset grid:

```html
<div
  v-for="asset in filteredAssets"
  :key="asset.id || asset.url || asset.image_url"
>
  ...
</div>
```

Add a filtered empty state, not only the current global empty state:

```html
<div
  v-if="assets.length && filteredAssets.length === 0"
  data-testid="image-review-empty-state"
  class="py-10 text-center text-sm text-slate-500"
>
  当前没有{{ reviewAssetFilterLabel }}资产。
</div>
```

In the asset card body, show gate state and render buttons from `allowed_actions`:

```html
<p v-if="asset.review_gate?.status" class="mt-2 text-xs text-slate-400">
  审查状态：{{ assetReviewGateLabel(asset.review_gate) }}
</p>

<div v-if="asset.id" class="mt-3 grid grid-cols-2 gap-2">
  <button
    v-if="assetAllowed(asset, 'approve')"
    type="button"
    :data-testid="`approve-asset-${asset.id}`"
    class="border border-emerald-500/70 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-950"
    @click="reviewAsset(asset, 'approve')"
  >
    通过
  </button>
  <button
    v-if="assetAllowed(asset, 'reject')"
    type="button"
    :data-testid="`reject-asset-${asset.id}`"
    class="border border-rose-500/70 px-2 py-1 text-xs text-rose-100 hover:bg-rose-950"
    @click="reviewAsset(asset, 'reject')"
  >
    拒绝
  </button>
  <button
    v-if="assetAllowed(asset, 'repaint')"
    type="button"
    :data-testid="`edit-asset-${asset.id}`"
    class="border border-sky-500/70 px-2 py-1 text-xs text-sky-100 hover:bg-sky-950"
    @click="editAgain(asset)"
  >
    重绘
  </button>
  <button
    v-if="assetAllowed(asset, 'promote_to_video_asset')"
    type="button"
    :data-testid="`promote-asset-${asset.id}`"
    class="border border-violet-500/70 px-2 py-1 text-xs text-violet-100 hover:bg-violet-950"
    @click="promoteAsset(asset)"
  >
    推广到视频
  </button>
</div>
```

Add helper:

```javascript
function assetReviewGateLabel(gate) {
  if (gate?.status === 'approved') return '已通过'
  if (gate?.status === 'manual_review_pending') return '待人工审查'
  if (gate?.status === 'ai_review_pending') return '待 AI 审查'
  if (gate?.status === 'blocked') return '已阻塞'
  return '未开始'
}
```

Add promotion handler:

```javascript
async function promoteAsset(asset) {
  if (!asset.id) return
  const context = asset.destination_context || {}
  const runId = context.video_run_id || context.run_id
  const frameId = context.frame_id
  if (!runId || !frameId) {
    error.value = '该图像缺少视频生产目标，不能直接推广到视频。'
    return
  }
  error.value = ''
  try {
    await promoteImageAssetToVideo(asset.id, {
      run_id: runId,
      frame_id: frameId,
      episode_id: asset.episode_id || task.value?.episode_id,
    })
    updateAsset({ ...asset, downstream_promoted: true })
  } catch (e) {
    error.value = normalizeError(e)
  }
}
```

Add dispatch function:

```javascript
const queueStatusLabel = computed(() => {
  const capacity = task.value?.capacity || {}
  if (task.value?.status !== 'queued') return ''
  return `排队中，前方 ${capacity.queue_depth || 0} 个任务，预计等待 ${capacity.estimated_wait_seconds || 0} 秒`
})

async function dispatchQueuedTask() {
  if (!task.value?.id || syncing.value) return
  syncing.value = true
  error.value = ''
  try {
    const response = await dispatchQueuedImageTask(task.value.id)
    applyTaskResponse(response)
  } catch (e) {
    error.value = normalizeError(e)
  } finally {
    syncing.value = false
  }
}
```

Add queue status and dispatch button next to sync button:

```html
<div
  v-if="task?.queue_job_id && !task?.pixelle_task_id"
  data-testid="image-queue-status"
  class="border border-amber-500/40 bg-amber-950/20 p-3 text-xs text-amber-100"
>
  {{ queueStatusLabel }}
  <p class="mt-1 text-amber-200/80">该任务尚未提交到 Pixelle，手动调度后才会进入真实生成。</p>
</div>
```

```html
<button
  v-if="task?.queue_job_id && !task?.pixelle_task_id"
  type="button"
  data-testid="dispatch-queued-image-task"
  class="border border-amber-500/70 px-3 py-1 text-xs text-amber-100 hover:bg-amber-950 disabled:cursor-not-allowed disabled:opacity-50"
  :disabled="syncing"
  @click="dispatchQueuedTask"
>
  手动调度排队任务
</button>
```

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js
```

Expected: PASS.

- [ ] **Step 8: Run focused accessibility and responsive checks**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-a11y.test.js
```

Expected: PASS. The review backlog filter must expose `aria-pressed`, high-cost confirmation must be reachable near the submit CTA, and the queue status must be visible in the task panel before manual dispatch.

## Task 6: Focused Regression And Build

**Files:**
- No source files should be modified in this task unless a test exposes a Phase 3 bug.

- [ ] **Step 1: Run backend Phase 3 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py tests/test_image_production_cost_service.py tests/test_image_selection_preview_service.py tests/test_image_creation_strategy_snapshot.py tests/test_image_asset_bridge.py -v
```

Expected: PASS.

Also run the structured error test from Task 0:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_errors.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend image regression**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_api.py tests/test_image_creation_models.py tests/test_image_creation_model_resolution.py tests/test_image_creation_pixelle_client.py tests/test_image_creation_mocked_e2e.py -v
```

Expected: PASS. Existing SQLAlchemy expression-index reflection warning is acceptable if there are no failures.

- [ ] **Step 3: Run migration tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py -v
```

Expected: PASS after extending the migration graph test to assert:

- Alembic head is `2b3c4d5e6f70`.
- `image_production_cost_events` is created.
- `event_key` length is 220, task/asset FKs exist, `uq_image_cost_event_key` exists, and the event type/strategy/created indexes exist.
- downgrade removes the table cleanly.

- [ ] **Step 4: Run frontend Phase 3 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/image-production-strategy-page.test.js src/__tests__/navigation.test.js
```

Expected: PASS.

- [ ] **Step 5: Run frontend build**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run build
```

Expected: PASS. Existing Vite large chunk warnings are acceptable if there are no errors.

- [ ] **Step 6: Scan production code for leaked provider secrets**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
rg -n 'ark-[0-9a-fA-F-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|(api_key|access_token|client_secret)\s*[:=]\s*["''][^"'']{8,}' server/app web/src
```

Expected: no real provider keys, bearer tokens, or decrypted API key values in production code.

- [ ] **Step 7: Final review checkpoint**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short -- server/app/services/image_creation_errors.py server/app/services/image_production_policy_runtime.py server/app/services/image_production_cost_service.py server/app/services/image_review_gate_service.py server/app/services/image_selection_preview_service.py server/app/services/image_creation_service.py server/app/services/image_asset_bridge_service.py server/app/db_models.py server/app/routers/image_creation.py server/tests/test_image_creation_errors.py server/tests/test_image_production_policy_runtime.py server/tests/test_image_production_cost_service.py server/tests/test_image_selection_preview_service.py server/tests/test_image_creation_strategy_snapshot.py server/tests/test_image_asset_bridge.py server/tests/test_image_production_migration.py web/src/views/ImageCreationPage.vue web/src/api/imageCreation.js web/src/api/imageProduction.js web/src/__tests__/image-creation-page.test.js
```

Expected: only Phase 3 files are listed from this plan, plus pre-existing unrelated worktree changes outside this file set.

## Phase 3 Completion Criteria

- Selection preview returns policy-based cost estimate, time estimate, capacity state, and review gate state.
- Frontend does not silently set `cost_confirmation: true` in create or repaint/edit-again paths; high-cost work requires an explicit operator confirmation.
- Task creation submits, queues, or returns `409 IMAGE_CAPACITY_BLOCKED` according to capacity admission state.
- Queued image tasks are visible and do not call Pixelle until real manual dispatch submits them.
- Queue job ids fit the current `String(36)` column by using bare UUID strings.
- Cost estimate event is written after durable task creation and before any queue return or Pixelle submit; actual event is written after provider completion only when usage data includes cost.
- Generated image assets carry review gate metadata and allowed actions.
- Image-to-video promotion is blocked until required gates pass.
- Review backlog filters assets by pending/approved/blocked state.
- Approved assets expose a working promote-to-video action; blocked review assets expose clear rescue actions: approve/reject/repaint/copy as new task.
- Focused backend tests pass.
- Focused frontend tests pass.
- Frontend build passes.
- Production secret scan finds no credential leaks.

## Deferred To Phase 4

- A/B strategy groups and attempts.
- Cost multiplication confirmation for A/B.
- Winner adoption flow.
- Strategy quality/cost/latency metrics feedback loop.
- Human-approved strategy mutation recommendations.

## Self-Review

Spec coverage:

- Phase 3 review policy references are covered by Tasks 1, 3, 4, and 5.
- Cost estimate preview and high-cost confirmation are covered by Tasks 1, 2, 3, and 5.
- Capacity policy and queue state display are covered by Tasks 1, 3, and 5.
- Downstream image-to-video blocking is covered by Task 4.
- Explicit bridge API remains the existing `/api/image-production/assets/{asset_id}/promote-to-video-asset`.
- A/B scope is explicitly deferred to Phase 4.

Placeholder scan:

- No step uses unresolved placeholder behavior.

Type consistency:

- Backend policy payloads consistently use `cost_estimate`, `time_estimate`, `capacity`, and `review_gate`.
- Frontend reads the same fields from selection preview, task payload, and asset payload.
- Existing task fields `estimated_cost_json`, `queue_job_id`, `capacity_lease_id`, `review_policy`, and `request_json` are reused instead of adding duplicate task columns.

## Autoplan Review Artifacts

What already exists:

- `ImageProductionPolicyVersion`, `ImageProductionStrategy`, `ImageSelectionPreview`, `ImageCreationTask`, `ImageCreationAsset`, and `ImageCreationReviewRecord` already exist in `server/app/db_models.py`.
- `ImageCreationTask` already has `estimated_cost_json`, `requires_cost_confirmation`, `queue_job_id`, `capacity_lease_id`, `review_policy`, `pixelle_payload_json`, `request_json`, and `provider_response_json`.
- `image_asset_bridge_service.py` already promotes approved image assets into `VideoProductionAsset`.
- `imageProduction.js` already exposes `promoteImageAssetToVideo`; Phase 3 should use it instead of creating a duplicate API.

NOT in scope:

- Scheduler/daemon wiring for queued tasks.
- Autonomous fallback execution without operator confirmation.
- A/B strategy groups, strategy winner adoption, and strategy auto-mutation.
- Standalone cost analytics dashboard beyond the event ledger and task/asset visibility.

Architecture dependency graph:

```text
ImageCreationPage.vue
  |-- previewImageSelection() --------------------+
  |                                               v
  |                                     image_selection_preview_service
  |                                               |
  |                                               v
  |                                image_production_policy_runtime
  |                                  | cost | capacity | review
  |
  |-- createImageTask() --------------------------+
  |                                               v
  |                                     image_creation_service
  |                                  | task snapshot
  |                                  | cost event
  |                                  | queue/admit
  |                                  | Pixelle submit
  |
  |-- dispatchQueuedImageTask() ------------------+
  |                                               v
  |                              dispatch_queued_image_task()
  |                                  | recheck capacity
  |                                  | acquire lease
  |                                  | Pixelle submit
  |
  |-- reviewImageAsset() -------------------------+
  |                                               v
  |                              image_review_gate_service
  |
  |-- promoteImageAssetToVideo() -----------------+
                                                  v
                               image_asset_bridge_service
                                  | review gate pass?
                                  v
                            VideoProductionAsset
```

Test diagram:

| Flow | Required coverage |
|---|---|
| Structured image errors | `test_image_creation_errors.py` verifies `details`, `rescue_actions`, and backward compatibility. |
| Policy preview | `test_image_production_policy_runtime.py` and `test_image_selection_preview_service.py` verify cost/time/capacity/review fields. |
| High-cost create | `test_image_creation_strategy_snapshot.py` verifies `409 IMAGE_COST_CONFIRMATION_REQUIRED` before Pixelle submit. |
| Capacity queued | `test_image_creation_strategy_snapshot.py` verifies queued task persists without `pixelle_task_id`. |
| Capacity blocked | `test_image_creation_strategy_snapshot.py` verifies `409 IMAGE_CAPACITY_BLOCKED` and structured capacity details. |
| Capacity re-check | `test_image_creation_strategy_snapshot.py` verifies submit-now decisions are rechecked before assigning a lease. |
| Manual dispatch | `test_image_creation_strategy_snapshot.py` verifies queued task dispatch calls Pixelle and becomes running. |
| Manual dispatch missing payload | `test_image_creation_strategy_snapshot.py` verifies queued tasks without saved provider payload return `409 IMAGE_QUEUE_PAYLOAD_MISSING`. |
| Cost ledger | `test_image_production_cost_service.py` verifies estimate idempotency, actual usage recording, and no actual event without cost. |
| Review gate | `test_image_asset_bridge.py` verifies manual and AI gate blocks. |
| Promote target guard | `test_image_asset_bridge.py` verifies `promote_to_video_asset` is exposed only when the asset has a video run/frame target. |
| Frontend trust rail | `image-creation-page.test.js` verifies cost/time/capacity/review display and confirmation reset. |
| Frontend review backlog | `image-creation-page.test.js` verifies allowed actions and promote button visibility. |
| Frontend repaint cost | `image-creation-page.test.js` verifies repaint/edit-again does not silently pass `cost_confirmation: true`. |

Failure modes registry:

| Failure mode | Risk | Mitigation in revised plan |
|---|---|---|
| `image_error` rejects new kwargs | Implementation fails at runtime | Task 0 extends error contract first and adds tests. |
| Cost estimation uses `model_config` before it exists | Implementation fails or diverges | Task 3 explicitly moves model resolution before cost estimation. |
| Capacity block returns both 409 and 200 blocked task | Client behavior ambiguous | Revised contract uses 409 for block and 200 queued task only when queueing is enabled. |
| Fake dispatch creates dead queue | User sees queue but cannot produce | Task 3 requires real manual dispatch to Pixelle. |
| Queued task lacks provider payload | Manual dispatch submits an empty or malformed request | Task 3 returns `409 IMAGE_QUEUE_PAYLOAD_MISSING` and tells the operator to recreate the task. |
| `queue_job_id` exceeds `String(36)` | Production DB truncation/error | Queue ids are bare UUID strings. |
| Stale capacity decision in a single request | More Pixelle submits than policy allows | Re-check capacity after flush and before assigning a lease. |
| Current task counted during capacity re-check | New task queues itself or blocks itself | Use `admission_pending` until the second capacity decision is applied. |
| Cost event key exceeds DB column | Actual cost event insert fails for long provider task ids | `event_key` length is 220. |
| Human approval bypasses AI-required gate | Bad asset enters video production | Task 4 checks manual and AI gates independently. |
| Approved asset lacks video target | UI promotes into guessed frame/run | `promote_to_video_asset` requires explicit run and frame context. |
| Repaint/edit silently confirms cost | Cost gate bypass | Task 5 sends `cost_confirmation: false` for edit-again and handles 409. |
| UI hides process in one overloaded panel | Operator cannot see production state | Task 5 splits pre-submit risk, production path, and review cards. |

Autoplan scores after revision:

- CEO/Product: 8/10 after replacing fake queue with real manual dispatch and adding review/promote closure.
- Design: 8/10 after splitting trust rail and gating asset actions by `allowed_actions`.
- Engineering: 8/10 after fixing error contract, model resolution order, capacity contract, and queue id length.
- DX: 8/10 after removing execution blockers and adding migration/error/front-end reset tests.

Decision Audit Trail:

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Eng | Add Task 0 for structured image errors | Auto-decided | Correctness | Existing `image_error` cannot support planned payloads. | Leaving `details`/`rescue_actions` as invalid kwargs. |
| 2 | Eng | Resolve model before cost estimation | Auto-decided | Executability | Policy cost may use model cost profile. | Estimating before `model_config` exists. |
| 3 | Product/Eng | Implement real manual dispatch | Auto-decided | User value | A fake dispatch endpoint creates a dead queue. | Marking queued tasks as blocked. |
| 4 | Eng | Use 409 for capacity block, 200 only for queue | Auto-decided | API clarity | Prevents frontend from treating blocked work as successful. | Persisting blocked task while naming contract says error. |
| 5 | Eng | Use UUID-only `queue_job_id` | Auto-decided | Production safety | Current column is `String(36)`. | Prefixing ids with `image-queue:`. |
| 6 | Product/Eng | Require manual and AI gate pass independently | Auto-decided | Safety | Human approval must not satisfy an AI-required gate. | `asset.status == approved` bypass. |
| 7 | Design | Split UI into pre-submit risk, production path, review cards | Auto-decided | Transparency | Prevents another overloaded side panel. | Adding all new fields to one summary grid. |
| 8 | Product/Design | Drive asset buttons from `allowed_actions` and add promote | Auto-decided | Workflow closure | Review gate should lead to video promotion, not only blocking. | Static approve/reject/edit buttons. |
| 9 | Product/Eng | Do not silently confirm repaint/edit cost | Auto-decided | Cost control | Repaint is a paid generation path too. | Keeping `editAgain` hardcoded to `true`. |
| 10 | Eng | Use `admission_pending` during capacity re-check | Auto-decided | Correctness | Prevents a new task from counting itself while rechecking capacity. | Rechecking while task is already `queued`. |
| 11 | Eng | Set cost event key length to 220 | Auto-decided | Production safety | UUID plus provider task id can exceed 160 characters. | Keeping `String(160)`. |
| 12 | Eng/Product | Require explicit video run and frame before showing promote | Auto-decided | Data integrity | UI must not guess a video target. | Defaulting to `asset.slot_key` or `frame-1`. |
| 13 | Eng | Block queued dispatch when provider payload is missing | Auto-decided | Correctness | A queued task must replay the exact provider payload saved at creation time. | Submitting an empty payload or failing with an opaque provider error. |

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-image-production-strategy-control-plane-phase3.md`.

Recommended execution:

1. **Subagent-Driven** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - acceptable only if one agent executes Task 0 through Task 6 sequentially with the listed test checkpoints.

## Plan Design Review Addendum

Design review result: plan is design-complete after the revisions below.

Scores:

| Dimension | Before | After | Result |
|---|---:|---:|---|
| Information architecture | 7.5 | 8.5 | Pre-submit checks, production path, review gate, and asset backlog are now separated. |
| State coverage | 7 | 8.5 | Added high-cost reset, filtered empty states, queued task status, and dispatch visibility. |
| User journey | 7.5 | 8.5 | Operator can move from preview to cost confirmation, queue dispatch, review, and video promotion without hidden steps. |
| AI slop risk | 8 | 8.5 | Removed vague field dumping and specified concrete labels, counts, and actions. |
| Design system fit | 8 | 8.5 | Reuses existing dark operational panel style, small controls, borders, and dense status layout. |
| Responsive and accessibility | 6.5 | 8 | Added submit-adjacent confirmation, `aria-pressed` filters, queue status, and a11y test checkpoint. |

Design decisions added:

- High-cost confirmation must appear near the main submit action, including mobile layouts.
- Trust rail must be grouped into `提交前检查`, `生产路径`, and `审查门禁`.
- Review backlog filters must show counts, `aria-pressed`, and filtered empty states.
- Asset card buttons must come from `allowed_actions`, not static approve/reject/edit controls.
- Queued tasks must display queue depth, wait estimate, and the fact that Pixelle has not been called yet.
- Manual dispatch button copy is `手动调度排队任务`, not a vague background action.

NOT in scope for design:

- A separate analytics dashboard for cost trends.
- A new visual timeline editor.
- New global navigation or route changes beyond the image workbench.
- New illustration-heavy or marketing-style layouts; this remains an operational tool.

What already exists and must be reused:

- Existing `ImageCreationPage.vue` dark control-panel structure.
- Existing mode tabs, model/parameter controls, source/reference board, trust rail, task panel, and asset card patterns.
- Existing `image-creation-a11y.test.js` regression target.

TODOs.md updates:

- None. The review converted actionable design gaps directly into this Phase 3 plan instead of deferring design debt.

Completion summary:

```text
+====================================================================+
| DESIGN PLAN REVIEW - COMPLETION SUMMARY                            |
+====================================================================+
| System Audit         | UI scope present, no DESIGN.md found         |
| Step 0               | Initial score 7.3, focus on state clarity    |
| Pass 1  Info Arch    | 7.5/10 -> 8.5/10                             |
| Pass 2  States       | 7.0/10 -> 8.5/10                             |
| Pass 3  Journey      | 7.5/10 -> 8.5/10                             |
| Pass 4  AI Slop      | 8.0/10 -> 8.5/10                             |
| Pass 5  Design Sys   | 8.0/10 -> 8.5/10                             |
| Pass 6  Responsive   | 6.5/10 -> 8.0/10                             |
| Pass 7  Decisions    | 6 resolved, 0 deferred                       |
+--------------------------------------------------------------------+
| NOT in scope         | written, 4 items                             |
| What already exists  | written                                      |
| TODOS.md updates     | 0 items proposed                             |
| Approved Mockups     | not generated                                |
| Decisions made       | 6 added to plan                              |
| Decisions deferred   | 0                                             |
| Overall design score | 7.3/10 -> 8.4/10                              |
+====================================================================+
```

Plan is design-complete. Run `/design-review` after implementation for visual QA.

## Plan Eng Review Addendum

Engineering review result: plan is implementation-ready after the revisions below.

Issues fixed in this review:

- Policy runtime tests now assert returned fields individually, including `policy_version_id`.
- Capacity limit tests seed `model_id`, so the model-scoped running-task filter is meaningful.
- Cost ledger `event_key` length is 220 in the model, migration, and migration test contract.
- Task creation uses `admission_pending` during post-flush capacity re-check so the current task does not count itself.
- Queued dispatch handles model-resolution errors and returns `409 IMAGE_QUEUE_PAYLOAD_MISSING` when the saved provider payload is absent.
- Manual approval now sets `audit_status="approved"` when no AI review is required.
- `promote_to_video_asset` is exposed only when the asset has explicit video run and frame context.
- Frontend promotion no longer guesses a `run_id` or `frame_id` from `slot_key` or a hardcoded default.

NOT in scope for engineering:

- A distributed capacity lock or worker-wide semaphore. Phase 3 only fixes stale decisions inside one request.
- A hidden queue daemon. Manual dispatch is explicit and visible to the operator.
- A video target picker inside the image workbench. Promotion requires existing run/frame context.
- Cost trend analytics beyond the task/asset cost event ledger.
- Provider retry orchestration beyond the existing fallback/error payload path.

What already exists and must be reused:

- `ImageCreationTask`, `ImageCreationAsset`, Pixelle submission, and task sync flows remain the execution spine.
- The model configuration center already resolves model scene and capability. Phase 3 reorders resolution before cost estimation instead of creating another selector.
- Existing policy-version storage is reused through `ImageProductionPolicyVersion`; Phase 3 adds runtime preview/evaluation functions around it.
- Existing image workbench layout, trust rail, task list, asset cards, and API wrapper are extended rather than replaced.
- Existing Alembic head is `1a2b3c4d5e6f`; the Phase 3 migration must use that as `down_revision`.

Failure-mode review:

| Area | Critical gap before review | Revision |
|---|---|---|
| Cost ledger | Long provider ids could overflow `event_key`. | Column and migration use `String(220)` and tests assert long keys. |
| Capacity | A flushed task could count itself and self-queue/self-block. | New task stays `admission_pending` until the second capacity decision is applied. |
| Queue dispatch | Missing payload could submit an empty provider call or fail opaquely. | Dispatch returns `409 IMAGE_QUEUE_PAYLOAD_MISSING` with affected task id. |
| Review gate | Manual approval could bypass pending AI review state. | Manual and AI gates are checked independently. |
| Video promotion | UI could promote into a guessed frame. | Backend action and frontend handler require explicit run/frame target. |

Implementation diagrams:

- The plan already includes a data-flow diagram and test coverage matrix.
- Add a short inline ASCII state note in `server/app/services/image_creation_service.py` near the admission flow: `admission_pending -> queued(waiting) | queued(admitted lease) -> running`.
- Add a short inline ASCII gate note in `server/app/services/image_review_gate_service.py`: `manual gate + AI gate -> allowed/blocked`.

Parallelization strategy:

| Step | Modules touched | Depends on |
|---|---|---|
| Task 0 structured errors | `server/app/services`, `server/tests` | none |
| Task 1 policy runtime | `server/app/services`, `server/tests` | Task 0 for structured errors in previews |
| Task 2 cost ledger | `server/app/db_models.py`, `server/alembic`, `server/app/services`, `server/tests` | Task 0 |
| Task 3 task creation and dispatch | `server/app/services`, `server/app/routers`, `server/tests` | Task 0, Task 1, Task 2 |
| Task 4 review gate and bridge | `server/app/services`, `server/tests` | Task 0, Task 1 |
| Task 5 frontend workbench | `web/src`, `web/tests` | Task 3 and Task 4 response contracts |
| Task 6 regression | `server/tests`, `web/tests` | Tasks 0-5 |

Parallel lanes:

- Lane A: Task 0 -> Task 1 -> Task 2. Backend foundation, mostly sequential because services/tests share contracts.
- Lane B: Task 4 can start after Task 0 and Task 1, but must coordinate with Task 3 on `asset_payload` and `allowed_actions`.
- Lane C: Task 5 can prepare UI structure early, but final wiring waits for Task 3 and Task 4 payload contracts.
- Lane D: Task 6 runs last.

Execution order: launch Lane A first. After Task 1 lands, Lane B can proceed. After Task 3/4 payload contracts are stable, finish Lane C. Run Lane D after merges.

Conflict flags: Task 3 and Task 4 both touch `server/app/services/image_creation_service.py`; keep them sequential or merge one small service boundary before parallel UI work.

TODOs.md updates:

- None. Engineering findings were folded directly into this Phase 3 implementation plan instead of deferred.

Completion summary:

```text
+====================================================================+
| ENGINEERING PLAN REVIEW - COMPLETION SUMMARY                       |
+====================================================================+
| Step 0 Scope Challenge | scope accepted as-is                       |
| Architecture Review    | 4 issues found, 4 fixed                   |
| Code Quality Review    | 2 issues found, 2 fixed                   |
| Test Review            | diagram produced, 2 gaps fixed            |
| Performance Review     | 0 new issues                              |
| NOT in scope           | written, 5 items                          |
| What already exists    | written                                   |
| TODOS.md updates       | 0 items proposed                          |
| Failure modes          | 0 critical gaps after revision            |
| Outside voice          | skipped, plan-only local review           |
| Parallelization        | 4 lanes, limited parallel after Task 1    |
| Lake Score             | 8/8 complete fixes chosen                 |
+====================================================================+
```

Plan is engineering-cleared for implementation. Diff-level code review is still required after implementation.

## Writing-Plans Self Review

Spec coverage check:

| Spec requirement | Covered by |
|---|---|
| Review policy runtime from strategy policy versions | Task 1 policy runtime and Task 4 review gate service |
| Cost and time estimate before execution | Task 1 policy runtime, Task 2 cost ledger, Task 3 creation integration |
| High-cost confirmation without silent frontend bypass | Task 3 backend 409 contract and Task 5 frontend confirmation reset |
| Capacity preview, queue depth, wait estimate, and admission | Task 1 capacity preview and Task 3 creation/dispatch integration |
| Real queued-task dispatch instead of a fake status change | Task 3 `dispatch_queued_image_task` service and router endpoint |
| Review metadata on generated image assets | Task 4 `asset_review_gate` and `review_image_asset` integration |
| Video promotion only after required gate passes | Task 4 image-to-video bridge tests and implementation |
| Review backlog and blocked asset rescue actions in UI | Task 5 review backlog, filters, and `allowed_actions` handling |
| Image production cost event ledger | Task 2 model, migration, service, and tests |
| A/B strategy groups and automatic strategy mutation | Explicitly deferred to Phase 4 in out-of-scope section |

Placeholder scan:

- Searched the plan for the forbidden placeholder vocabulary named by the `writing-plans` skill.
- No implementation placeholders remain.
- `TODOs.md updates` appears only as review metadata and does not defer implementation work.

Type and contract consistency:

- Backend names are consistent across tasks: `ImageProductionPolicyVersion`, `ImageProductionCostEvent`, `ImageCreationTask`, `ImageCreationAsset`, `dispatch_queued_image_task`, `asset_review_gate`, and `promote_image_asset_to_video_asset`.
- Payload keys are consistent across backend and frontend tasks: `cost_estimate`, `time_estimate`, `capacity`, `review_gate`, `queue_job_id`, `capacity_lease_id`, `allowed_actions`, and `destination_context`.
- Error codes are consistently defined and tested: `IMAGE_COST_CONFIRMATION_REQUIRED`, `IMAGE_CAPACITY_BLOCKED`, `IMAGE_QUEUE_PAYLOAD_MISSING`, `IMAGE_TASK_NOT_DISPATCHABLE`, `PIXELLE_IMAGE_DISPATCH_FAILED`, and `IMAGE_REVIEW_GATE_BLOCKED`.
- Admission states are consistent: `admission_pending` is internal only; API-visible waiting/admitted tasks remain `queued`, with `queue_job_id` or `capacity_lease_id` distinguishing the path.
- Video promotion contract is consistent: no backend action and no frontend button unless explicit `video_run_id`/`run_id` plus `frame_id` exist.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope and strategy | 1 | CLEAR via `/autoplan` | Replaced dead queue with real manual dispatch and closed review-to-video workflow. |
| Codex Review | `/codex review` | Independent second opinion | 0 | not run | No diff-level review was requested for this plan-only change. |
| Eng Review | `/plan-eng-review` | Architecture and tests required | 2 | CLEAR | 8 engineering issues fixed, 0 critical gaps after revision. |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR | Score 7.3/10 -> 8.4/10, 6 design decisions added. |
| DX Review | `/plan-devex-review` | Developer execution clarity | 1 | CLEAR via `/autoplan` | Removed execution blockers and added error, migration, frontend, and a11y checkpoints. |

- **UNRESOLVED:** 0 decisions.
- **VERDICT:** CEO + ENG + DESIGN + DX CLEARED for implementation planning. Diff-level code review is still required after implementation.
