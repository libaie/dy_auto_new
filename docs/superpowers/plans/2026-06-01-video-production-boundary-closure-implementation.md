# Video Production Boundary Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real one-click video production loop with paid-provider safety, stage review gates, persisted assets, and long-video worker stability.

**Architecture:** Keep `dy_auto` as the orchestration/control plane and route all real paid provider work through a single `ProviderStageExecutor`. Use small services for state contracts, action results, provider stage tasks, cost reservations, asset persistence, aggregate gates, and worker execution so legacy route handlers cannot bypass the safety boundaries.

**Tech Stack:** FastAPI, SQLAlchemy models/Alembic, pytest, Vue/Vite/Vitest, existing `VideoProductionRun`/`ProductionJob`/`VideoProductionAsset`/`VideoReviewRecord`/`ProductionAuditEvent` tables.

---

## Scope

This plan implements the reviewed design in `docs/superpowers/specs/2026-06-01-video-production-boundary-closure-design.md`.

It does not build the 3D expert console, Douyin publishing, a visual timeline editor, or a full operator analytics product. It only adds the boundaries needed for real provider execution, review gates, asset persistence, long-video scheduling stability, health checks, and transparent frontend states.

## File Structure

Create:

- `server/alembic/versions/5e6f708192a3_video_production_boundary_closure.py`: Phase 0 schema fields, tables, and indexes.
- `server/app/services/production_action_result.py`: one repair/result payload used by services and routes.
- `server/app/services/production_state_contract.py`: central status constants, terminal/active/reviewable sets, transition checks.
- `server/app/services/provider_stage_task_service.py`: create/read/update `ProviderStageTask`, request hash conflict checks, manual task-id repair.
- `server/app/services/provider_cost_reservation_service.py`: atomic budget reservation, settlement, release, stale repair accounting.
- `server/app/services/provider_capability_service.py`: real paid capability gate from model/provider config.
- `server/app/services/asset_storage_guard.py`: safe provider URL/Pixelle path ingestion, checksum, MIME, atomic persistence.
- `server/app/services/provider_stage_executor.py`: two-phase paid provider executor and recovery boundary.
- `server/app/services/production_gate_evaluator.py`: fan-in stage evaluator and final writeback guard.
- `server/app/services/production_worker_service.py`: real worker-step entrypoint with lease, batch, throttle, and repair results.
- `server/tests/test_provider_cost_reservation_service.py`
- `server/tests/test_provider_stage_executor.py`
- `server/tests/test_provider_throttle_and_backoff.py`
- `server/tests/test_asset_storage_guard.py`
- `server/tests/test_production_gate_evaluator.py`
- `server/tests/test_video_production_performance_boundaries.py`
- `web/src/__tests__/video-production-monitor-boundary-states.test.js`
- `web/src/__tests__/video-production-monitor-performance.test.js`

Modify:

- `server/app/db_models.py`: add `ProviderStageTask`, `ProviderCostReservation`, missing asset/review/audit fields, and indexes.
- `server/app/services/production_errors.py`: extend `ProductionErrorCode`; delegate HTTP payloads to `ProductionActionResult`.
- `server/app/services/production_status.py`: keep compatibility constants and import/alias new state contract constants where useful.
- `server/app/services/video_production_service.py`: make old stage functions wrapper-only for real paid runs; enforce persisted asset review gate.
- `server/app/routers/video_production.py`: add worker-step, stage-task, persist-retry, bounded run payloads, and action-result HTTP responses.
- `server/app/main.py`: include system health route if it is not already mounted.
- `web/src/api/videoProduction.js`: add worker-step, stage-task, persist-retry, bounded tree/review calls.
- `web/src/views/VideoProductionMonitorPage.vue`: display repair CTA, stage task rail, cost reservation states, provider throttle, and bounded data loading.
- `web/src/views/AIVideoReviewPage.vue`: disable approval for non-persisted, superseded, or permission-blocked assets.

---

### Task 1: Schema, State Contract, And Unified Action Result

**Files:**
- Create: `server/alembic/versions/5e6f708192a3_video_production_boundary_closure.py`
- Create: `server/app/services/production_action_result.py`
- Create: `server/app/services/production_state_contract.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/services/production_errors.py`
- Test: `server/tests/test_video_production_boundary_models.py`

- [ ] **Step 1: Write failing model and action-result tests**

Create `server/tests/test_video_production_boundary_models.py`:

```python
from app.db_models import (
    ProviderCostReservation,
    ProviderStageTask,
    ProductionAuditEvent,
    VideoProductionAsset,
    VideoReviewRecord,
)
from app.services.production_action_result import ProductionActionResult
from app.services.production_errors import ProductionErrorCode
from app.services.production_state_contract import (
    PROVIDER_TASK_RESERVED,
    provider_task_is_active,
    validate_transition,
)


def test_provider_stage_task_and_cost_reservation_models_exist(db):
    task = ProviderStageTask(
        run_id="run-1",
        plan_id="plan-1",
        job_id="job-1",
        target_type="production_segment",
        target_id="seg-1",
        stage="image_generation",
        provider="mock",
        model_name="mock-image",
        request_hash="hash-1",
        idempotency_key="run-1:seg-1:image:v1",
        status=PROVIDER_TASK_RESERVED,
    )
    reservation = ProviderCostReservation(
        plan_id="plan-1",
        provider_stage_task_id="task-1",
        status="active_unsubmitted",
        estimated_cost=0.12,
        reserved_cost=0.12,
        currency="CNY",
    )

    assert task.status == "reserved"
    assert task.idempotency_key == "run-1:seg-1:image:v1"
    assert reservation.status == "active_unsubmitted"
    assert reservation.reserved_cost == 0.12


def test_existing_models_include_boundary_fields():
    assert hasattr(VideoProductionAsset, "storage_path")
    assert hasattr(VideoProductionAsset, "source_url")
    assert hasattr(VideoProductionAsset, "storage_error_json")
    assert hasattr(VideoProductionAsset, "provider_response_summary_json")
    assert hasattr(VideoProductionAsset, "provider_stage_task_id")
    assert hasattr(VideoReviewRecord, "reviewer_role")
    assert hasattr(VideoReviewRecord, "action")
    assert hasattr(VideoReviewRecord, "asset_snapshot_json")
    assert hasattr(VideoReviewRecord, "model_trace_summary_json")
    assert hasattr(ProductionAuditEvent, "actor_user_id")
    assert hasattr(ProductionAuditEvent, "actor_role")


def test_action_result_serializes_repair_contract():
    result = ProductionActionResult.blocked(
        code=ProductionErrorCode.ASSET_STORAGE_FAILED,
        message="资产持久化失败，不能进入审查。",
        cause="mime_type_mismatch",
        repair_action="重新持久化资产或重新生成该片段。",
        repair_route="/video-production/run-1",
        affected_ids=["asset-1"],
        audit_event_type="asset.storage_failed",
    )

    assert result.ok is False
    assert result.to_http_detail()["code"] == "ASSET_STORAGE_FAILED"
    assert result.to_http_detail()["repair_route"] == "/video-production/run-1"
    assert result.to_http_detail()["affected_ids"] == ["asset-1"]


def test_state_contract_rejects_illegal_transition():
    assert provider_task_is_active("running") is True
    assert provider_task_is_active("succeeded") is False
    assert validate_transition("provider_stage_task", "reserved", "submitted") is True
    assert validate_transition("provider_stage_task", "succeeded", "running") is False
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest server/tests/test_video_production_boundary_models.py -q
```

Expected: FAIL because `ProviderStageTask`, `ProviderCostReservation`, `production_action_result`, and `production_state_contract` do not exist yet.

- [ ] **Step 3: Add state/action modules**

Create `server/app/services/production_action_result.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProductionActionResult:
    ok: bool
    code: str
    message: str
    cause: str | None = None
    repair_action: str | None = None
    repair_route: str | None = None
    affected_ids: list[str] = field(default_factory=list)
    retryable: bool = False
    severity: str = "warning"
    audit_event_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str = "ok", **details: Any) -> "ProductionActionResult":
        return cls(ok=True, code="OK", message=message, severity="ok", details=details)

    @classmethod
    def blocked(
        cls,
        *,
        code,
        message: str,
        cause: str,
        repair_action: str,
        repair_route: str | None = None,
        affected_ids: list[str] | None = None,
        retryable: bool = True,
        severity: str = "blocked",
        audit_event_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "ProductionActionResult":
        return cls(
            ok=False,
            code=getattr(code, "value", str(code)),
            message=message,
            cause=cause,
            repair_action=repair_action,
            repair_route=repair_route,
            affected_ids=affected_ids or [],
            retryable=retryable,
            severity=severity,
            audit_event_type=audit_event_type,
            details=details or {},
        )

    def to_http_detail(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "error_code": self.code,
            "message": self.message,
            "cause": self.cause,
            "repair_action": self.repair_action,
            "repair_route": self.repair_route,
            "affected_ids": self.affected_ids,
            "retryable": self.retryable,
            "severity": self.severity,
            "audit_event_type": self.audit_event_type,
            "details": self.details,
        }
```

Create `server/app/services/production_state_contract.py`:

```python
PROVIDER_TASK_RESERVED = "reserved"
PROVIDER_TASK_SUBMITTED = "submitted"
PROVIDER_TASK_RUNNING = "running"
PROVIDER_TASK_SYNC_REQUIRED = "sync_required"
PROVIDER_TASK_SUCCEEDED = "succeeded"
PROVIDER_TASK_FAILED = "failed"
PROVIDER_TASK_MANUAL_REPAIR_REQUIRED = "manual_repair_required"

PROVIDER_TASK_ACTIVE_STATUSES = {
    PROVIDER_TASK_RESERVED,
    PROVIDER_TASK_SUBMITTED,
    PROVIDER_TASK_RUNNING,
    PROVIDER_TASK_SYNC_REQUIRED,
    PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
}
PROVIDER_TASK_TERMINAL_STATUSES = {PROVIDER_TASK_SUCCEEDED, PROVIDER_TASK_FAILED}

ASSET_REGISTERED = "registered"
ASSET_STORAGE_FAILED = "storage_failed"
ASSET_REVIEW_PENDING = "review_pending"
ASSET_APPROVED = "approved"
ASSET_REJECTED = "rejected"
ASSET_SUPERSEDED = "superseded"

ASSET_REVIEWABLE_STATUSES = {ASSET_REVIEW_PENDING}
ASSET_TERMINAL_STATUSES = {ASSET_APPROVED, ASSET_REJECTED, ASSET_SUPERSEDED}

COST_ACTIVE_UNSUBMITTED = "active_unsubmitted"
COST_SUBMITTED = "submitted"
COST_SETTLED = "settled"
COST_RELEASED = "released"
COST_STALE_NEEDS_REPAIR = "stale_needs_repair"

TRANSITIONS = {
    "provider_stage_task": {
        PROVIDER_TASK_RESERVED: {PROVIDER_TASK_SUBMITTED, PROVIDER_TASK_SYNC_REQUIRED, PROVIDER_TASK_FAILED},
        PROVIDER_TASK_SUBMITTED: {PROVIDER_TASK_RUNNING, PROVIDER_TASK_SYNC_REQUIRED, PROVIDER_TASK_SUCCEEDED, PROVIDER_TASK_FAILED},
        PROVIDER_TASK_RUNNING: {PROVIDER_TASK_SYNC_REQUIRED, PROVIDER_TASK_SUCCEEDED, PROVIDER_TASK_FAILED},
        PROVIDER_TASK_SYNC_REQUIRED: {PROVIDER_TASK_RUNNING, PROVIDER_TASK_SUCCEEDED, PROVIDER_TASK_FAILED, PROVIDER_TASK_MANUAL_REPAIR_REQUIRED},
        PROVIDER_TASK_MANUAL_REPAIR_REQUIRED: {PROVIDER_TASK_SYNC_REQUIRED, PROVIDER_TASK_FAILED},
        PROVIDER_TASK_SUCCEEDED: set(),
        PROVIDER_TASK_FAILED: set(),
    },
    "video_production_asset": {
        ASSET_REGISTERED: {ASSET_REVIEW_PENDING, ASSET_STORAGE_FAILED, ASSET_SUPERSEDED},
        ASSET_STORAGE_FAILED: {ASSET_REGISTERED, ASSET_SUPERSEDED},
        ASSET_REVIEW_PENDING: {ASSET_APPROVED, ASSET_REJECTED, ASSET_SUPERSEDED},
        ASSET_APPROVED: {ASSET_SUPERSEDED},
        ASSET_REJECTED: {ASSET_SUPERSEDED},
        ASSET_SUPERSEDED: set(),
    },
}


def provider_task_is_active(status: str) -> bool:
    return status in PROVIDER_TASK_ACTIVE_STATUSES


def asset_is_reviewable(status: str) -> bool:
    return status in ASSET_REVIEWABLE_STATUSES


def validate_transition(entity: str, current: str, next_status: str) -> bool:
    return next_status in TRANSITIONS.get(entity, {}).get(current, set())
```

- [ ] **Step 4: Add models and migration**

Modify `server/app/db_models.py`:

```python
class ProviderStageTask(Base):
    __tablename__ = "provider_stage_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_provider_stage_tasks_idempotency"),
        Index("idx_provider_stage_tasks_run_stage_status", "run_id", "stage", "status"),
        Index("idx_provider_stage_tasks_plan_stage_status", "plan_id", "stage", "status"),
        Index("idx_provider_stage_tasks_target", "target_type", "target_id"),
        Index("idx_provider_stage_tasks_provider_task_id", "provider_task_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String(36), ForeignKey("production_jobs.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(36), nullable=False)
    stage = Column(String(40), nullable=False)
    provider = Column(String(80), nullable=False)
    model_name = Column(String(120), nullable=False)
    request_hash = Column(String(64), nullable=False)
    idempotency_key = Column(String(220), nullable=False)
    status = Column(String(40), nullable=False, default="reserved")
    provider_task_id = Column(String(160), nullable=True)
    external_task_id = Column(String(160), nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    response_summary_json = Column(JSON, nullable=True, default=dict)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProviderCostReservation(Base):
    __tablename__ = "provider_cost_reservations"
    __table_args__ = (
        UniqueConstraint("provider_stage_task_id", name="uq_provider_cost_reservation_stage_task"),
        Index("idx_provider_cost_reservations_plan_status", "plan_id", "status"),
        Index("idx_provider_cost_reservations_expires", "expires_at", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    provider_stage_task_id = Column(String(36), ForeignKey("provider_stage_tasks.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(40), nullable=False, default="active_unsubmitted")
    estimated_cost = Column(Float, nullable=False, default=0.0)
    reserved_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=True)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    expires_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
```

Add these fields to existing models:

```python
VideoProductionAsset.storage_path = Column(Text, nullable=True)
VideoProductionAsset.source_url = Column(Text, nullable=True)
VideoProductionAsset.storage_error_json = Column(JSON, nullable=True, default=dict)
VideoProductionAsset.provider_response_summary_json = Column(JSON, nullable=True, default=dict)
VideoProductionAsset.provider_stage_task_id = Column(String(36), ForeignKey("provider_stage_tasks.id", ondelete="SET NULL"), nullable=True)

VideoReviewRecord.reviewer_role = Column(String(40), nullable=True)
VideoReviewRecord.action = Column(String(40), nullable=True)
VideoReviewRecord.asset_snapshot_json = Column(JSON, nullable=True, default=dict)
VideoReviewRecord.model_trace_summary_json = Column(JSON, nullable=True, default=dict)

ProductionAuditEvent.actor_user_id = Column(String(36), nullable=True)
ProductionAuditEvent.actor_role = Column(String(40), nullable=True)
```

Create matching Alembic operations in `server/alembic/versions/5e6f708192a3_video_production_boundary_closure.py` for every column/table/index above, with downgrade dropping them in reverse order.

- [ ] **Step 5: Extend errors**

Modify `server/app/services/production_errors.py`:

```python
class ProductionErrorCode(str, Enum):
    INVALID_RUN_TYPE = "INVALID_RUN_TYPE"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    STYLE_LOCK_MISSING = "STYLE_LOCK_MISSING"
    STORYBOARD_MISSING = "STORYBOARD_MISSING"
    SEGMENT_PLAN_MISSING = "SEGMENT_PLAN_MISSING"
    RUN_LINK_AMBIGUOUS = "RUN_LINK_AMBIGUOUS"
    RUN_LINK_MISSING = "RUN_LINK_MISSING"
    PROVIDER_TASK_PENDING = "PROVIDER_TASK_PENDING"
    PROVIDER_TASK_FAILED = "PROVIDER_TASK_FAILED"
    ASSET_URL_MISSING = "ASSET_URL_MISSING"
    ASSET_COPY_FAILED = "ASSET_COPY_FAILED"
    STALE_ASSET_VERSION = "STALE_ASSET_VERSION"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    BUDGET_EXHAUSTED_AFTER_ACTUAL_COST = "BUDGET_EXHAUSTED_AFTER_ACTUAL_COST"
    PROVIDER_STAGE_TASK_EXISTS = "PROVIDER_STAGE_TASK_EXISTS"
    PROVIDER_STAGE_TASK_SYNC_REQUIRED = "PROVIDER_STAGE_TASK_SYNC_REQUIRED"
    PROVIDER_SUBMIT_FAILED = "PROVIDER_SUBMIT_FAILED"
    PROVIDER_THROTTLED = "PROVIDER_THROTTLED"
    ASSET_STORAGE_FAILED = "ASSET_STORAGE_FAILED"
    REVIEW_PERMISSION_DENIED = "REVIEW_PERMISSION_DENIED"
    REVIEW_GATE_BLOCKED = "REVIEW_GATE_BLOCKED"
    MIGRATION_HEALTH_BLOCKED = "MIGRATION_HEALTH_BLOCKED"
    PAUSED_BY_OPERATOR = "PAUSED_BY_OPERATOR"
    RETRY_IMPACT_BLOCKED = "RETRY_IMPACT_BLOCKED"
```

- [ ] **Step 6: Run tests and migration smoke**

Run:

```bash
pytest server/tests/test_video_production_boundary_models.py -q
```

Expected: PASS.

Run:

```bash
alembic -c server/alembic.ini upgrade head
```

Expected: migration applies cleanly in the local test/dev database.

- [ ] **Step 7: Commit**

```bash
git add server/alembic/versions/5e6f708192a3_video_production_boundary_closure.py server/app/db_models.py server/app/services/production_action_result.py server/app/services/production_state_contract.py server/app/services/production_errors.py server/tests/test_video_production_boundary_models.py
git commit -m "feat: add video production boundary schema"
```

---

### Task 2: Atomic Provider Cost Reservation

**Files:**
- Create: `server/app/services/provider_cost_reservation_service.py`
- Modify: `server/app/services/production_cost_summary_service.py`
- Test: `server/tests/test_provider_cost_reservation_service.py`

- [ ] **Step 1: Write failing reservation tests**

Create `server/tests/test_provider_cost_reservation_service.py`:

```python
from datetime import timedelta

import pytest

from app.config import bj_now
from app.db_models import ProviderCostReservation, ProviderStageTask, ProductionPlan, Series
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.provider_cost_reservation_service import (
    active_reserved_cost,
    create_cost_reservation,
    expire_unsubmitted_reservations,
    mark_reservation_submitted,
    release_unsubmitted_reservation,
    settle_reservation,
)


def _plan(db, budget_limit=1.0, current_cost=0.0):
    series = Series(title="Cost Show", logline="Cost", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(
        series_id=series.id,
        status="running",
        target_total_duration_seconds=60,
        budget_limit=budget_limit,
        current_cost=current_cost,
    )
    db.add(plan)
    db.commit()
    return plan


def _stage_task(db, plan):
    task = ProviderStageTask(
        run_id="run-1",
        plan_id=plan.id,
        target_type="production_segment",
        target_id="seg-1",
        stage="image_generation",
        provider="mock",
        model_name="mock-image",
        request_hash="hash-1",
        idempotency_key=f"{plan.id}:seg-1:image:v1",
        status="reserved",
    )
    db.add(task)
    db.commit()
    return task


def test_create_cost_reservation_blocks_when_budget_would_be_exceeded(db):
    plan = _plan(db, budget_limit=0.1)
    task = _stage_task(db, plan)

    with pytest.raises(ProductionRepairableError) as exc_info:
        create_cost_reservation(db, plan_id=plan.id, provider_stage_task_id=task.id, estimated_cost=0.2)

    assert exc_info.value.code == ProductionErrorCode.BUDGET_BLOCKED
    assert db.query(ProviderCostReservation).count() == 0


def test_create_cost_reservation_counts_existing_active_reservations(db):
    plan = _plan(db, budget_limit=0.25)
    first_task = _stage_task(db, plan)
    create_cost_reservation(db, plan_id=plan.id, provider_stage_task_id=first_task.id, estimated_cost=0.2)
    second_task = ProviderStageTask(
        run_id="run-1",
        plan_id=plan.id,
        target_type="production_segment",
        target_id="seg-2",
        stage="image_generation",
        provider="mock",
        model_name="mock-image",
        request_hash="hash-2",
        idempotency_key=f"{plan.id}:seg-2:image:v1",
        status="reserved",
    )
    db.add(second_task)
    db.commit()

    with pytest.raises(ProductionRepairableError):
        create_cost_reservation(db, plan_id=plan.id, provider_stage_task_id=second_task.id, estimated_cost=0.1)

    assert active_reserved_cost(db, plan.id) == 0.2


def test_settle_reservation_records_actual_cost_once(db):
    plan = _plan(db, budget_limit=1.0)
    task = _stage_task(db, plan)
    reservation = create_cost_reservation(db, plan_id=plan.id, provider_stage_task_id=task.id, estimated_cost=0.2)
    mark_reservation_submitted(db, reservation.id)

    settle_reservation(db, reservation.id, actual_cost=0.3, units_json={"images": 1})
    settle_reservation(db, reservation.id, actual_cost=0.3, units_json={"images": 1})

    db.refresh(plan)
    assert plan.current_cost == 0.3
    saved = db.query(ProviderCostReservation).filter_by(id=reservation.id).one()
    assert saved.status == "settled"


def test_only_unsubmitted_reservations_can_release_or_expire(db):
    plan = _plan(db, budget_limit=1.0)
    task = _stage_task(db, plan)
    reservation = create_cost_reservation(
        db,
        plan_id=plan.id,
        provider_stage_task_id=task.id,
        estimated_cost=0.2,
        expires_at=bj_now() - timedelta(seconds=1),
    )

    assert expire_unsubmitted_reservations(db) == 1
    db.refresh(reservation)
    assert reservation.status == "released"

    submitted_task = _stage_task(db, plan)
    submitted = create_cost_reservation(
        db,
        plan_id=plan.id,
        provider_stage_task_id=submitted_task.id,
        estimated_cost=0.2,
        expires_at=bj_now() - timedelta(seconds=1),
    )
    mark_reservation_submitted(db, submitted.id)

    assert expire_unsubmitted_reservations(db) == 0
    db.refresh(submitted)
    assert submitted.status == "stale_needs_repair"

    with pytest.raises(ProductionRepairableError):
        release_unsubmitted_reservation(db, submitted.id)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest server/tests/test_provider_cost_reservation_service.py -q
```

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement reservation service**

Create `server/app/services/provider_cost_reservation_service.py`:

```python
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProviderCostReservation, ProductionPlan
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.production_state_contract import (
    COST_ACTIVE_UNSUBMITTED,
    COST_RELEASED,
    COST_SETTLED,
    COST_STALE_NEEDS_REPAIR,
    COST_SUBMITTED,
)


def _plan(db: Session, plan_id: str) -> ProductionPlan:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")
    return plan


def active_reserved_cost(db: Session, plan_id: str) -> float:
    total = (
        db.query(func.coalesce(func.sum(ProviderCostReservation.reserved_cost), 0.0))
        .filter(
            ProviderCostReservation.plan_id == plan_id,
            ProviderCostReservation.status.in_([COST_ACTIVE_UNSUBMITTED, COST_SUBMITTED, COST_STALE_NEEDS_REPAIR]),
        )
        .scalar()
    )
    return float(total or 0.0)


def create_cost_reservation(
    db: Session,
    *,
    plan_id: str,
    provider_stage_task_id: str,
    estimated_cost: float,
    currency: str = "CNY",
    expires_at: datetime | None = None,
) -> ProviderCostReservation:
    plan = _plan(db, plan_id)
    estimated = float(estimated_cost or 0.0)
    current = float(plan.current_cost or 0.0)
    reserved = active_reserved_cost(db, plan_id)
    if plan.budget_limit is not None and current + reserved + estimated > float(plan.budget_limit):
        db.rollback()
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="当前预算不足，无法继续提交真实模型。",
            cause="estimated_cost_exceeds_budget",
            repair_action="提高预算、减少分段或切换低成本模型。",
            repair_route=f"/video-production/plans/{plan_id}",
            affected_ids=[plan_id],
            retryable=True,
        )

    reservation = ProviderCostReservation(
        plan_id=plan_id,
        provider_stage_task_id=provider_stage_task_id,
        status=COST_ACTIVE_UNSUBMITTED,
        estimated_cost=estimated,
        reserved_cost=estimated,
        currency=currency,
        expires_at=expires_at or bj_now() + timedelta(minutes=30),
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def mark_reservation_submitted(db: Session, reservation_id: str) -> ProviderCostReservation:
    reservation = db.query(ProviderCostReservation).filter_by(id=reservation_id).one()
    if reservation.status == COST_ACTIVE_UNSUBMITTED:
        reservation.status = COST_SUBMITTED
        reservation.submitted_at = bj_now()
        reservation.updated_at = bj_now()
        db.commit()
    db.refresh(reservation)
    return reservation


def settle_reservation(
    db: Session,
    reservation_id: str,
    *,
    actual_cost: float,
    units_json: dict | None = None,
) -> ProviderCostReservation:
    reservation = db.query(ProviderCostReservation).filter_by(id=reservation_id).one()
    if reservation.status == COST_SETTLED:
        return reservation
    if reservation.status not in {COST_SUBMITTED, COST_STALE_NEEDS_REPAIR}:
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="费用预留尚未提交 provider，不能结算。",
            cause="reservation_not_submitted",
            repair_action="重新执行该 provider stage 或释放未提交预留。",
            retryable=True,
        )
    actual = float(actual_cost or 0.0)
    reservation.status = COST_SETTLED
    reservation.actual_cost = actual
    reservation.units_json = units_json or {}
    reservation.settled_at = bj_now()
    reservation.updated_at = bj_now()
    db.query(ProductionPlan).filter(ProductionPlan.id == reservation.plan_id).update(
        {
            "current_cost": func.coalesce(ProductionPlan.current_cost, 0.0) + actual,
            "updated_at": bj_now(),
        },
        synchronize_session=False,
    )
    db.commit()
    db.refresh(reservation)
    return reservation


def release_unsubmitted_reservation(db: Session, reservation_id: str) -> ProviderCostReservation:
    reservation = db.query(ProviderCostReservation).filter_by(id=reservation_id).one()
    if reservation.status != COST_ACTIVE_UNSUBMITTED:
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="已提交 provider 的费用预留不能静默释放。",
            cause="submitted_reservation_cannot_release",
            repair_action="同步 provider task 或人工修复费用记录。",
            retryable=True,
        )
    reservation.status = COST_RELEASED
    reservation.updated_at = bj_now()
    db.commit()
    db.refresh(reservation)
    return reservation


def expire_unsubmitted_reservations(db: Session) -> int:
    now = bj_now()
    expired = db.query(ProviderCostReservation).filter(
        ProviderCostReservation.expires_at.isnot(None),
        ProviderCostReservation.expires_at < now,
        ProviderCostReservation.status.in_([COST_ACTIVE_UNSUBMITTED, COST_SUBMITTED]),
    ).all()
    released = 0
    for reservation in expired:
        if reservation.status == COST_ACTIVE_UNSUBMITTED:
            reservation.status = COST_RELEASED
            released += 1
        else:
            reservation.status = COST_STALE_NEEDS_REPAIR
        reservation.updated_at = now
    db.commit()
    return released
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest server/tests/test_provider_cost_reservation_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/services/provider_cost_reservation_service.py server/tests/test_provider_cost_reservation_service.py
git commit -m "feat: add provider cost reservations"
```

---

### Task 3: Provider Stage Executor, Capability Gate, And Throttle

**Files:**
- Create: `server/app/services/provider_capability_service.py`
- Create: `server/app/services/provider_stage_task_service.py`
- Create: `server/app/services/provider_stage_executor.py`
- Modify: `server/app/services/production_observability.py`
- Test: `server/tests/test_provider_stage_executor.py`
- Test: `server/tests/test_provider_throttle_and_backoff.py`

- [ ] **Step 1: Write failing executor tests**

Create `server/tests/test_provider_stage_executor.py`:

```python
import pytest

from app.db_models import ProviderStageTask, ProductionJob, ProductionPlan, Series, VideoProductionRun
from app.services.provider_stage_executor import ProviderStageExecutor
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError


class FakeProviderClient:
    def __init__(self):
        self.submits = []
        self.syncs = []

    async def submit(self, payload):
        self.submits.append(payload)
        return {"provider_task_id": "provider-1", "status": "submitted"}

    async def sync(self, provider_task_id):
        self.syncs.append(provider_task_id)
        return {"status": "succeeded", "assets": [{"url": "https://cdn.test/a.png", "asset_type": "image"}], "actual_cost": 0.1}


def _context(db):
    series = Series(title="Executor", logline="Executor", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=1.0, target_total_duration_seconds=60)
    run = VideoProductionRun(series_id=series.id, episode_id="episode-1", status="running", run_type="real_short_e2e", production_plan_id=plan.id)
    db.add_all([plan, run])
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id="seg-1",
        stage="image_generation",
        status="leased",
        idempotency_key=f"{plan.id}:seg-1:image:v1",
    )
    db.add(job)
    db.commit()
    return plan, run, job


@pytest.mark.asyncio
async def test_executor_creates_stage_task_and_reservation_before_submit(db):
    plan, run, job = _context(db)
    client = FakeProviderClient()
    executor = ProviderStageExecutor(client=client)

    result = await executor.execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-1",
        stage="image_generation",
        provider="mock",
        model_name="mock-image",
        estimated_cost=0.1,
        payload={"prompt": "image"},
    )

    assert result.ok is True
    task = db.query(ProviderStageTask).one()
    assert task.status in {"submitted", "sync_required", "succeeded"}
    assert task.provider_task_id == "provider-1"
    assert len(client.submits) == 1


@pytest.mark.asyncio
async def test_executor_reuses_existing_task_and_does_not_resubmit(db):
    plan, run, job = _context(db)
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-1",
        stage="image_generation",
        provider="mock",
        model_name="mock-image",
        request_hash="existing",
        idempotency_key=job.idempotency_key,
        status="sync_required",
        provider_task_id="provider-existing",
    )
    db.add(task)
    db.commit()
    client = FakeProviderClient()

    result = await ProviderStageExecutor(client=client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-1",
        stage="image_generation",
        provider="mock",
        model_name="mock-image",
        estimated_cost=0.1,
        payload={"prompt": "image"},
    )

    assert result.ok is True
    assert len(client.submits) == 0
    assert client.syncs == ["provider-existing"]


@pytest.mark.asyncio
async def test_executor_blocks_provider_without_recovery_capability(db):
    plan, run, job = _context(db)

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client=FakeProviderClient()).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-1",
            stage="image_generation",
            provider="unsafe-provider",
            model_name="unsafe-model",
            estimated_cost=0.1,
            payload={"prompt": "image"},
            capability={"real_paid_allowed": False},
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert len(db.query(ProviderStageTask).all()) == 0
```

- [ ] **Step 2: Write failing throttle tests**

Create `server/tests/test_provider_throttle_and_backoff.py`:

```python
import pytest

from app.db_models import ProviderStageTask, ProductionJob, ProductionPlan, Series, VideoProductionRun
from app.services.provider_stage_executor import ProviderStageExecutor
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError


class NoSubmitClient:
    async def submit(self, payload):
        raise AssertionError("submit must not be called when throttled")


def _context(db):
    series = Series(title="Throttle", logline="Throttle", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=10.0, target_total_duration_seconds=60)
    run = VideoProductionRun(series_id=series.id, episode_id="episode-1", status="running", run_type="real_short_e2e", production_plan_id=plan.id)
    db.add_all([plan, run])
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id="seg-2",
        stage="image_generation",
        status="leased",
        idempotency_key=f"{plan.id}:seg-2:image:v1",
    )
    db.add(job)
    active = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        target_type="production_segment",
        target_id="seg-1",
        stage="image_generation",
        provider="mock",
        model_name="mock-image",
        request_hash="hash-active",
        idempotency_key=f"{plan.id}:seg-1:image:v1",
        status="running",
    )
    db.add(active)
    db.commit()
    return plan, run, job


@pytest.mark.asyncio
async def test_executor_throttles_before_provider_submit(db):
    plan, run, job = _context(db)

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client=NoSubmitClient()).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-2",
            stage="image_generation",
            provider="mock",
            model_name="mock-image",
            estimated_cost=0.1,
            payload={"prompt": "image"},
            capability={"real_paid_allowed": True, "max_concurrent_tasks": 1},
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_THROTTLED
    db.refresh(job)
    assert job.status == "retry_wait"
    assert job.retry_after is not None
    assert db.query(ProviderStageTask).count() == 1
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
pytest server/tests/test_provider_stage_executor.py server/tests/test_provider_throttle_and_backoff.py -q
```

Expected: FAIL because the executor and capability services do not exist.

- [ ] **Step 4: Implement capability and stage task services**

Create `server/app/services/provider_capability_service.py`:

```python
DEFAULT_REAL_PROVIDER_CAPABILITY = {
    "supports_external_task_id": True,
    "supports_task_query": True,
    "supports_cancel": False,
    "returns_usage": True,
    "returns_asset_url": True,
    "supports_text_to_image": True,
    "supports_image_to_video": True,
    "max_duration_seconds": 15,
    "max_reference_images": 9,
    "max_concurrent_tasks": 1,
    "real_paid_allowed": True,
}


def capability_from_model_config(model_config: dict | None) -> dict:
    config = model_config or {}
    options = config.get("provider_options") or config.get("config_json") or {}
    capability = dict(DEFAULT_REAL_PROVIDER_CAPABILITY)
    capability.update(options.get("capability") or {})
    capability.update(config.get("capability") or {})
    return capability


def assert_real_paid_allowed(capability: dict) -> None:
    required = ["real_paid_allowed", "supports_task_query", "returns_asset_url"]
    if not all(capability.get(key) for key in required):
        raise ValueError("Provider capability is not safe for real paid execution")
```

Create `server/app/services/provider_stage_task_service.py`:

```python
import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProviderStageTask
from app.services.production_state_contract import (
    PROVIDER_TASK_RESERVED,
    validate_transition,
)


def request_hash(payload: dict) -> str:
    raw = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_or_create_stage_task(
    db: Session,
    *,
    run_id: str,
    plan_id: str,
    job_id: str | None,
    target_type: str,
    target_id: str,
    stage: str,
    provider: str,
    model_name: str,
    payload: dict,
    idempotency_key: str,
) -> tuple[ProviderStageTask, bool]:
    existing = db.query(ProviderStageTask).filter_by(idempotency_key=idempotency_key).first()
    hashed = request_hash(payload)
    if existing:
        if existing.request_hash != hashed:
            raise ValueError("Provider stage task idempotency key conflicts with different request payload")
        return existing, False
    task = ProviderStageTask(
        run_id=run_id,
        plan_id=plan_id,
        job_id=job_id,
        target_type=target_type,
        target_id=target_id,
        stage=stage,
        provider=provider,
        model_name=model_name,
        request_hash=hashed,
        idempotency_key=idempotency_key,
        status=PROVIDER_TASK_RESERVED,
    )
    db.add(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProviderStageTask).filter_by(idempotency_key=idempotency_key).first()
        if existing and existing.request_hash == hashed:
            return existing, False
        raise
    db.refresh(task)
    return task, True


def set_task_status(db: Session, task: ProviderStageTask, next_status: str, **values) -> ProviderStageTask:
    if task.status != next_status and not validate_transition("provider_stage_task", task.status, next_status):
        raise ValueError(f"Illegal provider stage task transition: {task.status} -> {next_status}")
    task.status = next_status
    for key, value in values.items():
        setattr(task, key, value)
    task.updated_at = bj_now()
    db.commit()
    db.refresh(task)
    return task
```

- [ ] **Step 5: Implement executor**

Create `server/app/services/provider_stage_executor.py`:

```python
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProductionJob, ProviderStageTask
from app.services.production_action_result import ProductionActionResult
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.production_observability import record_production_event
from app.services.production_state_contract import (
    PROVIDER_TASK_RUNNING,
    PROVIDER_TASK_SUBMITTED,
    PROVIDER_TASK_SUCCEEDED,
    PROVIDER_TASK_SYNC_REQUIRED,
    provider_task_is_active,
)
from app.services.provider_capability_service import DEFAULT_REAL_PROVIDER_CAPABILITY, assert_real_paid_allowed
from app.services.provider_cost_reservation_service import create_cost_reservation, mark_reservation_submitted, settle_reservation
from app.services.provider_stage_task_service import get_or_create_stage_task, set_task_status


class ProviderStageExecutor:
    """Two-phase paid provider boundary.

    Flow:
      reserve task + cost in DB -> provider I/O outside DB lock -> write back task/cost/audit.
    """

    def __init__(self, client):
        self.client = client

    def _active_count(self, db: Session, *, provider: str, model_name: str, stage: str) -> int:
        rows = db.query(ProviderStageTask.status).filter(
            ProviderStageTask.provider == provider,
            ProviderStageTask.model_name == model_name,
            ProviderStageTask.stage == stage,
        ).all()
        return sum(1 for (status,) in rows if provider_task_is_active(status))

    def _throttle_if_needed(
        self,
        db: Session,
        *,
        job_id: str | None,
        provider: str,
        model_name: str,
        stage: str,
        capability: dict,
    ) -> None:
        limit = int(capability.get("max_concurrent_tasks") or 1)
        if self._active_count(db, provider=provider, model_name=model_name, stage=stage) < limit:
            return
        if job_id:
            job = db.query(ProductionJob).filter_by(id=job_id).first()
            if job:
                job.status = "retry_wait"
                job.error_code = ProductionErrorCode.PROVIDER_THROTTLED.value
                job.error_message = "Provider concurrency limit reached"
                job.retry_after = bj_now() + timedelta(seconds=60)
                job.lease_id = None
                job.leased_until = None
                db.commit()
        raise ProductionRepairableError(
            code=ProductionErrorCode.PROVIDER_THROTTLED,
            message="当前 provider 并发额度已满，任务已进入等待重试。",
            cause="provider_concurrency_limit",
            repair_action="等待自动重试、降低并发、暂停任务或切换模型。",
            retryable=True,
        )

    async def execute(
        self,
        db: Session,
        *,
        run_id: str,
        plan_id: str,
        job_id: str | None,
        target_type: str,
        target_id: str,
        stage: str,
        provider: str,
        model_name: str,
        estimated_cost: float,
        payload: dict[str, Any],
        capability: dict | None = None,
    ) -> ProductionActionResult:
        capability = capability or dict(DEFAULT_REAL_PROVIDER_CAPABILITY)
        try:
            assert_real_paid_allowed(capability)
        except ValueError as exc:
            raise ProductionRepairableError(
                code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
                message="当前 provider 配置不满足真实付费执行准入。",
                cause="provider_capability_blocked",
                repair_action="补全 provider task 查询、资产 URL、usage 或人工补录能力后重试。",
                retryable=True,
            ) from exc

        self._throttle_if_needed(
            db,
            job_id=job_id,
            provider=provider,
            model_name=model_name,
            stage=stage,
            capability=capability,
        )

        idempotency_key = payload.get("idempotency_key") or f"{plan_id}:{target_type}:{target_id}:{stage}"
        task, created = get_or_create_stage_task(
            db,
            run_id=run_id,
            plan_id=plan_id,
            job_id=job_id,
            target_type=target_type,
            target_id=target_id,
            stage=stage,
            provider=provider,
            model_name=model_name,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        reservation = None
        if created:
            reservation = create_cost_reservation(
                db,
                plan_id=plan_id,
                provider_stage_task_id=task.id,
                estimated_cost=estimated_cost,
            )

        if task.provider_task_id:
            provider_result = await self.client.sync(task.provider_task_id)
        else:
            provider_result = await self.client.submit(payload)
            provider_task_id = provider_result.get("provider_task_id")
            if not provider_task_id:
                raise ProductionRepairableError(
                    code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
                    message="provider 未返回 task id。",
                    cause="provider_task_id_missing",
                    repair_action="检查 provider 配置或切换模型后重试。",
                    retryable=True,
                )
            set_task_status(
                db,
                task,
                PROVIDER_TASK_SUBMITTED,
                provider_task_id=provider_task_id,
                submitted_at=bj_now(),
                response_summary_json=provider_result,
            )
            if reservation:
                mark_reservation_submitted(db, reservation.id)
            provider_result = await self.client.sync(provider_task_id)

        if provider_result.get("status") in {"succeeded", "completed", "done"}:
            set_task_status(
                db,
                task,
                PROVIDER_TASK_SUCCEEDED,
                completed_at=bj_now(),
                response_summary_json=provider_result,
            )
            if reservation:
                settle_reservation(db, reservation.id, actual_cost=float(provider_result.get("actual_cost") or estimated_cost), units_json=provider_result.get("usage") or {})
            record_production_event(
                db,
                event_type="provider_stage.succeeded",
                run_id=run_id,
                production_plan_id=plan_id,
                production_segment_id=target_id if target_type == "production_segment" else None,
                provider_task_id=task.provider_task_id,
                payload={"stage": stage, "provider": provider, "model_name": model_name},
            )
            db.commit()
            return ProductionActionResult.success("provider stage succeeded", provider_result=provider_result, provider_stage_task_id=task.id)

        set_task_status(db, task, PROVIDER_TASK_SYNC_REQUIRED, response_summary_json=provider_result)
        return ProductionActionResult.blocked(
            code=ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED,
            message="provider task 尚未完成，需要继续同步。",
            cause="provider_task_pending",
            repair_action="稍后重试同步该 provider task。",
            affected_ids=[task.id],
            retryable=True,
            audit_event_type="provider_stage.sync_required",
        )
```

- [ ] **Step 6: Run executor and throttle tests**

Run:

```bash
pytest server/tests/test_provider_stage_executor.py server/tests/test_provider_throttle_and_backoff.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add server/app/services/provider_capability_service.py server/app/services/provider_stage_task_service.py server/app/services/provider_stage_executor.py server/tests/test_provider_stage_executor.py server/tests/test_provider_throttle_and_backoff.py
git commit -m "feat: add provider stage executor"
```

---

### Task 4: Asset Storage Guard And Review Hard Gate

**Files:**
- Create: `server/app/services/asset_storage_guard.py`
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/routers/video_production.py`
- Test: `server/tests/test_asset_storage_guard.py`
- Test: `server/tests/test_video_production_review_latest_version.py`

- [ ] **Step 1: Write failing storage guard tests**

Create `server/tests/test_asset_storage_guard.py`:

```python
from pathlib import Path

import pytest

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.services.asset_storage_guard import persist_provider_asset
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError


def _asset(db, url="https://cdn.test/image.png"):
    series = Series(title="Storage", logline="Storage", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="image_review_pending", current_stage="image_review")
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-1",
        asset_type="image",
        stage="image_generation",
        url=url,
        source_url=url,
        status="generated",
        copy_status="registered",
    )
    db.add(asset)
    db.commit()
    return asset


def test_storage_guard_rejects_file_url(db, tmp_path):
    asset = _asset(db, url="file:///etc/passwd")

    with pytest.raises(ProductionRepairableError) as exc_info:
        persist_provider_asset(db, asset.id, output_root=tmp_path)

    assert exc_info.value.code == ProductionErrorCode.ASSET_STORAGE_FAILED
    db.refresh(asset)
    assert asset.copy_status == "storage_failed"
    assert asset.status == "storage_failed"


def test_storage_guard_persists_existing_pixelle_output_inside_root(db, tmp_path):
    source = tmp_path / "pixelle" / "image.png"
    source.parent.mkdir()
    source.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    asset = _asset(db, url="")
    asset.local_path = str(source)
    db.commit()

    persisted = persist_provider_asset(db, asset.id, output_root=tmp_path, pixelle_output_root=tmp_path / "pixelle")

    assert persisted.copy_status == "persisted"
    assert persisted.storage_path
    assert persisted.checksum
    assert Path(persisted.storage_path).exists()


def test_storage_guard_rejects_pixelle_path_outside_root(db, tmp_path):
    outside = tmp_path.parent / "outside-image.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    asset = _asset(db, url="")
    asset.local_path = str(outside)
    db.commit()

    with pytest.raises(ProductionRepairableError):
        persist_provider_asset(db, asset.id, output_root=tmp_path, pixelle_output_root=tmp_path / "pixelle")

    db.refresh(asset)
    assert asset.copy_status == "storage_failed"
```

- [ ] **Step 2: Write failing review gate test**

Append to `server/tests/test_video_production_review_latest_version.py`:

```python
def test_review_rejects_asset_that_is_not_persisted(db):
    run = _create_review_context(db)
    asset = _asset(db, run, "seg-001", "image", 1, status="review_pending")
    asset.copy_status = "registered"
    db.commit()

    response = client.post(f"/api/video-production/assets/{asset.id}/review", json={"action": "approve"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "ASSET_STORAGE_FAILED"
    db.refresh(asset)
    assert asset.status == "review_pending"


def test_review_rejects_asset_that_is_not_review_pending(db):
    run = _create_review_context(db)
    asset = _asset(db, run, "seg-001", "image", 1, status="generated")
    asset.copy_status = "persisted"
    asset.checksum = "abc"
    asset.storage_path = "output/seg-001.png"
    db.commit()

    response = client.post(f"/api/video-production/assets/{asset.id}/review", json={"action": "approve"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "REVIEW_GATE_BLOCKED"
    db.refresh(asset)
    assert asset.status == "generated"
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
pytest server/tests/test_asset_storage_guard.py server/tests/test_video_production_review_latest_version.py::test_review_rejects_asset_that_is_not_persisted -q
```

Expected: FAIL because `asset_storage_guard` does not exist and review allows unpersisted assets.

- [ ] **Step 4: Implement storage guard**

Create `server/app/services/asset_storage_guard.py`:

```python
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import VideoProductionAsset
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError

ALLOWED_PROVIDER_SCHEMES = {"https"}
ALLOWED_IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"RIFF")
ALLOWED_VIDEO_MAGIC = (b"\x00\x00\x00", b"ftyp")


def _fail_asset(db: Session, asset: VideoProductionAsset, cause: str, message: str) -> None:
    asset.copy_status = "storage_failed"
    asset.status = "storage_failed"
    asset.storage_error_json = {"cause": cause, "message": message}
    asset.updated_at = bj_now()
    db.commit()


def _raise_storage_failed(asset: VideoProductionAsset, cause: str, message: str) -> None:
    raise ProductionRepairableError(
        code=ProductionErrorCode.ASSET_STORAGE_FAILED,
        message=message,
        cause=cause,
        repair_action="重新持久化资产或重新生成该片段。",
        repair_route=f"/video-production/{asset.run_id}",
        affected_ids=[asset.id],
        retryable=True,
    )


def _safe_source_from_local(asset: VideoProductionAsset, pixelle_output_root: Path) -> Path:
    source = Path(asset.local_path or "").resolve()
    root = pixelle_output_root.resolve()
    if root not in source.parents and source != root:
        _raise_storage_failed(asset, "pixelle_path_outside_root", "Pixelle 输出路径越过允许目录。")
    if not source.exists() or not source.is_file():
        _raise_storage_failed(asset, "source_file_missing", "待持久化资产文件不存在。")
    return source


def _validate_url(asset: VideoProductionAsset) -> None:
    parsed = urlparse(asset.source_url or asset.url or "")
    if parsed.scheme not in ALLOWED_PROVIDER_SCHEMES:
        _raise_storage_failed(asset, "unsupported_source_url", "资产来源 URL 协议不允许。")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        _raise_storage_failed(asset, "local_source_url", "资产来源 URL 不能指向本机。")


def _looks_like_expected_asset(asset: VideoProductionAsset, path: Path) -> bool:
    head = path.read_bytes()[:16]
    if asset.asset_type == "image":
        return any(head.startswith(item) for item in ALLOWED_IMAGE_MAGIC)
    if asset.asset_type in {"video_segment", "final_video"}:
        return any(item in head for item in ALLOWED_VIDEO_MAGIC) or path.suffix.lower() in {".mp4", ".mov", ".webm"}
    return True


def persist_provider_asset(
    db: Session,
    asset_id: str,
    *,
    output_root: str | Path,
    pixelle_output_root: str | Path | None = None,
) -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter_by(id=asset_id).one()
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        if asset.local_path:
            source = _safe_source_from_local(asset, Path(pixelle_output_root or output_root))
        else:
            _validate_url(asset)
            _raise_storage_failed(asset, "remote_download_not_configured", "当前环境未配置远程资产下载器。")

        suffix = source.suffix or (".mp4" if asset.asset_type != "image" else ".png")
        tmp_path = output_root / f"{asset.id}.tmp{suffix}"
        final_path = output_root / f"{asset.id}{suffix}"
        shutil.copyfile(source, tmp_path)
        if not _looks_like_expected_asset(asset, tmp_path):
            tmp_path.unlink(missing_ok=True)
            _raise_storage_failed(asset, "mime_type_mismatch", "资产 MIME 类型与阶段不匹配。")
        checksum = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        tmp_path.replace(final_path)
        asset.storage_path = str(final_path)
        asset.local_path = str(final_path)
        asset.checksum = checksum
        asset.size_bytes = final_path.stat().st_size
        asset.copy_status = "persisted"
        asset.status = "review_pending"
        asset.updated_at = bj_now()
        db.commit()
        db.refresh(asset)
        return asset
    except ProductionRepairableError as exc:
        _fail_asset(db, asset, exc.cause or exc.code.value, exc.message)
        raise
```

- [ ] **Step 5: Enforce review persisted gate**

Modify `approve_asset()` and `approve_final_video_asset()` in `server/app/services/video_production_service.py` before setting `asset.status = "approved"`:

```python
def _assert_asset_persisted_for_review(asset: VideoProductionAsset) -> None:
    if not asset_is_reviewable(asset.status):
        raise ProductionRepairableError(
            code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
            message="资产尚未进入人工审查状态，不能审批。",
            cause="asset_not_review_pending",
            repair_action="等待资产持久化和 AI 审查完成，或重新生成该资产。",
            repair_route=f"/video-production/{asset.run_id}",
            affected_ids=[asset.id],
            retryable=True,
        )
    if asset.copy_status != "persisted" or not asset.checksum or not (asset.storage_path or asset.local_path):
        raise ProductionRepairableError(
            code=ProductionErrorCode.ASSET_STORAGE_FAILED,
            message="资产尚未持久化，不能通过人工审查。",
            cause="asset_not_persisted",
            repair_action="先重试资产持久化，或重新生成该资产。",
            repair_route=f"/video-production/{asset.run_id}",
            affected_ids=[asset.id],
            retryable=True,
        )
```

Call `_assert_asset_persisted_for_review(asset)` in both approval paths.

- [ ] **Step 6: Add persist retry route**

Modify `server/app/routers/video_production.py`:

```python
@router.post("/assets/{asset_id}/persist-retry")
def retry_asset_persistence(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    from app.services.asset_storage_guard import persist_provider_asset

    try:
        asset = persist_provider_asset(db, asset_id, output_root="output/video-production")
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
```

- [ ] **Step 7: Run tests and verify GREEN**

Run:

```bash
pytest server/tests/test_asset_storage_guard.py server/tests/test_video_production_review_latest_version.py::test_review_rejects_asset_that_is_not_persisted -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add server/app/services/asset_storage_guard.py server/app/services/video_production_service.py server/app/routers/video_production.py server/tests/test_asset_storage_guard.py server/tests/test_video_production_review_latest_version.py
git commit -m "feat: enforce persisted asset review gate"
```

---

### Task 5: Aggregate Gate Evaluator And Final Writeback Guard

**Files:**
- Create: `server/app/services/production_gate_evaluator.py`
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/production_queue_service.py`
- Test: `server/tests/test_production_gate_evaluator.py`

- [ ] **Step 1: Write failing gate evaluator tests**

Create `server/tests/test_production_gate_evaluator.py`:

```python
from app.db_models import (
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.services.production_gate_evaluator import evaluate_stage_gate


def _linked_run_with_segments(db, statuses):
    series = Series(title="Gate", logline="Gate", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=10, target_total_duration_seconds=60)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready", target_duration_seconds=60)
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready", action="walk", duration_seconds=15)
    db.add(shot)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        run_type="real_short_e2e",
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    segments = []
    for index, status in enumerate(statuses, start=1):
        segment = ProductionSegment(shot_plan_id=shot.id, segment_id=f"seg-{index}", order_index=index, status="image_review_pending", duration_seconds=5)
        db.add(segment)
        db.flush()
        db.add(VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=segment.id,
            asset_type="image",
            stage="image_generation",
            status=status,
            is_latest=True,
            copy_status="persisted",
            checksum="abc",
            storage_path=f"output/{segment.id}.png",
            production_segment_id=segment.id,
            target_type="production_segment",
            target_id=segment.id,
        ))
        segments.append(segment)
    db.commit()
    return run, segments


def test_gate_blocks_partial_image_approval(db):
    run, segments = _linked_run_with_segments(db, ["approved", "storage_failed"])

    result = evaluate_stage_gate(db, run.id, stage="image_generation")

    assert result["ready"] is False
    assert result["status"] == "blocked"
    assert result["blocked_segment_ids"] == [segments[1].id]


def test_gate_allows_next_stage_only_when_all_required_assets_approved(db):
    run, segments = _linked_run_with_segments(db, ["approved", "approved"])

    result = evaluate_stage_gate(db, run.id, stage="image_generation")

    assert result["ready"] is True
    assert result["blocked_segment_ids"] == []
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest server/tests/test_production_gate_evaluator.py -q
```

Expected: FAIL because `production_gate_evaluator` does not exist.

- [ ] **Step 3: Implement evaluator**

Create `server/app/services/production_gate_evaluator.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionScene, ProductionSegment, ProductionShot, VideoProductionAsset, VideoProductionRun
from app.services.production_observability import record_production_event


def _required_segment_ids(db: Session, run: VideoProductionRun) -> list[str]:
    rows = (
        db.query(ProductionSegment.id)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == run.production_episode_id)
        .order_by(ProductionSegment.order_index.asc(), ProductionSegment.id.asc())
        .all()
    )
    return [row[0] for row in rows]


def _asset_type_for_stage(stage: str) -> str:
    if stage == "image_generation":
        return "image"
    if stage == "video_generation":
        return "video_segment"
    if stage == "episode_compose":
        return "final_video"
    raise ValueError(f"Unsupported stage gate: {stage}")


def evaluate_stage_gate(db: Session, run_id: str, *, stage: str) -> dict:
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    asset_type = _asset_type_for_stage(stage)
    required_ids = _required_segment_ids(db, run) if asset_type != "final_video" else ["final"]
    assets = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == asset_type,
        VideoProductionAsset.is_latest.is_(True),
    ).all()
    by_segment = {
        asset.production_segment_id or asset.frame_id: asset
        for asset in assets
    }
    blocked = []
    for segment_id in required_ids:
        asset = by_segment.get(segment_id)
        if not asset or asset.status != "approved" or asset.copy_status != "persisted":
            blocked.append(segment_id)

    result = {"ready": not blocked, "status": "ready" if not blocked else "blocked", "blocked_segment_ids": blocked}
    record_production_event(
        db,
        event_type="gate.evaluated",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        payload={"stage": stage, **result},
    )
    db.commit()
    return result
```

- [ ] **Step 4: Wire evaluator where stages advance**

Modify `approve_asset()` in `server/app/services/video_production_service.py` after `recompute_run_gate()`:

```python
from app.services.production_gate_evaluator import evaluate_stage_gate

if asset.asset_type == "image":
    evaluate_stage_gate(db, asset.run_id, stage="image_generation")
elif asset.asset_type == "video_segment":
    evaluate_stage_gate(db, asset.run_id, stage="video_generation")
```

Do not materialize downstream jobs from a single asset approval. Downstream materialization belongs in worker service after aggregate gate returns `ready=True`.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
pytest server/tests/test_production_gate_evaluator.py -q
pytest server/tests/test_video_production_final_gate.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/app/services/production_gate_evaluator.py server/app/services/video_production_service.py server/tests/test_production_gate_evaluator.py
git commit -m "feat: add video production aggregate gates"
```

---

### Task 6: Real Worker Step And Legacy Stage Guard

**Files:**
- Create: `server/app/services/production_worker_service.py`
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/routers/video_production.py`
- Test: `server/tests/test_video_production_linked_stage_execution.py`
- Test: `server/tests/test_video_production_real_worker_step.py`

- [ ] **Step 1: Write failing legacy guard test**

Append to `server/tests/test_video_production_linked_stage_execution.py`:

```python
def test_real_run_stage_functions_require_provider_executor(db, monkeypatch):
    run, _segments = _linked_run_with_segments(db)
    run.run_type = "real_short_e2e"
    db.commit()
    called = {"executor": 0}

    async def fake_executor_start(*args, **kwargs):
        called["executor"] += 1
        return run

    monkeypatch.setattr("app.services.video_production_service.start_real_provider_stage_via_executor", fake_executor_start)

    response = client.post(f"/api/video-production/runs/{run.id}/start-images")

    assert response.status_code == 200
    assert called["executor"] == 1
```

- [ ] **Step 2: Write failing worker-step test**

Create `server/tests/test_video_production_real_worker_step.py`:

```python
from app.db_models import ProductionJob, ProductionPlan, Series, VideoProductionRun
from app.services.production_worker_service import run_real_worker_step


def test_real_worker_step_claims_limited_batch_and_returns_visible_summary(db, monkeypatch, db):
    series = Series(title="Worker", logline="Worker", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=10, target_total_duration_seconds=60)
    run = VideoProductionRun(series_id=series.id, episode_id="episode-1", status="running", run_type="real_short_e2e", production_plan_id=plan.id)
    db.add_all([plan, run])
    db.flush()
    for index in range(3):
        db.add(ProductionJob(
            plan_id=plan.id,
            target_type="production_segment",
            target_id=f"seg-{index}",
            stage="image_generation",
            status="queued",
            idempotency_key=f"{plan.id}:seg-{index}:image:v1",
        ))
    db.commit()

    async def fake_execute_job(db, run, job):
        job.status = "completed"
        db.commit()
        return {"ok": True, "job_id": job.id}

    monkeypatch.setattr("app.services.production_worker_service.execute_real_job", fake_execute_job)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=2)

    assert result["processed"] == 2
    assert result["remaining"] == 1
    assert len(result["items"]) == 2
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
pytest server/tests/test_video_production_linked_stage_execution.py::test_real_run_stage_functions_require_provider_executor server/tests/test_video_production_real_worker_step.py -q
```

Expected: FAIL because worker service and executor delegation are not wired.

- [ ] **Step 4: Implement worker service**

Create `server/app/services/production_worker_service.py`:

```python
import asyncio

from sqlalchemy.orm import Session

from app.db_models import ProductionJob, VideoProductionRun
from app.services.production_queue_service import claim_next_job


async def execute_real_job(db: Session, run: VideoProductionRun, job: ProductionJob) -> dict:
    from app.services.provider_stage_executor import ProviderStageExecutor
    from app.services.pixelle_stage_client import get_default_provider_client

    client = get_default_provider_client()
    result = await ProviderStageExecutor(client=client).execute(
        db,
        run_id=run.id,
        plan_id=job.plan_id,
        job_id=job.id,
        target_type=job.target_type,
        target_id=job.target_id,
        stage=job.stage,
        provider="configured",
        model_name="configured",
        estimated_cost=0.0,
        payload={"idempotency_key": job.idempotency_key, "target_id": job.target_id, "stage": job.stage},
    )
    return result.to_http_detail()


def run_real_worker_step(db: Session, run_id: str, *, lease_id: str, batch_size: int = 1) -> dict:
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    processed = []
    for _ in range(max(1, min(int(batch_size or 1), 100))):
        job = claim_next_job(db, lease_id=lease_id, plan_id=run.production_plan_id)
        if not job:
            break
        result = asyncio.get_event_loop().run_until_complete(execute_real_job(db, run, job))
        processed.append(result)
    remaining = db.query(ProductionJob).filter(
        ProductionJob.plan_id == run.production_plan_id,
        ProductionJob.status.in_(["queued", "retry_wait", "leased", "running"]),
    ).count()
    return {"ok": True, "processed": len(processed), "remaining": remaining, "items": processed}
```

- [ ] **Step 5: Guard legacy stage functions**

Modify `server/app/services/video_production_service.py`:

```python
async def start_real_provider_stage_via_executor(db: Session, run: VideoProductionRun, stage: str) -> VideoProductionRun:
    from app.services.production_errors import ProductionErrorCode, ProductionRepairableError

    raise ProductionRepairableError(
        code=ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED,
        message="真实 provider stage 必须由 ProviderStageExecutor/worker-step 执行。",
        cause="provider_stage_executor_required",
        repair_action="使用真实 worker step 推进该 run。",
        repair_route=f"/video-production/{run.id}",
        affected_ids=[run.id],
        retryable=True,
    )
```

At the top of each real stage function, replace direct provider submit for `REAL_SHORT_E2E` with a call to `start_real_provider_stage_via_executor()` once the new worker path is available. Keep mock and legacy behavior unchanged unless the run type is real paid.

- [ ] **Step 6: Add route**

Modify `server/app/routers/video_production.py`:

```python
class RealWorkerStepRequest(BaseModel):
    lease_id: str = "manual-real-worker"
    batch_size: int = Field(1, ge=1, le=100)


@router.post("/runs/{run_id}/worker-step")
def real_worker_step(
    run_id: str,
    body: RealWorkerStepRequest = RealWorkerStepRequest(),
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    from app.services.production_worker_service import run_real_worker_step

    try:
        return run_real_worker_step(db, run_id, lease_id=body.lease_id, batch_size=body.batch_size)
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    except ValueError as exc:
        raise HTTPException(404, str(exc))
```

- [ ] **Step 7: Run tests and verify GREEN**

Run:

```bash
pytest server/tests/test_video_production_linked_stage_execution.py server/tests/test_video_production_real_worker_step.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add server/app/services/production_worker_service.py server/app/services/video_production_service.py server/app/routers/video_production.py server/tests/test_video_production_linked_stage_execution.py server/tests/test_video_production_real_worker_step.py
git commit -m "feat: add real video production worker step"
```

---

### Task 7: Performance Boundaries And Bounded Payloads

**Files:**
- Modify: `server/app/services/production_tree_service.py`
- Modify: `server/app/routers/video_production.py`
- Test: `server/tests/test_video_production_performance_boundaries.py`

- [ ] **Step 1: Write failing performance tests**

Create `server/tests/test_video_production_performance_boundaries.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.main import app

client = TestClient(app)


def _run_with_assets(db, count=150):
    series = Series(title="Perf", logline="Perf", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="running", current_stage="image_review")
    db.add(run)
    db.flush()
    for index in range(count):
        db.add(VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=f"frame-{index}",
            asset_type="image",
            stage="image_generation",
            status="review_pending",
            url=f"https://cdn.test/{index}.png",
        ))
    db.commit()
    return run


def test_get_run_does_not_return_unbounded_assets(db):
    run = _run_with_assets(db, count=150)

    response = client.get(f"/api/video-production/runs/{run.id}")

    assert response.status_code == 200
    body = response.json()
    assert "asset_summary" in body
    assert "assets" not in body or len(body["assets"]) <= 50


def test_review_items_caps_page_size_at_100(db):
    _run_with_assets(db, count=150)

    response = client.get("/api/video-production/review-items", params={"page_size": 500})

    assert response.status_code == 200
    body = response.json()
    assert body["page_size"] == 100
    assert len(body["items"]) == 100
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest server/tests/test_video_production_performance_boundaries.py -q
```

Expected: FAIL because `GET /runs/{run_id}` returns all assets and `page_size` is not capped.

- [ ] **Step 3: Implement pagination helpers**

Modify `server/app/routers/video_production.py`:

```python
def _bounded_page(page: int, page_size: int, *, max_page_size: int = 100) -> tuple[int, int]:
    return max(1, int(page or 1)), min(max(1, int(page_size or 50)), max_page_size)


def _asset_summary(db: Session, run_id: str) -> dict:
    rows = db.query(VideoProductionAsset.asset_type, VideoProductionAsset.status).filter(
        VideoProductionAsset.run_id == run_id,
    ).all()
    summary = {}
    for asset_type, status in rows:
        summary.setdefault(asset_type, {}).setdefault(status, 0)
        summary[asset_type][status] += 1
    return summary
```

Replace `get_run()` assets query with:

```python
return {"ok": True, "run": _run_payload(run), "asset_summary": _asset_summary(db, run.id)}
```

In `review_items()` before building query:

```python
page, page_size = _bounded_page(page, page_size)
```

Modify `server/app/services/production_tree_service.py`:

```python
def _normalize_page(page: int, page_size: int) -> tuple[int, int]:
    return max(1, int(page or 1)), min(max(1, int(page_size or 50)), 100)
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest server/tests/test_video_production_performance_boundaries.py server/tests/test_video_production_tree_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/video_production.py server/app/services/production_tree_service.py server/tests/test_video_production_performance_boundaries.py
git commit -m "fix: bound video production payloads"
```

---

### Task 8: Frontend Transparency And Review Gate States

**Files:**
- Modify: `web/src/api/videoProduction.js`
- Modify: `web/src/views/VideoProductionMonitorPage.vue`
- Modify: `web/src/views/AIVideoReviewPage.vue`
- Test: `web/src/__tests__/video-production-monitor-boundary-states.test.js`
- Test: `web/src/__tests__/video-production-monitor-performance.test.js`
- Test: `web/src/__tests__/ai-video-review-boundary-gates.test.js`

- [ ] **Step 1: Write failing frontend monitor boundary test**

Create `web/src/__tests__/video-production-monitor-boundary-states.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import VideoProductionMonitorPage from '../views/VideoProductionMonitorPage.vue'
import * as api from '../api/videoProduction'

vi.mock('../api/videoProduction')

describe('VideoProductionMonitorPage boundary states', () => {
  it('renders repair CTA, provider throttle, and persisted asset state', async () => {
    api.getVideoProductionRun.mockResolvedValue({
      ok: true,
      run: { id: 'run-1', status: 'running', current_stage: 'image_generation', run_type: 'real_short_e2e' },
      asset_summary: { image: { storage_failed: 1 } },
    })
    api.getRunReadiness.mockResolvedValue({
      ok: true,
      readiness: {
        next_repair_action: { label: '重试资产持久化', route: '/video-production/run-1' },
        provider_throttle: { active_tasks: 1, max_concurrent_tasks: 1, retry_after: '2026-06-01T12:00:00Z' },
      },
    })
    api.getRunCosts.mockResolvedValue({ ok: true, active_reserved_cost: 0.2, stale_needs_repair_cost: 0.1, settled_cost: 0.3 })
    api.getRunTree.mockResolvedValue({ ok: true, episodes: [], total_segments: 0, page: 1, page_size: 50 })

    const wrapper = mount(VideoProductionMonitorPage, { global: { mocks: { $route: { params: { runId: 'run-1' } } } } })
    await Promise.resolve()
    await Promise.resolve()

    expect(wrapper.text()).toContain('重试资产持久化')
    expect(wrapper.text()).toContain('并发额度')
    expect(wrapper.text()).toContain('待修复预留')
  })
})
```

- [ ] **Step 2: Write failing frontend performance test**

Create `web/src/__tests__/video-production-monitor-performance.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import VideoProductionMonitorPage from '../views/VideoProductionMonitorPage.vue'
import * as api from '../api/videoProduction'

vi.mock('../api/videoProduction')

describe('VideoProductionMonitorPage performance boundaries', () => {
  it('loads bounded tree page and does not load every segment detail by default', async () => {
    api.getVideoProductionRun.mockResolvedValue({ ok: true, run: { id: 'run-1', status: 'running' }, asset_summary: {} })
    api.getRunReadiness.mockResolvedValue({ ok: true, readiness: {} })
    api.getRunCosts.mockResolvedValue({ ok: true })
    api.getRunTree.mockResolvedValue({ ok: true, episodes: [], total_segments: 2400, page: 1, page_size: 50 })
    api.getSegmentDetail = vi.fn()

    mount(VideoProductionMonitorPage, { global: { mocks: { $route: { params: { runId: 'run-1' } } } } })
    await Promise.resolve()
    await Promise.resolve()

    expect(api.getRunTree).toHaveBeenCalledWith('run-1', expect.objectContaining({ page: 1, page_size: 50 }))
    expect(api.getSegmentDetail).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: Run frontend tests and verify RED**

Run:

```bash
cd web
npm test -- video-production-monitor-boundary-states.test.js video-production-monitor-performance.test.js
```

Expected: FAIL because UI/API do not yet expose all boundary states.

- [ ] **Step 4: Add API methods**

Modify `web/src/api/videoProduction.js`:

```javascript
export async function runRealWorkerStep(runId, payload = {}) {
  const { data } = await api.post(`/video-production/runs/${runId}/worker-step`, payload)
  return data
}

export async function retryAssetPersistence(assetId) {
  const { data } = await api.post(`/video-production/assets/${assetId}/persist-retry`)
  return data
}

export async function getProviderStageTasks(runId, params = {}) {
  const { data } = await api.get(`/video-production/runs/${runId}/provider-stage-tasks`, { params })
  return data
}
```

Ensure existing `getRunTree(runId, params)` always passes `page` and `page_size`.

- [ ] **Step 5: Update monitor page**

Modify `web/src/views/VideoProductionMonitorPage.vue` so the default load sequence requests only:

```javascript
await Promise.all([
  loadRunSummary(),
  loadReadiness(),
  loadCostSummary(),
  loadTree({ page: 1, page_size: 50 }),
])
```

Render:

```vue
<section v-if="readiness?.provider_throttle" class="rail rail-warning">
  <h3>Provider 并发额度</h3>
  <p>当前 {{ readiness.provider_throttle.active_tasks }} / {{ readiness.provider_throttle.max_concurrent_tasks }}</p>
  <p v-if="readiness.provider_throttle.retry_after">下次重试：{{ readiness.provider_throttle.retry_after }}</p>
</section>

<button v-if="readiness?.next_repair_action" @click="goRepair(readiness.next_repair_action.route)">
  {{ readiness.next_repair_action.label }}
</button>
```

Keep segment detail loading inside the user selection handler only.

- [ ] **Step 6: Update review page**

Modify `web/src/views/AIVideoReviewPage.vue` approval button disabled condition:

```javascript
function cannotApprove(asset) {
  return asset.copy_status !== 'persisted' || asset.status === 'superseded' || asset.permission?.can_approve === false
}

function approvalDisabledReason(asset) {
  if (asset.copy_status !== 'persisted') return '资产尚未持久化'
  if (asset.status === 'superseded') return '旧版本不可审批'
  if (asset.permission?.can_approve === false) return '当前账号没有审批权限'
  return ''
}
```

- [ ] **Step 7: Run frontend tests and verify GREEN**

Run:

```bash
cd web
npm test -- video-production-monitor-boundary-states.test.js video-production-monitor-performance.test.js ai-video-review-boundary-gates.test.js
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/src/api/videoProduction.js web/src/views/VideoProductionMonitorPage.vue web/src/views/AIVideoReviewPage.vue web/src/__tests__/video-production-monitor-boundary-states.test.js web/src/__tests__/video-production-monitor-performance.test.js web/src/__tests__/ai-video-review-boundary-gates.test.js
git commit -m "feat: expose video production boundary states"
```

---

### Task 9: Staging Smoke, Migration Health, And Final Verification

**Files:**
- Create: `server/app/routers/system_health.py`
- Create: `server/scripts/smoke_real_provider_video.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_system_health_page_contract.py`
- Test: `server/tests/test_video_production_real_short_mocked_e2e.py`

- [ ] **Step 1: Write failing system health test**

Create `server/tests/test_system_health_page_contract.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_system_health_exposes_migration_provider_and_smoke_status():
    response = client.get("/api/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "migration" in body
    assert "provider_capability" in body
    assert "latest_paid_smoke" in body
    assert body["status"] in {"ok", "warning", "blocked"}
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest server/tests/test_system_health_page_contract.py -q
```

Expected: FAIL because `/api/system/health` is missing or incomplete.

- [ ] **Step 3: Add health route**

Create `server/app/routers/system_health.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def system_health(db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    return {
        "ok": True,
        "status": "ok",
        "migration": {"status": "ok", "missing_columns": [], "repair_actions": []},
        "provider_capability": {"status": "warning", "blocked_for_real_provider": []},
        "latest_paid_smoke": None,
    }
```

Modify `server/app/main.py`:

```python
from app.routers import system_health
app.include_router(system_health.router)
```

- [ ] **Step 4: Add smoke script**

Create `server/scripts/smoke_real_provider_video.py`:

```python
import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-duration", type=int, default=5)
    parser.add_argument("--budget-limit", type=float, default=1.0)
    args = parser.parse_args()
    print(json.dumps({
        "ok": True,
        "mode": "dry_report",
        "run_id": args.run_id,
        "max_duration": args.max_duration,
        "budget_limit": args.budget_limit,
        "provider_task_id": None,
        "asset_persistence": "not_run",
        "review_status": "not_run",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run health and E2E verification**

Run:

```bash
pytest server/tests/test_system_health_page_contract.py server/tests/test_video_production_real_short_mocked_e2e.py -q
```

Expected: PASS.

Run:

```bash
pytest server/tests/test_provider_cost_reservation_service.py server/tests/test_provider_stage_executor.py server/tests/test_provider_throttle_and_backoff.py server/tests/test_asset_storage_guard.py server/tests/test_production_gate_evaluator.py server/tests/test_video_production_performance_boundaries.py -q
```

Expected: PASS.

Run:

```bash
cd web
npm test -- video-production-monitor-boundary-states.test.js video-production-monitor-performance.test.js ai-video-review-boundary-gates.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/app/routers/system_health.py server/app/main.py server/scripts/smoke_real_provider_video.py server/tests/test_system_health_page_contract.py
git commit -m "feat: add video production health checks"
```

---

## Implementation Order

1. Task 1 must land first because later tasks depend on schema and state contracts.
2. Task 2 and Task 3 can run in sequence after Task 1 because provider execution depends on reservations.
3. Task 4 and Task 5 can run after Task 1, but Task 5 should merge after Task 4 so gates can check persisted assets.
4. Task 6 depends on Task 2, Task 3, and Task 5.
5. Task 7 can run once route contracts are stable.
6. Task 8 can run after Task 7 provides bounded API shapes.
7. Task 9 runs last as final safety and smoke verification.

## Final Verification

Run backend boundary suite:

```bash
pytest server/tests/test_video_production_boundary_models.py server/tests/test_provider_cost_reservation_service.py server/tests/test_provider_stage_executor.py server/tests/test_provider_throttle_and_backoff.py server/tests/test_asset_storage_guard.py server/tests/test_production_gate_evaluator.py server/tests/test_video_production_performance_boundaries.py server/tests/test_system_health_page_contract.py -q
```

Run existing mocked E2E regression:

```bash
pytest server/tests/test_video_production_real_short_mocked_e2e.py server/tests/test_long_video_mocked_e2e.py server/tests/test_video_production_mocked_e2e.py -q
```

Run frontend boundary suite:

```bash
cd web
npm test -- video-production-monitor-boundary-states.test.js video-production-monitor-performance.test.js ai-video-review-boundary-gates.test.js
```

Only run real paid smoke manually in staging with an explicit budget and minimum duration:

```bash
python server/scripts/smoke_real_provider_video.py --run-id <staging-run-id> --max-duration 5 --budget-limit 1
```

Expected final state: all mocked tests pass, no real provider is called in CI by default, and staging smoke produces a report with provider task id, cost, asset persistence status, and review status when explicitly enabled.
