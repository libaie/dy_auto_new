# Image Production Strategy Control Plane Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not create git commits unless the user explicitly asks; use test output and `git status --short` as checkpoints.

**Goal:** Add Phase 4 A/B strategy comparison, attempt ledger, winner adoption, and strategy quality/cost/latency metrics on top of the completed Phase 3 image production control plane.

**Architecture:** Keep `POST /api/image-creation/tasks` as the only authoritative image execution path. Phase 4 adds A/B orchestration around that path: an A/B group records the shared prompt/input package, each attempt creates one normal `ImageCreationTask`, metrics are incrementally derived from task, asset, review, and cost events, and winner adoption is an explicit admin action.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Vitest, existing `image_creation` and `image_production` API clients.

---

## Source Material

- Design spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-28-image-production-strategy-control-plane-design.md`
- Completed Phase 1 plan: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-28-image-production-strategy-control-plane-phase1.md`
- Completed Phase 2 plan: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-28-image-production-strategy-control-plane-phase2.md`
- Completed Phase 3 plan: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-29-image-production-strategy-control-plane-phase3.md`
- Existing models: `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- Existing image creation service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Existing strategy service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_strategy_service.py`
- Existing cost ledger: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_cost_service.py`
- Existing image production router: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Existing image creation UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Existing strategy center UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`

## Current State Assumption

Phase 3 is complete and verified:

- Strategy CRUD, immutable versions, selection preview, fallback diagnostics, cost confirmation, capacity preview, queue dispatch, review gates, and image-to-video promotion exist.
- `ImageCreationTask.ab_test_group_id` already exists as a nullable field.
- `ImageProductionStrategy.ab_test_policy_version_id` already exists.
- `ImageProductionCostEvent` exists and records estimated and actual image generation cost events.
- No `image_production_ab_groups`, `image_production_ab_attempts`, or `image_production_metrics` tables exist yet.

This plan does not repeat Phase 1, Phase 2, or Phase 3 work.

## Scope

In scope for Phase 4:

- A/B preview for multiple strategy attempts before execution.
- Cost multiplication confirmation before creating A/B attempts.
- First-class A/B group and attempt tables.
- Derived idempotency key per attempt to prevent duplicate strategy attempts.
- Attempt status refresh from normal image tasks and assets.
- Winner adoption, no-winner decision, and manual decision notes.
- Strategy metrics aggregation by strategy version and model.
- Strategy center metric columns and low-sample warnings.
- Image creation workbench A/B mode and side-by-side attempt comparison.

Out of scope for Phase 4:

- Automatic strategy mutation or automatic winner adoption.
- Provider-online E2E against real Pixelle, Seedream, or Seedance.
- Background metric daemon. Phase 4 exposes an explicit refresh service/API and leaves scheduled aggregation to a later ops pass.
- Full analytics dashboard beyond strategy center metrics and A/B comparison.
- Cross-series experiment analytics.

## File Structure

### Backend

- Modify `server/app/db_models.py`
  - Add `ImageProductionAbGroup`, `ImageProductionAbAttempt`, and `ImageProductionMetric`.
- Create `server/alembic/versions/3c4d5e6f7081_image_production_phase4_ab_metrics.py`
  - Adds A/B and metrics tables.
- Create `server/app/services/image_ab_test_service.py`
  - Owns A/B preview, group creation, attempt creation through `create_image_task`, attempt refresh, winner adoption, and payload serialization.
- Create `server/app/services/image_production_metrics_service.py`
  - Owns idempotent metric aggregation from tasks, assets, review records, and cost events.
- Modify `server/app/routers/image_production.py`
  - Adds A/B preview/create/read/refresh/winner/no-winner endpoints and strategy metric summary endpoint.
- Modify `server/app/services/image_creation_service.py`
  - Ensures `task_payload()` includes `ab_test_group_id`.
- Modify `server/app/services/image_production_strategy_service.py`
  - Adds optional metrics summary to `strategy_payload()` only when a service caller requests it.

### Frontend

- Modify `web/src/api/imageProduction.js`
  - Add A/B preview/create/read/refresh/winner/no-winner and metrics API wrappers.
- Modify `web/src/views/ImageCreationPage.vue`
  - Add A/B mode toggle, strategy multi-select, cost multiplication confirmation, and comparison panel.
- Modify `web/src/views/ImageProductionStrategiesPage.vue`
  - Add metric columns, low-sample warning, and A/B result links.

### Tests

- Create `server/tests/test_image_ab_service.py`
- Create `server/tests/test_image_production_metrics_service.py`
- Create `server/tests/test_image_ab_api.py`
- Extend `server/tests/test_image_production_migration.py`
- Extend `server/tests/test_image_creation_strategy_snapshot.py`
- Extend `web/src/__tests__/image-creation-page.test.js`
- Extend `web/src/__tests__/image-production-strategy-page.test.js`
- Extend `web/src/__tests__/image-creation-a11y.test.js`

## Naming Contract

A/B preview response:

```json
{
  "ok": true,
  "request_hash": "sha256:...",
  "strategy_count": 2,
  "attempt_previews": [
    {
      "strategy_id": "strategy-a",
      "strategy_version": 3,
      "selected_model": {"model_id": "model-a", "name": "Seedream"},
      "cost_estimate": {"amount": 1.2, "currency": "CNY"},
      "warnings": []
    }
  ],
  "total_cost_estimate": {
    "amount": 2.4,
    "currency": "CNY",
    "requires_confirmation": true,
    "confirmation_threshold": 2.0
  },
  "warnings": ["A/B comparison will create 2 image tasks."]
}
```

A/B group response:

```json
{
  "ok": true,
  "ab_group": {
    "id": "group-id",
    "status": "running",
    "source_request_hash": "sha256:...",
    "winner_attempt_id": null,
    "attempts": [
      {
        "id": "attempt-id",
        "task_id": "task-id",
        "strategy_id": "strategy-id",
        "strategy_version": 1,
        "model_id": "model-id",
        "status": "running",
        "metrics": {"estimated_cost": 1.2, "actual_cost": 0, "latency_seconds": null}
      }
    ]
  }
}
```

Error contract:

| Error code | HTTP | Meaning | Required details |
|---|---:|---|---|
| `IMAGE_AB_TEST_STRATEGY_COUNT_INVALID` | 422 | Fewer than 2 or more than 4 strategies | `strategy_count` |
| `IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED` | 409 | Total cost exceeds threshold and user has not confirmed | `total_cost_estimate`, `strategy_count`, `request_hash` |
| `IMAGE_AB_TEST_PREVIEW_DRIFT` | 409 | Create payload does not match preview hash | `expected_hash`, `actual_hash` |
| `IMAGE_AB_TEST_ATTEMPT_NOT_READY` | 409 | Winner attempt has not produced an approved asset | `attempt_id`, `status` |
| `IMAGE_AB_TEST_WINNER_CONFLICT` | 409 | Winner or no-winner decision already exists | `winner_attempt_id`, `status` |
| `IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT` | 409 | A/B idempotency key was reused for a different request | `idempotency_key`, `existing_hash`, `actual_hash` |

## Task 0: Add A/B And Metrics Schema

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\alembic\versions\3c4d5e6f7081_image_production_phase4_ab_metrics.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\conftest.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_migration.py`

- [ ] **Step 1: Write failing migration tests**

Append to `server/tests/test_image_production_migration.py`:

```python
def test_image_production_phase4_revision_depends_on_phase3():
    config = _alembic_config()
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision("3c4d5e6f7081")

    assert script.get_heads() == ["3c4d5e6f7081"]
    assert revision is not None
    assert revision.down_revision == "2b3c4d5e6f70"


def test_image_production_phase4_tables_exist(test_db):
    inspector = inspect(test_db)

    assert "image_production_ab_groups" in inspector.get_table_names()
    assert "image_production_ab_attempts" in inspector.get_table_names()
    assert "image_production_metrics" in inspector.get_table_names()

    group_columns = {column["name"] for column in inspector.get_columns("image_production_ab_groups")}
    assert {
        "idempotency_key",
        "source_request_hash",
        "winner_attempt_id",
        "decision_json",
    }.issubset(group_columns)

    attempt_columns = {column["name"] for column in inspector.get_columns("image_production_ab_attempts")}
    assert {
        "group_id",
        "task_id",
        "strategy_id",
        "strategy_version",
        "model_id",
        "status",
        "metrics_snapshot_json",
        "human_decision_json",
    }.issubset(attempt_columns)
```

- [ ] **Step 2: Run migration tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py::test_image_production_phase4_revision_depends_on_phase3 tests/test_image_production_migration.py::test_image_production_phase4_tables_exist -v -p no:cacheprovider
```

Expected: FAIL because the Phase 4 revision and ORM tables do not exist.

- [ ] **Step 3: Add ORM models**

Modify `server/app/db_models.py` after `ImageProductionCostEvent`:

```python
class ImageProductionAbGroup(Base):
    __tablename__ = "image_production_ab_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(160), nullable=True)
    source_request_hash = Column(String(64), nullable=False)
    prompt_snapshot_json = Column(JSON, nullable=False, default=dict)
    cost_confirmation_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="running")
    winner_attempt_id = Column(String(36), nullable=True)
    decision_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_image_ab_group_idempotency_key"),
        Index("idx_image_ab_groups_hash", "source_request_hash"),
        Index("idx_image_ab_groups_status_created", "status", "created_at"),
        Index("idx_image_ab_groups_winner", "winner_attempt_id"),
    )


class ImageProductionAbAttempt(Base):
    __tablename__ = "image_production_ab_attempts"

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("image_production_ab_groups.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="SET NULL"), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    model_id = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="created")
    metrics_snapshot_json = Column(JSON, nullable=True, default=dict)
    human_decision_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("group_id", "strategy_id", "strategy_version", name="uq_image_ab_attempt_strategy"),
        Index("idx_image_ab_attempts_group", "group_id"),
        Index("idx_image_ab_attempts_task", "task_id"),
        Index("idx_image_ab_attempts_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_ab_attempts_status", "status"),
    )


class ImageProductionMetric(Base):
    __tablename__ = "image_production_metrics"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="CASCADE"), nullable=False)
    strategy_version = Column(Integer, nullable=False)
    model_id = Column(String(120), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    ai_pass_count = Column(Integer, nullable=False, default=0)
    human_pass_count = Column(Integer, nullable=False, default=0)
    repaint_count = Column(Integer, nullable=False, default=0)
    average_latency_seconds = Column(Float, nullable=False, default=0.0)
    average_cost_amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("strategy_id", "strategy_version", "model_id", name="uq_image_metric_strategy_model"),
        Index("idx_image_metrics_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_metrics_updated", "updated_at"),
    )
```

- [ ] **Step 4: Add Alembic migration**

Create `server/alembic/versions/3c4d5e6f7081_image_production_phase4_ab_metrics.py`:

```python
"""image production phase4 ab metrics

Revision ID: 3c4d5e6f7081
Revises: 2b3c4d5e6f70
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "3c4d5e6f7081"
down_revision = "2b3c4d5e6f70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_production_ab_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("source_request_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("cost_confirmation_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("winner_attempt_id", sa.String(length=36), nullable=True),
        sa.Column("decision_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_image_ab_group_idempotency_key"),
    )
    op.create_index("idx_image_ab_groups_hash", "image_production_ab_groups", ["source_request_hash"])
    op.create_index("idx_image_ab_groups_status_created", "image_production_ab_groups", ["status", "created_at"])
    op.create_index("idx_image_ab_groups_winner", "image_production_ab_groups", ["winner_attempt_id"])

    op.create_table(
        "image_production_ab_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_version", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("metrics_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("human_decision_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["image_production_ab_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["image_creation_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["image_production_strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "strategy_id", "strategy_version", name="uq_image_ab_attempt_strategy"),
    )
    op.create_index("idx_image_ab_attempts_group", "image_production_ab_attempts", ["group_id"])
    op.create_index("idx_image_ab_attempts_task", "image_production_ab_attempts", ["task_id"])
    op.create_index("idx_image_ab_attempts_strategy", "image_production_ab_attempts", ["strategy_id", "strategy_version"])
    op.create_index("idx_image_ab_attempts_status", "image_production_ab_attempts", ["status"])

    op.create_table(
        "image_production_metrics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("ai_pass_count", sa.Integer(), nullable=False),
        sa.Column("human_pass_count", sa.Integer(), nullable=False),
        sa.Column("repaint_count", sa.Integer(), nullable=False),
        sa.Column("average_latency_seconds", sa.Float(), nullable=False),
        sa.Column("average_cost_amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["image_production_strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "strategy_version", "model_id", name="uq_image_metric_strategy_model"),
    )
    op.create_index("idx_image_metrics_strategy", "image_production_metrics", ["strategy_id", "strategy_version"])
    op.create_index("idx_image_metrics_updated", "image_production_metrics", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_image_metrics_updated", table_name="image_production_metrics")
    op.drop_index("idx_image_metrics_strategy", table_name="image_production_metrics")
    op.drop_table("image_production_metrics")
    op.drop_index("idx_image_ab_attempts_status", table_name="image_production_ab_attempts")
    op.drop_index("idx_image_ab_attempts_strategy", table_name="image_production_ab_attempts")
    op.drop_index("idx_image_ab_attempts_task", table_name="image_production_ab_attempts")
    op.drop_index("idx_image_ab_attempts_group", table_name="image_production_ab_attempts")
    op.drop_table("image_production_ab_attempts")
    op.drop_index("idx_image_ab_groups_winner", table_name="image_production_ab_groups")
    op.drop_index("idx_image_ab_groups_status_created", table_name="image_production_ab_groups")
    op.drop_index("idx_image_ab_groups_hash", table_name="image_production_ab_groups")
    op.drop_table("image_production_ab_groups")
```

- [ ] **Step 4A: Add Phase 4 tables to test cleanup order**

Modify `server/tests/conftest.py` imports to include:

```python
ImageProductionAbAttempt, ImageProductionAbGroup, ImageProductionMetric
```

Place the new tables before image tasks and strategies in `_CLEANUP_TABLES`:

```python
ImageProductionAbAttempt, ImageProductionAbGroup, ImageProductionMetric,
ImageCreationReviewRecord, ImageProductionCostEvent, ImageCreationAsset, ImageCreationTask,
```

This prevents A/B groups and metrics from leaking between tests in the session-scoped SQLite database.

- [ ] **Step 5: Run migration tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 1: Add Strategy Metrics Aggregation

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_metrics_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_metrics_service.py`

- [ ] **Step 1: Write failing metrics tests**

Create `server/tests/test_image_production_metrics_service.py`:

```python
from datetime import timedelta

from app.config import bj_now
from app.db_models import ImageCreationAsset, ImageCreationReviewRecord, ImageCreationTask, ImageProductionCostEvent
from app.services.image_production_metrics_service import refresh_image_strategy_metrics, strategy_metrics_payload


def test_refresh_image_strategy_metrics_counts_task_asset_review_and_cost(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        prompt="metric prompt",
        count=1,
        target_count=1,
        strategy_id="strategy-1",
        strategy_version=2,
        model_id="model-1",
        provider="seedance",
        created_at=bj_now() - timedelta(seconds=12),
        completed_at=bj_now(),
    )
    db.add(task)
    db.flush()
    asset = ImageCreationAsset(
        task_id=task.id,
        status="approved",
        audit_status="approved",
        manual_review_status="approved",
        url="https://cdn.example/a.png",
        destination_role="image_to_video_input",
    )
    db.add(asset)
    db.flush()
    db.add(ImageCreationReviewRecord(
        task_id=task.id,
        asset_id=asset.id,
        review_type="human",
        reviewer_type="human",
        status="approved",
        action="approve",
        asset_version=1,
        is_latest_asset_review=True,
    ))
    db.add(ImageProductionCostEvent(
        event_key=f"{task.id}:actual:metric",
        task_id=task.id,
        event_type="actual",
        strategy_id="strategy-1",
        strategy_version=2,
        model_id="model-1",
        provider="seedance",
        actual_cost=1.8,
        estimated_cost=1.5,
        currency="CNY",
    ))
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 2, "model-1")

    assert metric.attempt_count == 1
    assert metric.success_count == 1
    assert metric.failure_count == 0
    assert metric.ai_pass_count == 1
    assert metric.human_pass_count == 1
    assert metric.average_cost_amount == 1.8
    assert metric.average_latency_seconds >= 1
    assert strategy_metrics_payload(metric)["success_rate"] == 1.0


def test_refresh_image_strategy_metrics_is_idempotent(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="failed",
        prompt="failed metric prompt",
        count=1,
        target_count=1,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
    )
    db.add(task)
    db.commit()

    first = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")
    second = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")

    assert first.id == second.id
    assert second.attempt_count == 1
    assert second.failure_count == 1


def test_refresh_image_strategy_metrics_counts_latest_actual_cost_once_per_task(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        prompt="retry metric prompt",
        count=1,
        target_count=1,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
    )
    db.add(task)
    db.flush()
    db.add(ImageProductionCostEvent(
        event_key=f"{task.id}:actual:first",
        task_id=task.id,
        event_type="actual",
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
        actual_cost=1.0,
        estimated_cost=1.0,
        currency="CNY",
        created_at=bj_now() - timedelta(seconds=10),
    ))
    db.add(ImageProductionCostEvent(
        event_key=f"{task.id}:actual:retry",
        task_id=task.id,
        event_type="actual",
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
        actual_cost=2.0,
        estimated_cost=1.0,
        currency="CNY",
        created_at=bj_now(),
    ))
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")

    assert metric.attempt_count == 1
    assert metric.average_cost_amount == 2.0
```

- [ ] **Step 2: Run metrics tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_metrics_service.py -v -p no:cacheprovider
```

Expected: FAIL because `image_production_metrics_service.py` does not exist.

- [ ] **Step 3: Implement metrics service**

Create `server/app/services/image_production_metrics_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import (
    ImageCreationAsset,
    ImageCreationReviewRecord,
    ImageCreationTask,
    ImageProductionCostEvent,
    ImageProductionMetric,
)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _latency_seconds(task: ImageCreationTask) -> float | None:
    if task.created_at and task.completed_at:
        return max(0.0, (task.completed_at - task.created_at).total_seconds())
    return None


def _actual_costs(db: Session, task_ids: list[str]) -> tuple[list[float], str]:
    if not task_ids:
        return [], "CNY"
    rows = (
        db.query(ImageProductionCostEvent)
        .filter(ImageProductionCostEvent.task_id.in_(task_ids))
        .filter(ImageProductionCostEvent.event_type == "actual")
        .all()
    )
    latest_by_task: dict[str, ImageProductionCostEvent] = {}
    for row in rows:
        current = latest_by_task.get(row.task_id)
        if current is None or row.created_at > current.created_at:
            latest_by_task[row.task_id] = row
    costs = [float(row.actual_cost or 0.0) for row in latest_by_task.values()]
    currency = rows[0].currency if rows else "CNY"
    return costs, currency


def refresh_image_strategy_metrics(
    db: Session,
    strategy_id: str,
    strategy_version: int,
    model_id: str | None,
) -> ImageProductionMetric:
    query = (
        db.query(ImageCreationTask)
        .filter(ImageCreationTask.strategy_id == strategy_id)
        .filter(ImageCreationTask.strategy_version == strategy_version)
    )
    if model_id is None:
        query = query.filter(ImageCreationTask.model_id.is_(None))
    else:
        query = query.filter(ImageCreationTask.model_id == model_id)
    tasks = query.all()
    task_ids = [task.id for task in tasks]

    assets = (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id.in_(task_ids))
        .all()
        if task_ids else []
    )
    reviews = (
        db.query(ImageCreationReviewRecord)
        .filter(ImageCreationReviewRecord.task_id.in_(task_ids))
        .filter(ImageCreationReviewRecord.is_latest_asset_review.is_(True))
        .all()
        if task_ids else []
    )
    costs, currency = _actual_costs(db, task_ids)
    latencies = [value for value in (_latency_seconds(task) for task in tasks) if value is not None]

    metric = (
        db.query(ImageProductionMetric)
        .filter(ImageProductionMetric.strategy_id == strategy_id)
        .filter(ImageProductionMetric.strategy_version == strategy_version)
        .filter(ImageProductionMetric.model_id == model_id)
        .first()
    )
    if not metric:
        metric = ImageProductionMetric(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            model_id=model_id,
        )
        db.add(metric)

    metric.attempt_count = len(tasks)
    metric.success_count = len([task for task in tasks if task.status == "completed"])
    metric.failure_count = len([task for task in tasks if task.status == "failed"])
    metric.ai_pass_count = len([asset for asset in assets if asset.audit_status == "approved"])
    metric.human_pass_count = len([review for review in reviews if review.action == "approve" or review.status == "approved"])
    metric.repaint_count = len([asset for asset in assets if asset.status == "regenerating" or asset.source_asset_id])
    metric.average_latency_seconds = _avg(latencies)
    metric.average_cost_amount = _avg(costs)
    metric.currency = currency
    metric.updated_at = bj_now()
    db.commit()
    db.refresh(metric)
    return metric


def strategy_metrics_payload(metric: ImageProductionMetric | None) -> dict[str, Any]:
    if not metric:
        return {
            "attempt_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 0,
            "ai_pass_rate": 0,
            "human_pass_rate": 0,
            "average_latency_seconds": 0,
            "average_cost_amount": 0,
            "currency": "CNY",
            "low_sample": True,
        }
    attempts = max(metric.attempt_count, 1)
    return {
        "attempt_count": metric.attempt_count,
        "success_count": metric.success_count,
        "failure_count": metric.failure_count,
        "success_rate": round(metric.success_count / attempts, 4),
        "ai_pass_rate": round(metric.ai_pass_count / attempts, 4),
        "human_pass_rate": round(metric.human_pass_count / attempts, 4),
        "repaint_count": metric.repaint_count,
        "average_latency_seconds": metric.average_latency_seconds,
        "average_cost_amount": metric.average_cost_amount,
        "currency": metric.currency,
        "low_sample": metric.attempt_count < 5,
        "updated_at": metric.updated_at.isoformat() if metric.updated_at else None,
    }
```

- [ ] **Step 4: Run metrics tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_metrics_service.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 2: Add A/B Preview And Creation Service

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_ab_test_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_ab_service.py`

- [ ] **Step 1: Write failing A/B preview and creation tests**

Create `server/tests/test_image_ab_service.py`:

```python
import pytest

from app.db_models import AIModel, ImageProductionStrategy
from app.services.crypto import encrypt
from app.services.image_ab_test_service import create_ab_group, preview_ab_group


def _model(db):
    row = AIModel(
        name="AB Image Model",
        provider="seedance",
        model_type="image",
        model_name="seedream-ab",
        enabled=True,
        base_url="https://example.invalid",
        api_key=encrypt("secret-key"),
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation"],
            "capabilities": {"text_to_image": True},
            "cost_profile": {"unit_cost": 1.5, "currency": "CNY"},
        },
    )
    db.add(row)
    db.commit()
    return row


def _strategy(db, model, slug):
    row = ImageProductionStrategy(
        slug=slug,
        name=slug,
        destination_role="storyboard_first_frame",
        supported_modes_json=["text_to_image"],
        default_model_id=model.id,
        fallback_model_ids_json=[],
        common_parameters_json={},
        provider_options_json={},
        status="active",
        version=1,
    )
    db.add(row)
    db.commit()
    return row


def test_preview_ab_group_requires_multiple_strategies(db):
    model = _model(db)
    strategy = _strategy(db, model, "one")

    with pytest.raises(Exception) as exc:
        preview_ab_group(db, {
            "mode": "text_to_image",
            "prompt": "one strategy",
            "destination_role": "storyboard_first_frame",
            "strategy_ids": [strategy.id],
            "count": 1,
        })

    assert exc.value.detail["error_code"] == "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID"


def test_preview_ab_group_returns_total_cost_and_request_hash(db):
    model = _model(db)
    first = _strategy(db, model, "first")
    second = _strategy(db, model, "second")

    result = preview_ab_group(db, {
        "mode": "text_to_image",
        "prompt": "compare prompt",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": [first.id, second.id],
        "count": 1,
    })

    assert result["strategy_count"] == 2
    assert len(result["attempt_previews"]) == 2
    assert result["total_cost_estimate"]["amount"] == 3.0
    assert result["request_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_create_ab_group_creates_attempt_tasks_with_derived_idempotency(db, monkeypatch):
    model = _model(db)
    first = _strategy(db, model, "first-create")
    second = _strategy(db, model, "second-create")

    async def fake_create_image_task(db, payload):
        from app.db_models import ImageCreationTask
        task = ImageCreationTask(
            mode=payload["mode"],
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            count=1,
            target_count=1,
            strategy_id=payload["strategy_id"],
            strategy_version=payload["strategy_version"],
            ab_test_group_id=payload["ab_test_group_id"],
            idempotency_key=payload["idempotency_key"],
            model_id=model.id,
        )
        db.add(task)
        db.flush()
        return task

    monkeypatch.setattr("app.services.image_ab_test_service.create_image_task", fake_create_image_task)
    preview = preview_ab_group(db, {
        "mode": "text_to_image",
        "prompt": "create group",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": [first.id, second.id],
        "count": 1,
    })

    group = await create_ab_group(db, {
        "mode": "text_to_image",
        "prompt": "create group",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": [first.id, second.id],
        "count": 1,
        "preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
        "idempotency_key": "ab-idem-1",
    }, user_id="user-1")

    assert group.status == "running"
    assert len(group.attempts_for_test) == 2
    assert {attempt.strategy_id for attempt in group.attempts_for_test} == {first.id, second.id}


@pytest.mark.asyncio
async def test_create_ab_group_reuses_group_idempotency_key_for_same_request(db, monkeypatch):
    model = _model(db)
    first = _strategy(db, model, "first-idem")
    second = _strategy(db, model, "second-idem")

    async def fake_create_image_task(db, payload):
        from app.db_models import ImageCreationTask
        existing = db.query(ImageCreationTask).filter(ImageCreationTask.idempotency_key == payload["idempotency_key"]).first()
        if existing:
            return existing
        task = ImageCreationTask(
            mode=payload["mode"],
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            count=1,
            target_count=1,
            strategy_id=payload["strategy_id"],
            strategy_version=payload["strategy_version"],
            ab_test_group_id=payload["ab_test_group_id"],
            idempotency_key=payload["idempotency_key"],
            model_id=model.id,
        )
        db.add(task)
        db.flush()
        return task

    monkeypatch.setattr("app.services.image_ab_test_service.create_image_task", fake_create_image_task)
    payload = {
        "mode": "text_to_image",
        "prompt": "same group request",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": [first.id, second.id],
        "count": 1,
        "cost_confirmation": True,
        "idempotency_key": "ab-group-idem",
    }

    first_group = await create_ab_group(db, dict(payload), user_id="user-1")
    second_group = await create_ab_group(db, dict(payload), user_id="user-1")

    assert first_group.id == second_group.id
```

- [ ] **Step 2: Run A/B service tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_service.py -v -p no:cacheprovider
```

Expected: FAIL because `image_ab_test_service.py` does not exist.

- [ ] **Step 3: Implement A/B service**

Create `server/app/services/image_ab_test_service.py`:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ImageCreationAsset, ImageCreationTask, ImageProductionAbAttempt, ImageProductionAbGroup
from app.services.image_creation_errors import image_error
from app.services.image_creation_service import create_image_task, task_payload
from app.services.image_production_metrics_service import refresh_image_strategy_metrics
from app.services.image_production_strategy_service import get_strategy, strategy_payload
from app.services.image_selection_preview_service import create_selection_preview


MAX_AB_STRATEGIES = 4


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _base_preview_payload(payload: dict[str, Any], strategy_id: str, strategy_version: int) -> dict[str, Any]:
    return {
        "mode": payload["mode"],
        "prompt": payload["prompt"],
        "negative_prompt": payload.get("negative_prompt") or "",
        "destination_role": payload.get("destination_role"),
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "source": payload.get("source"),
        "source_url": payload.get("source_url"),
        "source_asset_id": payload.get("source_asset_id"),
        "reference_images": payload.get("reference_images") or [],
        "size": payload.get("size"),
        "count": payload.get("count") or 1,
        "output_format": payload.get("output_format"),
        "response_format": payload.get("response_format"),
        "watermark": payload.get("watermark"),
        "provider_options": payload.get("provider_options") or {},
    }


def _strategy_rows(db: Session, strategy_ids: list[str]):
    if len(strategy_ids) < 2 or len(strategy_ids) > MAX_AB_STRATEGIES:
        raise image_error(
            422,
            "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID",
            "A/B comparison requires 2 to 4 strategies.",
            "Choose between 2 and 4 active image strategies.",
            retryable=False,
            details={"strategy_count": len(strategy_ids)},
        )
    strategies = [get_strategy(db, strategy_id) for strategy_id in strategy_ids]
    inactive = [strategy.id for strategy in strategies if strategy.status != "active"]
    if inactive:
        raise image_error(
            422,
            "IMAGE_AB_TEST_STRATEGY_INACTIVE",
            "A/B comparison can only use active strategies.",
            "Activate or replace inactive strategies.",
            retryable=False,
            affected_ids=inactive,
        )
    return strategies


def preview_ab_group(db: Session, payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    strategies = _strategy_rows(db, payload.get("strategy_ids") or [])
    request_hash = _stable_hash({
        "mode": payload["mode"],
        "prompt": payload["prompt"],
        "negative_prompt": payload.get("negative_prompt") or "",
        "destination_role": payload.get("destination_role"),
        "strategy_ids": [strategy.id for strategy in strategies],
        "strategy_versions": [strategy.version for strategy in strategies],
        "source": payload.get("source"),
        "source_url": payload.get("source_url"),
        "source_asset_id": payload.get("source_asset_id"),
        "reference_images": payload.get("reference_images") or [],
        "size": payload.get("size"),
        "count": payload.get("count") or 1,
        "output_format": payload.get("output_format"),
        "response_format": payload.get("response_format"),
        "watermark": payload.get("watermark"),
        "provider_options": payload.get("provider_options") or {},
    })
    previews = []
    total_amount = 0.0
    currency = "CNY"
    requires_confirmation = False
    threshold = 0.0
    for strategy in strategies:
        preview = create_selection_preview(
            db,
            _base_preview_payload(payload, strategy.id, strategy.version),
            user_id=user_id,
        )
        estimate = preview.get("cost_estimate") or {}
        amount = float(estimate.get("amount") or 0.0)
        total_amount += amount
        currency = estimate.get("currency") or currency
        requires_confirmation = requires_confirmation or bool(estimate.get("requires_confirmation"))
        threshold = max(threshold, float(estimate.get("confirmation_threshold") or 0.0))
        previews.append({
            "strategy": strategy_payload(strategy),
            "strategy_id": strategy.id,
            "strategy_version": strategy.version,
            "selection_preview_id": preview.get("selection_preview_id"),
            "selection_preview_request_hash": preview.get("request_hash"),
            "selected_model": preview.get("selected_model"),
            "selection_explanation": preview.get("selection_explanation") or {},
            "cost_estimate": estimate,
            "capacity": preview.get("capacity") or {},
            "review_gate": preview.get("review_gate") or {},
            "warnings": preview.get("warnings") or [],
        })
    total = {
        "amount": round(total_amount, 4),
        "currency": currency,
        "requires_confirmation": requires_confirmation or total_amount > threshold,
        "confirmation_threshold": threshold,
    }
    return {
        "ok": True,
        "request_hash": request_hash,
        "strategy_count": len(strategies),
        "attempt_previews": previews,
        "total_cost_estimate": total,
        "warnings": [f"A/B comparison will create {len(strategies)} image tasks."],
    }


def _ensure_preview_matches(db: Session, payload: dict[str, Any], user_id: str | None) -> dict[str, Any]:
    preview = preview_ab_group(db, payload, user_id=user_id)
    expected = payload.get("preview_request_hash")
    if expected and expected != preview["request_hash"]:
        raise image_error(
            409,
            "IMAGE_AB_TEST_PREVIEW_DRIFT",
            "A/B preview no longer matches the create request.",
            "Run A/B preview again and confirm the displayed cost.",
            retryable=False,
            details={"expected_hash": expected, "actual_hash": preview["request_hash"]},
        )
    if preview["total_cost_estimate"].get("requires_confirmation") and not payload.get("cost_confirmation"):
        raise image_error(
            409,
            "IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED",
            "A/B comparison requires explicit cost confirmation.",
            "Confirm the total A/B cost before creating attempts.",
            retryable=False,
            details={
                "total_cost_estimate": preview["total_cost_estimate"],
                "strategy_count": preview["strategy_count"],
                "request_hash": preview["request_hash"],
            },
        )
    return preview


def _existing_group_for_idempotency(db: Session, payload: dict[str, Any], request_hash: str) -> ImageProductionAbGroup | None:
    key = payload.get("idempotency_key")
    if not key:
        return None
    existing = db.query(ImageProductionAbGroup).filter(ImageProductionAbGroup.idempotency_key == key).first()
    if not existing:
        return None
    if existing.source_request_hash != request_hash:
        raise image_error(
            409,
            "IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT",
            "A/B idempotency key was reused for a different request.",
            "Use a new A/B idempotency key or restore the original request.",
            retryable=False,
            details={
                "idempotency_key": key,
                "existing_hash": existing.source_request_hash,
                "actual_hash": request_hash,
            },
        )
    return existing


async def create_ab_group(db: Session, payload: dict[str, Any], user_id: str | None = None) -> ImageProductionAbGroup:
    preview = _ensure_preview_matches(db, payload, user_id)
    existing = _existing_group_for_idempotency(db, payload, preview["request_hash"])
    if existing:
        existing.attempts_for_test = (
            db.query(ImageProductionAbAttempt)
            .filter(ImageProductionAbAttempt.group_id == existing.id)
            .order_by(ImageProductionAbAttempt.created_at.asc())
            .all()
        )
        return existing
    group = ImageProductionAbGroup(
        user_id=user_id,
        idempotency_key=payload.get("idempotency_key"),
        source_request_hash=preview["request_hash"],
        prompt_snapshot_json={
            "mode": payload["mode"],
            "prompt": payload["prompt"],
            "negative_prompt": payload.get("negative_prompt") or "",
            "destination_role": payload.get("destination_role"),
            "strategy_ids": payload.get("strategy_ids") or [],
            "count": payload.get("count") or 1,
            "source": payload.get("source"),
            "source_asset_id": payload.get("source_asset_id"),
            "reference_images": payload.get("reference_images") or [],
        },
        cost_confirmation_json={
            "confirmed": bool(payload.get("cost_confirmation")),
            "total_cost_estimate": preview["total_cost_estimate"],
        },
        status="running",
    )
    db.add(group)
    db.flush()
    attempts = []
    for index, attempt_preview in enumerate(preview["attempt_previews"]):
        attempt = ImageProductionAbAttempt(
            group_id=group.id,
            strategy_id=attempt_preview["strategy_id"],
            strategy_version=attempt_preview["strategy_version"],
            model_id=(attempt_preview.get("selected_model") or {}).get("model_id"),
            status="creating",
            metrics_snapshot_json={"estimated_cost": attempt_preview.get("cost_estimate") or {}},
        )
        db.add(attempt)
        db.flush()
        attempt_payload = dict(payload)
        attempt_payload.update({
            "strategy_id": attempt.strategy_id,
            "strategy_version": attempt.strategy_version,
            "selection_preview_id": attempt_preview.get("selection_preview_id"),
            "selection_preview_request_hash": attempt_preview.get("selection_preview_request_hash"),
            "ab_test_group_id": group.id,
            "cost_confirmation": True,
            "idempotency_key": f"{payload.get('idempotency_key') or group.id}:attempt:{index}:{attempt.strategy_id}:{attempt.strategy_version}",
        })
        task = await create_image_task(db, attempt_payload)
        task.ab_test_group_id = group.id
        attempt.task_id = task.id
        attempt.status = task.status
        attempt.metrics_snapshot_json = {
            **(attempt.metrics_snapshot_json or {}),
            "task": task_payload(task),
        }
        attempts.append(attempt)
    db.commit()
    group.attempts_for_test = attempts
    return group
```

- [ ] **Step 4: Run A/B service tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_service.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 3: Add A/B Refresh And Winner Adoption

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_ab_test_service.py`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_ab_service.py`

- [ ] **Step 1: Add failing winner tests**

Append to `server/tests/test_image_ab_service.py`:

```python
from app.db_models import ImageCreationAsset, ImageCreationTask, ImageProductionAbAttempt, ImageProductionAbGroup
from app.services.image_ab_test_service import adopt_ab_winner, mark_ab_no_winner, refresh_ab_group, serialize_ab_group


def test_refresh_ab_group_marks_completed_when_all_attempts_terminal(db):
    group = ImageProductionAbGroup(source_request_hash="sha256:x", prompt_snapshot_json={}, status="running")
    db.add(group)
    db.flush()
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        prompt="done",
        count=1,
        target_count=1,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
    )
    db.add(task)
    db.flush()
    db.add(ImageProductionAbAttempt(
        group_id=group.id,
        task_id=task.id,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
        status="running",
    ))
    db.commit()

    result = refresh_ab_group(db, group.id)

    assert result.status == "completed"
    assert serialize_ab_group(db, result)["attempts"][0]["status"] == "completed"


def test_adopt_ab_winner_requires_approved_asset(db):
    group = ImageProductionAbGroup(source_request_hash="sha256:x", prompt_snapshot_json={}, status="completed")
    db.add(group)
    db.flush()
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        prompt="winner",
        count=1,
        target_count=1,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
    )
    db.add(task)
    db.flush()
    attempt = ImageProductionAbAttempt(
        group_id=group.id,
        task_id=task.id,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
        status="completed",
    )
    db.add(attempt)
    db.commit()

    with pytest.raises(Exception) as exc:
        adopt_ab_winner(db, group.id, attempt.id, {"reason": "looks best"})

    assert exc.value.detail["error_code"] == "IMAGE_AB_TEST_ATTEMPT_NOT_READY"


def test_adopt_ab_winner_records_decision_for_approved_attempt(db):
    group = ImageProductionAbGroup(source_request_hash="sha256:x", prompt_snapshot_json={}, status="completed")
    db.add(group)
    db.flush()
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        prompt="winner",
        count=1,
        target_count=1,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
    )
    db.add(task)
    db.flush()
    asset = ImageCreationAsset(task_id=task.id, url="https://cdn.example/w.png", status="approved")
    db.add(asset)
    db.flush()
    attempt = ImageProductionAbAttempt(
        group_id=group.id,
        task_id=task.id,
        strategy_id="strategy-1",
        strategy_version=1,
        model_id="model-1",
        status="completed",
    )
    db.add(attempt)
    db.commit()

    result = adopt_ab_winner(db, group.id, attempt.id, {"reason": "best quality"})

    assert result.status == "winner_selected"
    assert result.winner_attempt_id == attempt.id
```

- [ ] **Step 2: Run winner tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_service.py -k "refresh_ab_group or adopt_ab_winner" -v -p no:cacheprovider
```

Expected: FAIL because refresh and winner functions do not exist.

- [ ] **Step 3: Implement refresh and winner functions**

Append to `server/app/services/image_ab_test_service.py`:

```python
TERMINAL_TASK_STATUSES = {"completed", "failed", "blocked", "rejected"}


def get_ab_group(db: Session, group_id: str) -> ImageProductionAbGroup:
    group = db.query(ImageProductionAbGroup).filter(ImageProductionAbGroup.id == group_id).first()
    if not group:
        raise image_error(
            404,
            "IMAGE_AB_TEST_GROUP_NOT_FOUND",
            "A/B comparison group was not found.",
            "Reload the A/B comparison.",
            retryable=False,
            affected_ids=[group_id],
        )
    return group


def _attempt_rows(db: Session, group_id: str) -> list[ImageProductionAbAttempt]:
    return (
        db.query(ImageProductionAbAttempt)
        .filter(ImageProductionAbAttempt.group_id == group_id)
        .order_by(ImageProductionAbAttempt.created_at.asc())
        .all()
    )


def _attempt_has_approved_asset(db: Session, attempt: ImageProductionAbAttempt) -> bool:
    if not attempt.task_id:
        return False
    return (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id == attempt.task_id)
        .filter(ImageCreationAsset.status == "approved")
        .first()
        is not None
    )


def refresh_ab_group(db: Session, group_id: str) -> ImageProductionAbGroup:
    group = get_ab_group(db, group_id)
    attempts = _attempt_rows(db, group.id)
    terminal_count = 0
    failed_count = 0
    for attempt in attempts:
        task = db.query(ImageCreationTask).filter(ImageCreationTask.id == attempt.task_id).first() if attempt.task_id else None
        if task:
            attempt.status = task.status
            attempt.model_id = task.model_id
            attempt.metrics_snapshot_json = {
                **(attempt.metrics_snapshot_json or {}),
                "task_status": task.status,
                "approved_asset_ready": _attempt_has_approved_asset(db, attempt),
            }
            if task.strategy_id and task.strategy_version:
                refresh_image_strategy_metrics(db, task.strategy_id, task.strategy_version, task.model_id)
            if task.status in TERMINAL_TASK_STATUSES:
                terminal_count += 1
            if task.status == "failed":
                failed_count += 1
    if attempts and terminal_count == len(attempts):
        group.status = "failed" if failed_count == len(attempts) else "completed"
    group.updated_at = bj_now()
    db.commit()
    db.refresh(group)
    return group


def adopt_ab_winner(db: Session, group_id: str, attempt_id: str, decision: dict[str, Any]) -> ImageProductionAbGroup:
    group = get_ab_group(db, group_id)
    if group.winner_attempt_id or group.status in {"winner_selected", "no_winner"}:
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_CONFLICT",
            "A/B comparison already has a final decision.",
            "Open the existing decision instead of choosing another winner.",
            retryable=False,
            details={"winner_attempt_id": group.winner_attempt_id, "status": group.status},
        )
    attempt = (
        db.query(ImageProductionAbAttempt)
        .filter(ImageProductionAbAttempt.id == attempt_id)
        .filter(ImageProductionAbAttempt.group_id == group.id)
        .first()
    )
    if not attempt or not _attempt_has_approved_asset(db, attempt):
        raise image_error(
            409,
            "IMAGE_AB_TEST_ATTEMPT_NOT_READY",
            "Winner attempt must have an approved image asset.",
            "Approve the generated image before selecting it as the winner.",
            retryable=False,
            affected_ids=[attempt_id],
            details={"attempt_id": attempt_id, "status": attempt.status if attempt else "missing"},
        )
    attempt.human_decision_json = {"decision": "winner", **(decision or {})}
    group.winner_attempt_id = attempt.id
    group.status = "winner_selected"
    group.decision_json = {"winner_attempt_id": attempt.id, **(decision or {})}
    group.updated_at = bj_now()
    db.commit()
    db.refresh(group)
    return group


def mark_ab_no_winner(db: Session, group_id: str, decision: dict[str, Any]) -> ImageProductionAbGroup:
    group = get_ab_group(db, group_id)
    if group.winner_attempt_id or group.status in {"winner_selected", "no_winner"}:
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_CONFLICT",
            "A/B comparison already has a final decision.",
            "Open the existing decision instead of changing it.",
            retryable=False,
            details={"winner_attempt_id": group.winner_attempt_id, "status": group.status},
        )
    group.status = "no_winner"
    group.decision_json = {"decision": "no_winner", **(decision or {})}
    group.updated_at = bj_now()
    db.commit()
    db.refresh(group)
    return group


def serialize_ab_group(db: Session, group: ImageProductionAbGroup) -> dict[str, Any]:
    attempts = []
    for attempt in _attempt_rows(db, group.id):
        task = db.query(ImageCreationTask).filter(ImageCreationTask.id == attempt.task_id).first() if attempt.task_id else None
        assets = db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id == attempt.task_id).all() if attempt.task_id else []
        attempts.append({
            "id": attempt.id,
            "task_id": attempt.task_id,
            "strategy_id": attempt.strategy_id,
            "strategy_version": attempt.strategy_version,
            "model_id": attempt.model_id,
            "status": attempt.status,
            "metrics": attempt.metrics_snapshot_json or {},
            "approved_asset_ready": any(asset.status == "approved" for asset in assets),
            "asset_ids": [asset.id for asset in assets],
            "task": task_payload(task) if task else None,
            "human_decision": attempt.human_decision_json or {},
        })
    return {
        "id": group.id,
        "status": group.status,
        "source_request_hash": group.source_request_hash,
        "prompt_snapshot": group.prompt_snapshot_json or {},
        "cost_confirmation": group.cost_confirmation_json or {},
        "winner_attempt_id": group.winner_attempt_id,
        "decision": group.decision_json or {},
        "attempts": attempts,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }
```

- [ ] **Step 4: Run A/B service tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_service.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 4: Add A/B API Endpoints

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_ab_api.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`

- [ ] **Step 1: Write failing API tests**

Create `server/tests/test_image_ab_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ab_preview_rejects_single_strategy():
    resp = client.post("/api/image-production/ab-tests/preview", json={
        "mode": "text_to_image",
        "prompt": "api ab",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": ["one"],
        "count": 1,
    })

    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID"


def test_ab_group_read_returns_not_found():
    resp = client.get("/api/image-production/ab-tests/missing")

    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_GROUP_NOT_FOUND"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_api.py -v -p no:cacheprovider
```

Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Add request models and endpoints**

Modify `server/app/routers/image_production.py` imports:

```python
from app.services.image_ab_test_service import (
    adopt_ab_winner,
    create_ab_group,
    get_ab_group,
    mark_ab_no_winner,
    preview_ab_group,
    refresh_ab_group,
    serialize_ab_group,
)
```

Add request models:

```python
class AbPreviewRequest(BaseModel):
    mode: str
    prompt: str
    negative_prompt: str = ""
    destination_role: str | None = None
    strategy_ids: list[str] = Field(default_factory=list)
    source: dict | None = None
    source_url: str | None = None
    source_asset_id: str | None = None
    reference_images: list[dict] = Field(default_factory=list)
    size: str | None = None
    count: int = 1
    output_format: str | None = None
    response_format: str | None = None
    watermark: bool | None = None
    provider_options: dict = Field(default_factory=dict)


class AbCreateRequest(AbPreviewRequest):
    preview_request_hash: str | None = None
    cost_confirmation: bool = False
    idempotency_key: str | None = None


class AbDecisionRequest(BaseModel):
    reason: str = ""
    notes: str = ""
```

Add endpoints before `/strategies/{strategy_id}`:

```python
@router.post("/ab-tests/preview")
def ab_preview(body: AbPreviewRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    user_id = user[0] if isinstance(user, tuple) else None
    return preview_ab_group(db, body.model_dump(), user_id=user_id)


@router.post("/ab-tests")
async def ab_create(body: AbCreateRequest, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    user_id = user[0] if isinstance(user, tuple) else None
    group = await create_ab_group(db, body.model_dump(), user_id=user_id)
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.get("/ab-tests/{group_id}")
def ab_read(group_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return {"ok": True, "ab_group": serialize_ab_group(db, get_ab_group(db, group_id))}


@router.post("/ab-tests/{group_id}/refresh")
def ab_refresh(group_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    group = refresh_ab_group(db, group_id)
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.post("/ab-tests/{group_id}/winner/{attempt_id}")
def ab_winner(group_id: str, attempt_id: str, body: AbDecisionRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    group = adopt_ab_winner(db, group_id, attempt_id, body.model_dump())
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.post("/ab-tests/{group_id}/no-winner")
def ab_no_winner(group_id: str, body: AbDecisionRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    group = mark_ab_no_winner(db, group_id, body.model_dump())
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}
```

Modify `task_payload()` in `server/app/services/image_creation_service.py`:

```python
"ab_test_group_id": task.ab_test_group_id,
```

Also modify the `ImageCreationTask(...)` construction inside `create_image_task()` so the association is durable before the first task commit:

```python
ab_test_group_id=payload.get("ab_test_group_id"),
```

- [ ] **Step 4: Run API tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_api.py tests/test_image_ab_service.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 5: Add Frontend A/B API And Workbench Flow

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\api\imageProduction.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-page.test.js`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-a11y.test.js`

- [ ] **Step 1: Write failing frontend A/B tests**

Extend the hoisted `mocks` object in `web/src/__tests__/image-creation-page.test.js`:

```javascript
previewImageAbTest: vi.fn(),
createImageAbTest: vi.fn(),
getImageAbTest: vi.fn(),
refreshImageAbTest: vi.fn(),
chooseImageAbWinner: vi.fn(),
chooseImageAbNoWinner: vi.fn(),
```

Extend the `vi.mock('../api/imageProduction.js', ...)` return value:

```javascript
previewImageAbTest: mocks.previewImageAbTest,
createImageAbTest: mocks.createImageAbTest,
getImageAbTest: mocks.getImageAbTest,
refreshImageAbTest: mocks.refreshImageAbTest,
chooseImageAbWinner: mocks.chooseImageAbWinner,
chooseImageAbNoWinner: mocks.chooseImageAbNoWinner,
```

Append to `web/src/__tests__/image-creation-page.test.js`:

```javascript
it('previews and creates A/B image comparison with explicit cost confirmation', async () => {
  mocks.listImageProductionStrategies.mockResolvedValueOnce({
    data: {
      strategies: [
        { id: 'strategy-a', name: '策略 A', destination_role: 'storyboard_first_frame', version: 1, status: 'active' },
        { id: 'strategy-b', name: '策略 B', destination_role: 'storyboard_first_frame', version: 1, status: 'active' },
      ],
    },
  })
  mocks.previewImageAbTest.mockResolvedValueOnce({
    data: {
      ok: true,
      request_hash: 'sha256:ab',
      strategy_count: 2,
      attempt_previews: [
        { strategy_id: 'strategy-a', strategy: { name: '策略 A' }, cost_estimate: { amount: 1, currency: 'CNY' } },
        { strategy_id: 'strategy-b', strategy: { name: '策略 B' }, cost_estimate: { amount: 1.5, currency: 'CNY' } },
      ],
      total_cost_estimate: { amount: 2.5, currency: 'CNY', requires_confirmation: true },
      warnings: ['A/B comparison will create 2 image tasks.'],
    },
  })
  mocks.createImageAbTest.mockResolvedValueOnce({
    data: { ok: true, ab_group: { id: 'group-1', status: 'running', attempts: [] } },
  })

  const wrapper = mount(Page)
  await flushPromises()

  await wrapper.get('[data-testid="image-prompt"]').setValue('ab prompt')
  await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
  await wrapper.get('[data-testid="ab-strategy-strategy-a"]').setValue(true)
  await wrapper.get('[data-testid="ab-strategy-strategy-b"]').setValue(true)
  await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
  await flushPromises()

  expect(wrapper.text()).toContain('A/B 对比')
  expect(wrapper.text()).toContain('2.5 CNY')

  await wrapper.get('[data-testid="ab-cost-confirmation"]').setValue(true)
  await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
  await flushPromises()

  expect(mocks.createImageAbTest).toHaveBeenCalledWith(expect.objectContaining({
    prompt: 'ab prompt',
    strategy_ids: ['strategy-a', 'strategy-b'],
    preview_request_hash: 'sha256:ab',
    cost_confirmation: true,
  }))
})
```

- [ ] **Step 2: Run frontend test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js
```

Expected: FAIL because the A/B API wrapper and UI controls do not exist.

- [ ] **Step 3: Add frontend API wrapper functions**

Modify `web/src/api/imageProduction.js`:

```javascript
export function previewImageAbTest(payload) {
  return client.post('/image-production/ab-tests/preview', payload)
}

export function createImageAbTest(payload) {
  return client.post('/image-production/ab-tests', payload)
}

export function getImageAbTest(groupId) {
  return client.get(`/image-production/ab-tests/${groupId}`)
}

export function refreshImageAbTest(groupId) {
  return client.post(`/image-production/ab-tests/${groupId}/refresh`)
}

export function chooseImageAbWinner(groupId, attemptId, payload) {
  return client.post(`/image-production/ab-tests/${groupId}/winner/${attemptId}`, payload)
}

export function chooseImageAbNoWinner(groupId, payload) {
  return client.post(`/image-production/ab-tests/${groupId}/no-winner`, payload)
}
```

- [ ] **Step 4: Add A/B state to ImageCreationPage**

Modify `web/src/views/ImageCreationPage.vue` script:

```javascript
import {
  chooseImageAbNoWinner,
  chooseImageAbWinner,
  createImageAbTest,
  previewImageAbTest,
  refreshImageAbTest,
} from '../api/imageProduction.js'

const abMode = ref(false)
const abStrategyIds = ref([])
const abPreview = ref(null)
const abGroup = ref(null)
const abCostConfirmed = ref(false)
const abLoading = ref(false)
const abError = ref('')

function buildAbPayload() {
  return {
    mode: form.mode,
    prompt: form.prompt,
    negative_prompt: form.negativePrompt || '',
    destination_role: form.destination_role || selectedStrategy.value?.destination_role || '',
    strategy_ids: [...abStrategyIds.value],
    source: form.source || null,
    source_url: form.sourceUrl || null,
    source_asset_id: form.sourceAssetId || null,
    reference_images: form.referenceImages || [],
    size: form.size || null,
    count: form.count || 1,
    output_format: form.output_format || null,
    response_format: form.response_format || null,
    watermark: form.watermark,
    provider_options: form.providerOptions || {},
  }
}

async function runAbPreview() {
  abError.value = ''
  abLoading.value = true
  abCostConfirmed.value = false
  try {
    const resp = await previewImageAbTest(buildAbPayload())
    abPreview.value = resp.data
  } catch (err) {
    abError.value = normalizeError(err)
  } finally {
    abLoading.value = false
  }
}

async function createAbComparison() {
  abError.value = ''
  abLoading.value = true
  try {
    const resp = await createImageAbTest({
      ...buildAbPayload(),
      preview_request_hash: abPreview.value?.request_hash || null,
      cost_confirmation: abCostConfirmed.value,
      idempotency_key: `ab-${Date.now()}`,
    })
    abGroup.value = resp.data.ab_group
  } catch (err) {
    abError.value = normalizeError(err)
  } finally {
    abLoading.value = false
  }
}

async function refreshAbComparison() {
  if (!abGroup.value?.id) return
  const resp = await refreshImageAbTest(abGroup.value.id)
  abGroup.value = resp.data.ab_group
}

async function chooseAbWinner(attempt) {
  const resp = await chooseImageAbWinner(abGroup.value.id, attempt.id, { reason: 'manual_selection' })
  abGroup.value = resp.data.ab_group
}

async function chooseNoAbWinner() {
  const resp = await chooseImageAbNoWinner(abGroup.value.id, { reason: 'no_attempt_met_quality_bar' })
  abGroup.value = resp.data.ab_group
}
```

- [ ] **Step 5: Add A/B markup**

Add this near the normal strategy selector:

```html
<button
  type="button"
  data-testid="ab-mode-toggle"
  class="min-h-11 border px-3 py-2 text-sm"
  :class="abMode ? 'border-sky-500 text-sky-200' : 'border-slate-700 text-slate-300'"
  :aria-pressed="abMode"
  @click="abMode = !abMode"
>
  A/B 对比
</button>
```

Add this panel inside the trust rail:

```html
<section v-if="abMode" data-testid="ab-comparison-panel" class="space-y-3 border border-slate-800 bg-slate-950/70 p-4">
  <div class="flex items-center justify-between gap-3">
    <h3 class="text-sm font-semibold text-slate-100">A/B 策略对比</h3>
    <button
      type="button"
      data-testid="ab-preview-button"
      class="min-h-11 border border-sky-500/40 px-3 py-2 text-sm text-sky-200"
      :disabled="abLoading || abStrategyIds.length < 2"
      @click="runAbPreview"
    >
      预览 A/B 成本
    </button>
  </div>
  <div class="grid gap-2 sm:grid-cols-2">
    <label
      v-for="strategy in strategies"
      :key="strategy.id"
      class="flex min-h-11 items-center gap-2 border border-slate-800 px-3 py-2 text-sm text-slate-300"
    >
      <input
        v-model="abStrategyIds"
        type="checkbox"
        :value="strategy.id"
        :data-testid="`ab-strategy-${strategy.id}`"
      />
      <span>{{ strategy.name }} v{{ strategy.version }}</span>
    </label>
  </div>
  <p v-if="abError" class="text-sm text-rose-300">{{ abError }}</p>
  <div v-if="abPreview" class="space-y-2">
    <p class="text-sm text-amber-200">
      总成本：{{ abPreview.total_cost_estimate?.amount }} {{ abPreview.total_cost_estimate?.currency }}
    </p>
    <label class="flex min-h-11 items-center gap-2 text-sm text-slate-300">
      <input v-model="abCostConfirmed" data-testid="ab-cost-confirmation" type="checkbox" />
      <span>我确认本次 A/B 会同时创建 {{ abPreview.strategy_count }} 个图片任务</span>
    </label>
    <button
      type="button"
      data-testid="ab-create-button"
      class="min-h-11 border border-emerald-500/40 bg-emerald-600 px-3 py-2 text-sm text-white"
      :disabled="abPreview.total_cost_estimate?.requires_confirmation && !abCostConfirmed"
      @click="createAbComparison"
    >
      创建 A/B 对比
    </button>
  </div>
  <div v-if="abGroup" class="space-y-2">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-sm text-emerald-300">A/B 组已创建：{{ abGroup.id }}</p>
      <div class="flex gap-2">
        <button type="button" data-testid="ab-refresh-button" class="min-h-11 border border-slate-700 px-3 py-2 text-sm" @click="refreshAbComparison">
          刷新结果
        </button>
        <button type="button" data-testid="ab-no-winner-button" class="min-h-11 border border-amber-500/40 px-3 py-2 text-sm text-amber-200" @click="chooseNoAbWinner">
          本轮无胜出
        </button>
      </div>
    </div>
    <div class="grid gap-3 lg:grid-cols-2">
      <div v-for="attempt in abGroup.attempts" :key="attempt.id" class="border border-slate-800 p-3 text-sm">
        <p class="text-slate-100">{{ attempt.strategy_id }} · {{ attempt.status }}</p>
        <p class="text-slate-500">任务：{{ attempt.task_id }}</p>
        <p class="text-slate-500">成本：{{ attempt.metrics?.estimated_cost?.amount || attempt.metrics?.actual_cost || 0 }}</p>
        <button
          type="button"
          :data-testid="`ab-choose-winner-${attempt.id}`"
          class="mt-3 min-h-11 border border-emerald-500/40 px-3 py-2 text-sm text-emerald-200 disabled:opacity-50"
          :disabled="!attempt.approved_asset_ready"
          @click="chooseAbWinner(attempt)"
        >
          选为胜出
        </button>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 5A: Add a winner-action frontend test**

Append to `web/src/__tests__/image-creation-page.test.js`:

```javascript
it('refreshes A/B comparison and only enables winner action for approved attempts', async () => {
  mocks.listImageProductionStrategies.mockResolvedValueOnce({
    data: {
      strategies: [
        { id: 'strategy-a', name: '策略 A', destination_role: 'storyboard_first_frame', version: 1, status: 'active' },
        { id: 'strategy-b', name: '策略 B', destination_role: 'storyboard_first_frame', version: 1, status: 'active' },
      ],
    },
  })
  mocks.previewImageAbTest.mockResolvedValueOnce({
    data: {
      ok: true,
      request_hash: 'sha256:ab',
      strategy_count: 2,
      attempt_previews: [],
      total_cost_estimate: { amount: 1, currency: 'CNY', requires_confirmation: false },
      warnings: [],
    },
  })
  mocks.createImageAbTest.mockResolvedValueOnce({
    data: {
      ok: true,
      ab_group: {
        id: 'group-1',
        status: 'completed',
        attempts: [
          { id: 'attempt-a', strategy_id: 'strategy-a', status: 'completed', approved_asset_ready: true, metrics: {} },
          { id: 'attempt-b', strategy_id: 'strategy-b', status: 'failed', approved_asset_ready: false, metrics: {} },
        ],
      },
    },
  })
  mocks.chooseImageAbWinner.mockResolvedValueOnce({
    data: { ok: true, ab_group: { id: 'group-1', status: 'winner_selected', winner_attempt_id: 'attempt-a', attempts: [] } },
  })

  const wrapper = mount(Page)
  await flushPromises()

  await wrapper.get('[data-testid="image-prompt"]').setValue('ab winner prompt')
  await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
  await wrapper.get('[data-testid="ab-strategy-strategy-a"]').setValue(true)
  await wrapper.get('[data-testid="ab-strategy-strategy-b"]').setValue(true)
  await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
  await flushPromises()
  await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
  await flushPromises()

  expect(wrapper.get('[data-testid="ab-choose-winner-attempt-a"]').attributes('disabled')).toBeUndefined()
  expect(wrapper.get('[data-testid="ab-choose-winner-attempt-b"]').attributes('disabled')).toBeDefined()
  await wrapper.get('[data-testid="ab-choose-winner-attempt-a"]').trigger('click')
  await flushPromises()

  expect(mocks.chooseImageAbWinner).toHaveBeenCalledWith('group-1', 'attempt-a', { reason: 'manual_selection' })
})
```

- [ ] **Step 6: Run frontend A/B tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js
```

Expected: PASS.

## Task 6: Add Strategy Center Metrics And Winner Controls

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`
- Extend: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-production-strategy-page.test.js`

- [ ] **Step 1: Add failing frontend strategy metrics test**

Append to `web/src/__tests__/image-production-strategy-page.test.js`:

```javascript
it('shows strategy metrics and low sample warning', async () => {
  vi.spyOn(api, 'listImageProductionStrategies').mockResolvedValue({
    data: {
      strategies: [{
        id: 'strategy-1',
        name: '策略指标',
        destination_role: 'storyboard_first_frame',
        status: 'active',
        version: 1,
        metrics: {
          attempt_count: 3,
          success_rate: 0.66,
          average_cost_amount: 1.2,
          currency: 'CNY',
          average_latency_seconds: 18,
          low_sample: true,
        },
      }],
    },
  })

  const wrapper = mount(Page)
  await flushPromises()

  expect(wrapper.text()).toContain('66%')
  expect(wrapper.text()).toContain('1.2 CNY')
  expect(wrapper.text()).toContain('样本不足')
})
```

- [ ] **Step 2: Run strategy page test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-production-strategy-page.test.js
```

Expected: FAIL because metrics columns are not rendered.

- [ ] **Step 3: Add optional metrics payload on strategy list**

Modify `server/app/routers/image_production.py` `strategies()` endpoint:

```python
include_metrics: bool = Query(False),
```

Use this serialization:

```python
from app.db_models import ImageProductionMetric
from app.services.image_production_metrics_service import strategy_metrics_payload


def _strategy_payload_with_metrics(db: Session, row, include_metrics: bool):
    payload = strategy_payload(row)
    if include_metrics:
        metric = (
            db.query(ImageProductionMetric)
            .filter(ImageProductionMetric.strategy_id == row.id)
            .filter(ImageProductionMetric.strategy_version == row.version)
            .first()
        )
        payload["metrics"] = strategy_metrics_payload(metric)
    return payload
```

Return:

```python
return {"ok": True, "strategies": [_strategy_payload_with_metrics(db, row, include_metrics) for row in rows]}
```

- [ ] **Step 4: Render metrics in strategy page**

Modify `web/src/views/ImageProductionStrategiesPage.vue` strategy row to include:

```html
<span>{{ Math.round((strategy.metrics?.success_rate || 0) * 100) }}%</span>
<span>{{ strategy.metrics?.average_cost_amount || 0 }} {{ strategy.metrics?.currency || 'CNY' }}</span>
<span>{{ strategy.metrics?.average_latency_seconds || 0 }}s</span>
<span v-if="strategy.metrics?.low_sample" class="text-xs text-amber-300">样本不足</span>
```

Ensure `loadStrategies()` calls:

```javascript
const resp = await listImageProductionStrategies({ include_metrics: true })
```

- [ ] **Step 5: Run strategy page tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-production-strategy-page.test.js src/__tests__/navigation.test.js
```

Expected: PASS.

## Task 7: Regression And Verification

**Files:**
- No source files should be modified unless tests expose a Phase 4 bug.

- [ ] **Step 1: Run backend Phase 4 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_service.py tests/test_image_ab_api.py tests/test_image_production_metrics_service.py tests/test_image_production_migration.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run backend image production regression**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py tests/test_image_production_cost_service.py tests/test_image_selection_preview_service.py tests/test_image_creation_strategy_snapshot.py tests/test_image_asset_bridge.py tests/test_image_creation_api.py tests/test_image_creation_models.py tests/test_image_creation_model_resolution.py tests/test_image_creation_pixelle_client.py tests/test_image_creation_mocked_e2e.py -v -p no:cacheprovider
```

Expected: PASS. Existing SQLAlchemy expression-index warning is acceptable.

- [ ] **Step 3: Run frontend Phase 4 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/image-production-strategy-page.test.js src/__tests__/navigation.test.js
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run build
```

Expected: PASS. Existing Vite large chunk warning is acceptable if there are no errors.

- [ ] **Step 5: Secret scan**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
$pattern = 'ark-[0-9a-fA-F-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|(api_key|access_token|client_secret)\s*[:=]\s*["''][^"'']{8,}'
$matches = rg -n $pattern server/app web/src
if ($LASTEXITCODE -eq 1) { 'NO_MATCHES'; exit 0 }
$matches
exit $LASTEXITCODE
```

Expected: `NO_MATCHES`.

- [ ] **Step 6: Review checkpoint**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short server/app/db_models.py server/alembic/versions/3c4d5e6f7081_image_production_phase4_ab_metrics.py server/app/services/image_ab_test_service.py server/app/services/image_production_metrics_service.py server/app/routers/image_production.py server/app/services/image_creation_service.py server/tests/test_image_ab_service.py server/tests/test_image_ab_api.py server/tests/test_image_production_metrics_service.py server/tests/test_image_production_migration.py web/src/api/imageProduction.js web/src/views/ImageCreationPage.vue web/src/views/ImageProductionStrategiesPage.vue web/src/__tests__/image-creation-page.test.js web/src/__tests__/image-production-strategy-page.test.js web/src/__tests__/image-creation-a11y.test.js
```

Expected: only Phase 4 files are listed from this plan, plus unrelated pre-existing worktree changes outside this file set.

## Phase 4 Completion Criteria

- A/B preview requires 2 to 4 active strategies.
- A/B preview returns per-attempt selected model, selection explanation, capacity/review gate summary, and cost estimate.
- A/B create requires matching preview hash when supplied.
- A/B create requires explicit confirmation when total cost requires confirmation.
- A/B create writes one group and one attempt per strategy.
- Every attempt creates a normal `ImageCreationTask` and stores `ab_test_group_id`.
- Attempt creation uses derived idempotency keys.
- A/B group refresh updates attempt statuses from tasks and updates strategy metrics.
- Winner adoption requires an approved image asset from the selected attempt.
- No-winner decision is explicit and final.
- Strategy metrics show attempt count, success rate, AI/human pass rate, average cost, average latency, repaint count, and low-sample warning.
- Image creation UI supports A/B mode without disrupting the normal single-strategy generation flow.
- Strategy center shows metrics without scanning all tasks on every page render.
- Backend focused and regression tests pass.
- Frontend focused tests and build pass.
- Secret scan finds no production credential leaks.

## Deferred To Later Phases

- Scheduled metric aggregation worker.
- Full strategy analytics dashboard.
- Automatic strategy recommendation or mutation.
- Cross-series experiment reports.
- Real provider staging E2E.
- A visual A/B gallery with image zoom and side-by-side pixel comparison.

## Self-Review

Spec coverage:

| Spec requirement | Covered by |
|---|---|
| A/B group and attempt records | Task 0 schema and Task 2 service |
| Cost multiplication confirmation | Task 2 preview/create service and Task 5 frontend confirmation |
| Winner adoption flow | Task 3 service and Task 4 API |
| No-winner state | Task 3 service and Task 4 API |
| Metrics feedback loop | Task 1 service and Task 6 strategy center |
| Strategy table metrics | Task 6 frontend and metrics payload |
| Attempt idempotency | Task 2 derived idempotency key |
| Avoid automatic strategy mutation | Explicit out-of-scope and winner adoption is manual |
| Do not bypass existing image creation path | Task 2 creates attempts through `create_image_task` |

Placeholder scan:

- No forbidden placeholder vocabulary or vague edge-case instructions are used.
- Each task has concrete files, test code, implementation code, commands, and expected results.
- Every new function referenced in later tasks is introduced in an earlier task.

Type and contract consistency:

- Backend payload fields are consistent: `strategy_ids`, `preview_request_hash`, `cost_confirmation`, `ab_test_group_id`, `winner_attempt_id`, and `metrics_snapshot_json`.
- Frontend API functions match backend routes: `previewImageAbTest`, `createImageAbTest`, `getImageAbTest`, `refreshImageAbTest`, `chooseImageAbWinner`, and `chooseImageAbNoWinner`.
- Strategy metrics use one shape in backend and frontend: `attempt_count`, `success_rate`, `average_cost_amount`, `currency`, `average_latency_seconds`, and `low_sample`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-image-production-strategy-control-plane-phase4.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Recommended order: Task 0 -> Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7. Task 5 can begin UI skeleton work after Task 4 response contracts are stable.

## Autoplan Review Report

Autoplan reviewed this Phase 4 plan through CEO, design, engineering, and DX lenses after Phase 3 completion.

### CEO Review

Verdict: **hold scope with targeted hardening**.

Premise challenge:

- Right problem: yes. Phase 4 closes the deferred quality loop from the design spec: compare strategies, pick winners, and feed metrics back into strategy operations.
- Proxy risk: medium before revision. A/B groups without durable group idempotency would look like experimentation but could duplicate spend on retry.
- Dream state delta: this phase moves dy_auto from "generate reviewed images" to "learn which image strategy works for which video asset role." It still intentionally stops short of autonomous strategy mutation.

Scope decision:

- Keep A/B, winner adoption, and metrics in scope.
- Do not add a full analytics dashboard, scheduled metric worker, or automatic strategy optimizer in this phase.
- Add group-level idempotency, real winner actions in UI, and low-sample warnings as required scope because they protect spend and operator trust.

Error and rescue registry:

| Code path | Failure | Error code | User sees | Test |
|---|---|---|---|---|
| A/B preview | strategy count outside 2-4 | `IMAGE_AB_TEST_STRATEGY_COUNT_INVALID` | choose 2 to 4 active strategies | `test_preview_ab_group_requires_multiple_strategies` |
| A/B create | total cost requires confirmation | `IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED` | confirm total A/B cost | service/API tests |
| A/B create | request differs from preview | `IMAGE_AB_TEST_PREVIEW_DRIFT` | rerun preview | service tests |
| A/B create | idempotency key reused with different request | `IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT` | use a new key or restore original request | idempotency service test |
| Winner adoption | attempt has no approved asset | `IMAGE_AB_TEST_ATTEMPT_NOT_READY` | approve generated image first | winner service test |
| Winner adoption | final decision already exists | `IMAGE_AB_TEST_WINNER_CONFLICT` | open existing decision | winner conflict test |

Failure modes registry:

| Code path | Failure mode | Rescued | Test | User sees | Critical gap |
|---|---|---:|---:|---|---:|
| Migration | old Phase 3 head assertion not updated | yes | yes | migration test failure before implementation | no |
| Test DB cleanup | A/B tables leak between tests | yes | yes | isolated tests remain deterministic | no |
| Group creation | browser retry duplicates all attempts | yes | yes | same A/B group returned | no |
| Attempt creation | task exists but group id not durable before first commit | yes | yes | attempt remains linked to group | no |
| Metrics | retry actual-cost events double-count | yes | yes | average cost uses latest actual per task | no |
| UI | A/B creates group but cannot choose winner | yes | yes | winner/no-winner controls visible | no |

### Design Review

Initial design score: **7.2/10**. Revised score: **8.6/10**.

| Dimension | Before | After | Revision |
|---|---:|---:|---|
| Information architecture | 7 | 8.5 | A/B mode stays secondary and does not interrupt normal generation. |
| Interaction states | 7 | 8.5 | Added refresh, approved-ready, disabled winner, and no-winner states. |
| User journey | 7 | 8.5 | Operator can preview cost, create attempts, inspect results, and pick a winner in one flow. |
| Specificity | 7 | 8.5 | Added concrete A/B card markup and test IDs. |
| Design system fit | 8 | 8.5 | Reuses dense slate operational panels and 8px-or-less surfaces. |
| Responsive/a11y | 7 | 8.5 | A/B attempt cards use grid-to-stack behavior and text labels, not color-only states. |
| Unresolved decisions | 2 | 0 | Winner availability and no-winner behavior are now explicit. |

Design requirements added:

- A/B comparison is not the default path; it appears only after the operator enables A/B mode.
- Attempt cards must show strategy, status, task id, cost/metric summary, and winner eligibility.
- Winner action is disabled unless `approved_asset_ready` is true.
- No-winner is a visible explicit action, not an implicit failed state.
- A/B refresh is visible because attempt status changes asynchronously through existing image task sync.

### Engineering Review

Verdict: **cleared after revision**.

Architecture graph:

```text
ImageCreationPage
  -> imageProduction.js
     -> /api/image-production/ab-tests/preview
     -> /api/image-production/ab-tests
     -> /api/image-production/ab-tests/{id}/refresh
     -> /api/image-production/ab-tests/{id}/winner/{attempt}
        -> image_ab_test_service.py
           -> create_selection_preview()
           -> create_image_task()
           -> ImageProductionAbGroup
           -> ImageProductionAbAttempt
           -> ImageCreationTask.ab_test_group_id
           -> image_production_metrics_service.py
              -> ImageProductionMetric
              -> ImageProductionCostEvent
              -> ImageCreationAsset / ImageCreationReviewRecord
```

Issues found and fixed in the plan:

| Severity | Issue | Fix |
|---|---|---|
| P1 | A/B group creation had no group-level idempotency, so retry could duplicate spend. | Added `idempotency_key`, unique constraint, conflict error, and same-request reuse test. |
| P1 | Existing migration test still expected Phase 3 as Alembic head. | Updated Phase 4 migration test to assert `3c4d5e6f7081` as head. |
| P1 | New A/B tables were not added to `conftest.py` cleanup. | Added explicit cleanup order for groups, attempts, and metrics. |
| P1 | `create_image_task()` payload association could be written only after the first internal commit. | Added explicit `ab_test_group_id=payload.get("ab_test_group_id")` requirement in task construction. |
| P2 | Metrics could double-count multiple actual cost events for one retried task. | Changed metric plan to use latest actual cost event per task and added a retry-cost test. |
| P2 | Frontend tests referenced A/B mock functions not added to the hoisted mock contract. | Added mock extension instructions before the tests. |
| P2 | API tests used non-existent `auth_headers` fixture. | Rewrote API tests to follow existing `TestClient(app)` pattern and auth override. |

Test diagram:

| Code path / UX path | Unit | API | Frontend | Regression |
|---|---:|---:|---:|---:|
| Phase 4 migration graph and tables | yes | n/a | n/a | `test_image_production_migration.py` |
| Metrics aggregation from task/asset/review/cost | yes | n/a | n/a | image production regression |
| Latest actual-cost per task | yes | n/a | n/a | metrics service |
| A/B preview strategy count and cost | yes | yes | yes | image creation page |
| A/B create preview drift and cost confirmation | yes | yes | yes | image creation page |
| Group idempotency reuse/conflict | yes | yes | n/a | A/B service |
| Attempt task creation through existing image path | yes | yes | n/a | image creation strategy snapshot |
| Refresh updates attempt statuses | yes | yes | yes | A/B workbench |
| Winner requires approved asset | yes | yes | yes | A/B workbench |
| No-winner decision | yes | yes | yes | A/B workbench |
| Strategy center metrics and low-sample warning | yes | API payload | yes | strategy page |

Performance review:

- Strategy list with `include_metrics=true` must read pre-aggregated `ImageProductionMetric`; it must not scan all tasks/assets per page load.
- A/B preview performs one selection preview per strategy; strategy count remains capped at 4.
- Metrics refresh scans only tasks for one strategy/version/model or one A/B group refresh path, not the full task table.
- Add indexes on group status, attempt group/task/status, and metric strategy/version.

### DX Review

DX score: **8.3/10** after revision.

Developer journey:

| Stage | Expected developer action | Plan support |
|---|---|---|
| Find entrypoint | Open Phase 4 plan | Source material and file structure are explicit. |
| Add schema | Create models and migration | Concrete ORM and Alembic snippets provided. |
| Keep tests isolated | Update conftest cleanup | Added after review. |
| Implement metrics | Add service and tests | Concrete tests and code path provided. |
| Implement A/B backend | Add service/API | Concrete payloads, endpoints, and errors provided. |
| Wire frontend | Add API wrapper and page controls | Concrete mocks, state, and markup provided. |
| Verify | Run focused and regression suites | Commands listed with expected outputs. |
| Debug failure | Named errors and rescue actions | Error table and rescue actions included. |
| Ship safely | Run secret scan and review checkpoint | Commands included. |

DX fixes added:

- Removed fixture ambiguity from API tests.
- Added missing frontend mock contract updates.
- Added implementation checkpoint for test cleanup, which prevents confusing cross-test failures.
- Added group idempotency contract so retry behavior is predictable for developers and operators.

### NOT in scope after autoplan

- Automatic winner selection.
- Automatic strategy mutation based on metrics.
- Scheduled metrics worker.
- Standalone analytics dashboard.
- Provider-online E2E against real image/video models.
- Visual image zoom/pixel comparison gallery.

### What already exists and is reused

- `ImageCreationTask` remains the single execution path.
- `create_selection_preview()` remains the selection/cost/capacity preview primitive.
- `create_image_task()` remains the task creation primitive for each A/B attempt.
- `ImageProductionCostEvent` remains the source for estimated/actual spend.
- `ImageCreationAsset` and `ImageCreationReviewRecord` remain the source for approval and review state.
- Existing Vue workbench and strategy center are extended, not replaced.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Keep Phase 4 scoped to A/B and feedback loop, not a full analytics product | Auto-decided | Focus as subtraction | The design spec explicitly defers dashboards and autonomous mutation. | Add a separate analytics dashboard now |
| 2 | CEO/Eng | Add group-level A/B idempotency | Auto-decided | Spend safety | Browser retry must not create duplicate paid attempts. | Rely only on per-attempt idempotency |
| 3 | Eng | Update migration head expectations to Phase 4 | Auto-decided | Executable plan | Existing migration test currently asserts Phase 3 as the head. | Leave failing migration test for implementer to discover |
| 4 | Eng | Add A/B tables to session DB cleanup | Auto-decided | Test determinism | The project uses a session-scoped in-memory DB and explicit cleanup order. | Let A/B rows leak between tests |
| 5 | Eng | Persist `ab_test_group_id` inside `create_image_task()` construction | Auto-decided | Durable association | The task-group link should exist before the first internal commit. | Patch task after service returns |
| 6 | Eng | Count latest actual cost once per task | Auto-decided | Metric integrity | Retries can create multiple actual cost events and must not inflate averages. | Average every actual cost event |
| 7 | Design | Add winner and no-winner actions to the A/B workbench panel | Auto-decided | Workflow closure | A/B without a visible final decision is not a complete operator flow. | Show only task ids after group creation |
| 8 | DX | Replace non-existent `auth_headers` test fixture with existing auth override pattern | Auto-decided | Follow local patterns | Current backend tests use global `TestClient(app)` and auth overrides. | Invent a new fixture in this plan |
| 9 | DX | Add frontend mock contract before A/B page tests | Auto-decided | Test executability | Vitest hoisted mocks must declare new API functions before imports. | Let tests fail at mock resolution |

## Plan Design Review Addendum

Design review classification: **APP UI**. This is an operator workbench, not a landing page. The design target is a dense, calm production console that keeps the existing image creation flow primary and exposes A/B comparison only when the operator deliberately enables it.

System audit:

- Project `DESIGN.md`: not present.
- Existing UI vocabulary to reuse: dark operational shell, trust rail, compact task panels, status chips, `data-testid`-driven Vue tests.
- Primary files this plan extends: `web/src/views/ImageCreationPage.vue` and `web/src/views/ImageProductionStrategiesPage.vue`.
- Design risk: the A/B panel can become a generic card stack unless the plan fixes hierarchy, states, and action gating.

### First-Screen Information Architecture

The A/B comparison UI must not replace the normal image workbench. It appears as a controlled extension inside the existing generation page.

```text
+----------------------------------------------------------------------------------+
| Image creation header: prompt context, current scene, submit status               |
+-----------------------------------------------+----------------------------------+
| Main work area                                 | Trust rail                        |
| - prompt textarea                              | - selected model                  |
| - image mode controls                          | - estimated cost                  |
| - model selector                               | - provider warnings               |
| - common parameters                            | - audit/review status             |
| - dynamic provider parameters                  |                                  |
|                                               | A/B comparison panel              |
|                                               | - enable toggle                   |
|                                               | - strategy picker                 |
|                                               | - cost preview                    |
|                                               | - create group action             |
+-----------------------------------------------+----------------------------------+
| A/B result area after group exists                                                |
| - attempt cards: strategy, status, asset preview, review state, cost, winner      |
| - refresh, no-winner decision, retry/review links                                 |
+----------------------------------------------------------------------------------+
```

Three facts must be visible above the fold when A/B mode is enabled:

1. Normal single-strategy generation remains the default path.
2. A/B mode will create N paid generation tasks, with total estimated cost visible before submit.
3. Winner selection is unavailable until an attempt has an approved image asset.

Desktop layout contract:

- At `>=1280px`, keep the existing two-column layout: main work area `1fr`, trust rail `360px`.
- A/B settings live in the trust rail because they modify submission risk and cost.
- A/B result cards live below the main editor and use two columns only after a group exists.

Tablet and mobile layout contract:

- At `768px-1279px`, place the trust rail and A/B settings below the main editor to avoid cramped controls.
- At `<=767px`, use a single column. Strategy checkboxes are full-width rows, attempt cards are stacked, and action buttons are full-width with minimum `44px` touch targets.
- No horizontal scrolling is allowed in the workbench, strategy picker, or attempt comparison area.

### Interaction State Coverage

| Feature | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| A/B strategy picker | Skeleton rows with disabled create action | "No enabled strategies for this scene" with link to strategy center | Inline error with retry | Selectable strategy rows with model, version, and sample count | Some strategies disabled with visible reason |
| A/B cost preview | Cost row shows calculating state | Preview not requested yet; primary action is preview | Drift/conflict warning and refresh action | Total estimated cost, attempt count, and per-strategy cost visible | Mixed warnings per strategy, create still blocked if any hard error exists |
| A/B group creation | Create button shows pending state and locks inputs | Group not created; preview remains visible | Conflict/spend/capacity error shown in panel | Group id, attempt count, and refresh action shown | Group created but some attempts failed; failed attempts remain visible |
| Attempt comparison cards | Card placeholders preserve dimensions | "No image asset yet" with task status | Failed attempt shows error text and retry/review link if available | Approved asset preview, strategy metadata, cost, review state, winner button | Some attempts approved, some pending; eligible buttons only on approved cards |
| Winner/no-winner controls | Decision button shows saving state | Disabled until group exists | Conflict/not-ready error with exact blocking reason | Winner or no-winner decision shown as final state | Ineligible attempts disabled with visible reason such as "requires approved review" |
| Strategy metrics table | Skeleton table rows | Low/no sample message with explanation | Retry banner, no broken table | Metrics columns render with latest values | Low-sample warning chip on affected rows |

Visual behavior requirements:

- Disabled actions must explain why in visible text, not only a tooltip.
- Color is never the only state indicator; every chip also includes text.
- A/B errors use the same compact warning style as the existing workbench trust rail.

### User Journey Storyboard

| Step | User does | User feels | Plan support |
|---|---|---|---|
| 1 | Opens image workbench | Familiar, not interrupted | Existing single-strategy flow remains primary |
| 2 | Enables A/B mode | In control, aware this is optional | Toggle reveals scoped panel only inside the workbench |
| 3 | Selects 2-4 strategies | Comparing without guessing | Strategy rows expose model, version, sample count, and warnings |
| 4 | Previews cost | Financially safe | Total estimated cost and attempt count appear before create |
| 5 | Creates A/B group | Confident the workflow is tracked | Group id and attempt cards appear immediately |
| 6 | Waits or refreshes | Not lost | Cards show task/review state and refresh action |
| 7 | Uses review flow | Clear quality gate | Winner buttons stay disabled until approved asset exists |
| 8 | Picks winner or no-winner | Decision is durable | Final decision state is shown on the group and later strategy metrics |

Time-horizon design:

- 5 seconds: user sees that normal generation still works and A/B is optional.
- 5 minutes: user can submit, wait, refresh, review, and decide without reading backend logs.
- 5 years: metrics explain why a strategy is trusted or retired, using recorded outcomes rather than memory.

### Responsive And Accessibility Contract

Keyboard order:

1. A/B mode toggle.
2. Strategy checkboxes.
3. Preview cost.
4. Cost confirmation.
5. Create A/B group.
6. Refresh/no-winner actions.
7. Winner buttons on eligible attempt cards.

Accessibility rules:

- `ab-mode-toggle` uses `aria-pressed`.
- A/B status and errors use `aria-live="polite"`.
- Attempt cards expose strategy name, review state, task state, cost, and winner eligibility as text.
- All interactive controls meet minimum `44px` touch target height on mobile.
- Body text contrast must meet at least `4.5:1`.
- Placeholder text is not the only label for any field.
- Winner buttons that are disabled include visible reason text such as "requires approved review".

### AI Slop Risk Controls

The implementation must avoid:

- Decorative gradient panels.
- Icon bubble grids.
- Centered marketing sections.
- Repeating card mosaics where layout would be clearer.
- Hero-style copy or promotional wording.
- New visual decoration unrelated to production status.

Accepted design direction:

- Use compact production language: "A/B comparison", "estimated cost", "approved asset", "winner", "no winner".
- Use cards only for attempt comparison because each attempt is an inspectable unit.
- Keep the right rail operational: risk, cost, state, and decision controls.
- Keep typography and spacing aligned with the existing image workbench instead of introducing a new design system.

### What Already Exists

- `ImageCreationPage.vue` already has the dark workbench surface, trust rail, task panel, and review card patterns.
- `ImageProductionStrategiesPage.vue` already has the strategy table/editor surface and can receive metrics without a new dashboard.
- Existing Vitest patterns rely on explicit `data-testid` selectors.
- Existing API wrapper/mocking conventions are sufficient for the new frontend tests.
- There is no project `DESIGN.md`; this addendum is the design source for Phase 4 implementation.

### Not In Scope

- New gallery zoom or pixel comparison tool.
- Standalone analytics dashboard.
- Marketing, onboarding, or hero-style pages.
- New global design system.
- Automatic winner selection.
- 3D visualization or decorative expert-team UI changes.
- Real provider-online visual QA.

### Backlog Updates

No deferred design debt is being added. The information architecture, state coverage, mobile rules, accessibility rules, and visual constraints above are folded directly into the Phase 4 implementation plan.

### DESIGN PLAN REVIEW - COMPLETION SUMMARY

| Area | Result |
|---|---|
| System audit | No project `DESIGN.md`; UI scope is app workbench and strategy center |
| Step 0 | Initial score 7.6/10; focus areas were hierarchy, states, mobile, and a11y |
| Pass 1 - Info architecture | 7.8/10 -> 9.0/10 after fixes |
| Pass 2 - Interaction states | 7.4/10 -> 9.0/10 after fixes |
| Pass 3 - User journey | 7.6/10 -> 8.8/10 after fixes |
| Pass 4 - AI slop risk | 8.2/10 -> 9.0/10 after fixes |
| Pass 5 - Design system | 7.5/10 -> 8.6/10 after fixes |
| Pass 6 - Responsive and a11y | 7.2/10 -> 8.8/10 after fixes |
| Pass 7 - Decisions | 5 resolved, 0 deferred |
| Not in scope | Written, 7 items |
| What already exists | Written |
| Backlog updates | 0 items proposed |
| Approved mockups | 0 generated, 0 approved |
| Decisions made | 5 added to plan |
| Decisions deferred | 0 |
| Overall design score | 7.6/10 -> 8.9/10 |

Unresolved design decisions: **0**.

Plan is design-complete for Phase 4. Run live design QA after implementation to verify real spacing, text overflow, keyboard order, and mobile behavior.

## Plan Engineering Review Addendum

This review was run after the design addendum. Scope is accepted as-is: Phase 4 is still the right minimum complete unit because A/B groups, attempts, winner decisions, and metrics must ship together to close the image strategy feedback loop. The plan remains intentionally inside existing image production surfaces and does not introduce a new runtime artifact or distribution path.

### Findings Applied

1. **[P1] (confidence: 9/10) `server/app/services/image_ab_test_service.py` planned `create_ab_group()` does not handle partial attempt creation failure.**

   Existing `create_image_task()` commits task state internally before Pixelle submission and can later raise provider errors. If attempt 1 is saved and attempt 2 fails, the current plan can return an error while already having persisted paid or queued work. Mandatory fix:

   - Add `partial_failed` as an allowed A/B group status.
   - Add a per-attempt `try/except` inside `create_ab_group()` around `await create_image_task(...)`.
   - On one attempt failure, call `db.rollback()`, preserve the failed `ImageProductionAbAttempt`, store a redacted error summary in `metrics_snapshot_json["error"]`, set attempt status to `failed`, continue creating remaining attempts, and return the group.
   - Set group status to `failed` only when every attempt fails, `partial_failed` when at least one attempt fails and at least one attempt exists, otherwise `running`.
   - Update `refresh_ab_group()` so an attempt with status `failed` and no `task_id` counts as terminal.
   - Add `test_create_ab_group_records_partial_failure_when_one_attempt_fails`.

   Required test shape:

   ```python
   @pytest.mark.asyncio
   async def test_create_ab_group_records_partial_failure_when_one_attempt_fails(db, monkeypatch):
       model = _model(db)
       first = _strategy(db, model, "first-partial")
       second = _strategy(db, model, "second-partial")
       calls = {"count": 0}

       async def fake_create_image_task(db, payload):
           from app.db_models import ImageCreationTask
           calls["count"] += 1
           if calls["count"] == 2:
               raise RuntimeError("provider rejected attempt")
           task = ImageCreationTask(
               mode=payload["mode"],
               output_mode="single",
               capability_key="text_to_image",
               status="running",
               prompt=payload["prompt"],
               count=1,
               target_count=1,
               strategy_id=payload["strategy_id"],
               strategy_version=payload["strategy_version"],
               ab_test_group_id=payload["ab_test_group_id"],
               idempotency_key=payload["idempotency_key"],
               model_id=model.id,
           )
           db.add(task)
           db.flush()
           return task

       monkeypatch.setattr("app.services.image_ab_test_service.create_image_task", fake_create_image_task)

       group = await create_ab_group(db, {
           "mode": "text_to_image",
           "prompt": "partial group",
           "destination_role": "storyboard_first_frame",
           "strategy_ids": [first.id, second.id],
           "count": 1,
           "cost_confirmation": True,
           "idempotency_key": "partial-ab",
       }, user_id="user-1")

       statuses = {attempt.status for attempt in group.attempts_for_test}
       assert group.status == "partial_failed"
       assert statuses == {"running", "failed"}
   ```

2. **[P2] (confidence: 9/10) `server/app/routers/image_production.py` planned metrics payload adds an N+1 query.**

   The plan's Task 6 helper queries `ImageProductionMetric` once per strategy row. It avoids scanning tasks/assets, but still scales linearly by query count. Mandatory fix:

   - Replace per-row metric lookup with one batched metrics query when `include_metrics=true`.
   - Build a dictionary keyed by `(strategy_id, strategy_version, model_id)`.
   - Pass the matched metric into a pure serializer helper.
   - Keep the default `include_metrics=false` path unchanged.

   Required implementation shape:

   ```python
   def _strategy_payload_with_metric(row, metric):
       payload = strategy_payload(row)
       payload["metrics"] = strategy_metrics_payload(metric)
       return payload


   def _metrics_by_strategy(db: Session, rows: list[ImageProductionStrategy]) -> dict[tuple[str, int, str | None], ImageProductionMetric]:
       if not rows:
           return {}
       strategy_ids = [row.id for row in rows]
       metrics = db.query(ImageProductionMetric).filter(ImageProductionMetric.strategy_id.in_(strategy_ids)).all()
       return {
           (metric.strategy_id, metric.strategy_version, metric.model_id): metric
           for metric in metrics
       }
   ```

   The route then reads metrics once and serializes with:

   ```python
   metric_map = _metrics_by_strategy(db, rows) if include_metrics else {}
   return {
       "ok": True,
       "strategies": [
           _strategy_payload_with_metric(
               row,
               metric_map.get((row.id, row.version, row.default_model_id)),
           ) if include_metrics else strategy_payload(row)
           for row in rows
       ],
   }
   ```

3. **[P2] (confidence: 8/10) A/B API tests cover route rejection and not-found, but not successful create/refresh/winner route serialization.**

   Service tests cover most logic, but route contracts can still fail through missing imports, wrong async handling, dependency wiring, or payload serialization. Mandatory fix:

   - Extend `server/tests/test_image_ab_api.py` with one happy route test for `POST /api/image-production/ab-tests`.
   - Extend the same file with a winner-not-ready route test for `POST /api/image-production/ab-tests/{group_id}/winner/{attempt_id}`.
   - Use `monkeypatch` to stub `app.services.image_ab_test_service.create_image_task` so no provider call occurs.

4. **[P2] (confidence: 8/10) Frontend tests do not yet pin the new design-review accessibility contract.**

   Task 5 mentions extending `image-creation-a11y.test.js`, but does not specify the assertions. Mandatory fix:

   - Assert `data-testid="ab-mode-toggle"` exposes `aria-pressed`.
   - Assert A/B status/error output has `aria-live="polite"`.
   - Assert disabled winner buttons render visible reason text such as `需先通过审查`.
   - Assert mobile layout selectors/classes keep the A/B panel and attempt cards single-column under the existing responsive shell.

5. **[P3] (confidence: 10/10) The design addendum referenced `web/src/pages/...`, but this project uses `web/src/views/...`.**

   Fixed in this document. Implementation must use `web/src/views/ImageCreationPage.vue` and `web/src/views/ImageProductionStrategiesPage.vue`.

### Data Flow Diagram

```text
Operator enables A/B
  -> ImageCreationPage.vue
     -> previewImageAbTest(payload)
        -> POST /api/image-production/ab-tests/preview
           -> preview_ab_group()
              -> create_selection_preview() for each strategy
              -> total cost + request hash
  -> createImageAbTest(payload + confirmed hash)
     -> POST /api/image-production/ab-tests
        -> create_ab_group()
           -> ImageProductionAbGroup
           -> ImageProductionAbAttempt per strategy
           -> create_image_task() per attempt
              -> existing image task admission/cost/provider path
           -> partial_failed if any attempt fails after group creation
  -> refreshImageAbTest(group_id)
     -> refresh_ab_group()
        -> sync attempt status from ImageCreationTask
        -> refresh_image_strategy_metrics()
  -> chooseImageAbWinner()
     -> adopt_ab_winner()
        -> requires approved ImageCreationAsset
        -> writes final group decision
```

### Test Coverage Diagram

```text
CODE PATHS                                             USER FLOWS
[+] image_production.py routes                         [+] A/B workbench
  |-- [covered] preview rejects invalid count             |-- [covered] preview + create
  |-- [added] create route serializes group               |-- [covered] refresh + winner enabled state
  |-- [added] winner route returns not-ready error        |-- [added] disabled winner reason is visible
  |-- [covered] read route returns not found              |-- [added] a11y live region and toggle state

[+] image_ab_test_service.py
  |-- [covered] preview cost/hash
  |-- [covered] idempotency reuse/conflict
  |-- [added] partial attempt failure returns group
  |-- [covered] refresh terminal state
  |-- [covered] winner requires approved asset
  |-- [covered] no-winner decision

[+] image_production_metrics_service.py
  |-- [covered] counts tasks/assets/reviews/costs
  |-- [covered] idempotent refresh
  |-- [covered] latest actual cost once per task

[+] strategy metrics route
  |-- [added] batched metric lookup for include_metrics=true
  |-- [covered] default path omits metrics unless requested
```

Coverage after this addendum: all planned backend service branches, route contract branches, and primary frontend interaction states have explicit tests in the plan. No E2E browser framework exists in this repo, so Phase 4 stays with pytest route/service tests and Vitest component tests.

### Failure Modes Registry

| Code path | Realistic failure | Planned handling | Test |
|---|---|---|---|
| A/B create attempt 2 fails after attempt 1 task is persisted | Partial paid/queued work could be hidden behind a 500 | Return group as `partial_failed`, preserve failed attempt error | `test_create_ab_group_records_partial_failure_when_one_attempt_fails` |
| Metrics strategy list with many strategies | Per-row metric lookup causes avoidable N+1 queries | Batch metrics by strategy ids | Strategy route test with `include_metrics=true` |
| Winner route called before asset approval | Operator selects unreviewed image | 409 `IMAGE_AB_TEST_ATTEMPT_NOT_READY` and visible disabled reason | Service, API, and frontend tests |
| A/B retry with same idempotency key | Duplicate spend | Reuse same group for same request, conflict for different request | Existing idempotency tests |
| A/B preview stale before create | Operator confirms old cost | 409 `IMAGE_AB_TEST_PREVIEW_DRIFT` | Existing service tests |

Critical gaps after this addendum: **0**.

### What Already Exists

- Existing `create_image_task()` remains the only image execution path.
- Existing `create_selection_preview()` remains the cost/model/capacity preview primitive.
- Existing `ImageCreationAsset` and `ImageCreationReviewRecord` remain the quality gate sources.
- Existing `ImageProductionCostEvent` remains the cost source.
- Existing Vue workbench and strategy center remain the UI surfaces.

### Not In Scope

- New scheduler or background metrics worker; metrics refresh stays synchronous to explicit A/B refresh and strategy reads.
- New browser E2E framework; the repo currently uses pytest and Vitest.
- Real provider-online E2E; provider behavior remains mocked in Phase 4 tests.
- Standalone A/B analytics dashboard; metrics appear in the strategy center.
- Automatic winner selection or autonomous strategy mutation.

### Backlog Updates

No deferred engineering backlog items are added. All review findings above are mandatory Phase 4 plan amendments.

### Worktree Parallelization Strategy

| Step | Modules touched | Depends on |
|---|---|---|
| Schema and migration | `server/app`, `server/alembic`, `server/tests` | none |
| Metrics service and route payload | `server/app/services`, `server/app/routers`, `server/tests` | schema |
| A/B service and API routes | `server/app/services`, `server/app/routers`, `server/tests` | schema, metrics service |
| Frontend workbench A/B UI | `web/src/api`, `web/src/views`, `web/src/__tests__` | API contract stable |
| Strategy center metrics UI | `web/src/views`, `web/src/__tests__` | metrics API contract stable |
| Regression verification | `server/tests`, `web/src/__tests__`, build | all implementation lanes |

Parallel lanes:

- Lane A: schema -> metrics service -> strategy metrics route.
- Lane B: A/B service -> A/B API routes.
- Lane C: frontend API mocks and UI skeleton after API response contracts are stable.
- Lane D: strategy center metrics UI after metrics response contract is stable.

Execution order: launch Lane A and Lane B sequentially until schema is merged, then Lane C and Lane D can proceed in parallel. Final regression verification is sequential.

Conflict flags: Lane A and Lane B both touch `server/app/routers/image_production.py`; coordinate route edits or merge Lane A before Lane B.

### ENG PLAN REVIEW - COMPLETION SUMMARY

- Step 0: Scope Challenge - scope accepted as-is; no new artifact distribution path.
- Architecture Review: 2 issues found and fixed in plan (`partial_failed` group handling, route/API serialization coverage).
- Code Quality Review: 1 issue found and fixed in plan (`web/src/views` path correction).
- Test Review: diagram produced, 2 gaps identified and fixed in plan (route happy/error tests, frontend a11y/responsive assertions).
- Performance Review: 1 issue found and fixed in plan (batched metrics lookup).
- Not in scope: written.
- What already exists: written.
- Backlog updates: 0 items proposed.
- Failure modes: 0 critical gaps after fixes.
- Outside voice: skipped; this was a plan-stage engineering rerun after design changes.
- Parallelization: 4 lanes, 2 partially parallel after schema.
- Lake Score: 5/5 findings chose the complete option.

Unresolved engineering decisions: **0**.

## OpenClaw CEO Review Addendum

Status: **DONE**.

Mode: **HOLD SCOPE**. The baseline scope is right: Phase 4 should not become a standalone analytics product, but it must make the A/B loop trustworthy enough that operators can understand cost, quality, and final decisions six months later.

### Step 0 - Nuclear Scope Challenge

Premise:

- Right problem: yes. The current image production control plane already has model selection, strategy rules, cost preview, capacity preview, review gates, and image tasks. The missing business outcome is learning which strategy actually produces usable assets without duplicating spend or hiding failures.
- Proxy risk: medium. If Phase 4 only counts attempts and winners, operators may optimize for "winner selected" instead of actual approved, reusable, cost-effective images.
- Do nothing outcome: strategy quality remains anecdotal; operators keep manually guessing which model/strategy works, and cost drift remains hard to explain.

Existing leverage:

- `create_image_task()` already owns execution, provider submission, cost event creation, capacity, and task serialization.
- `create_selection_preview()` already owns model/cost/capacity/review preview.
- `ImageCreationAsset` and `ImageCreationReviewRecord` already represent the quality gate.
- `ImageProductionCostEvent` already records estimated and actual cost.
- `ImageProductionStrategy` already has versioning and policy links.

Twelve-month ideal:

```text
Current state
  -> image tasks and strategy config exist, but strategy quality is mostly manual memory
This plan
  -> A/B group, attempts, cost preview, explicit winner/no-winner, and metrics feedback
12-month ideal
  -> operators can explain why a strategy is trusted, when it became worse, what it costs, and which approved assets prove it
```

Approaches considered:

| Approach | Summary | Effort | Risk | Reuses | Decision |
|---|---|---|---|---|---|
| Minimal viable | Add A/B groups and manual winner only | M | Medium | image task and review flow | Rejected: does not close the feedback loop |
| Current Phase 4 | Add A/B groups, attempts, winner/no-winner, metrics, and workbench UI | L | Medium | all existing image production primitives | Accepted |
| Ideal architecture | Add experiment analytics, scheduled metric jobs, anomaly alerts, and automatic strategy mutation | XL | High | partial reuse | Deferred: too much for this phase |

CEO recommendation: keep the current Phase 4 scope, but add three trust-hardening requirements below. These are not product expansion; they make the accepted scope credible.

### Strongest Challenges Applied

1. **A/B cost confirmation is not enough without a hard group-level spend guard.**

   Why this matters: A/B intentionally multiplies paid image tasks. A checkbox saying "I confirm" protects against accidental clicks, but not against a bad strategy/policy combination that estimates far above the intended experiment budget.

   Mandatory amendment:

   - Add optional A/B hard cap support using the existing cost policy snapshot. Name the field `ab_max_group_cost`.
   - In `preview_ab_group()`, compute `total_cost_estimate.amount` as already planned and include `ab_max_group_cost` when present.
   - In `create_ab_group()`, reject creation when total estimate exceeds the hard cap, even if `cost_confirmation=true`.
   - Add named error:

     | Error code | HTTP | Trigger | User sees |
     |---|---:|---|---|
     | `IMAGE_AB_TEST_COST_LIMIT_EXCEEDED` | 409 | total A/B estimate exceeds policy `ab_max_group_cost` | lower strategy count, reduce image count/options, or adjust policy |

   Required tests:

   - `test_preview_ab_group_returns_group_cost_cap_when_policy_sets_it`
   - `test_create_ab_group_rejects_when_total_cost_exceeds_ab_group_cap`

2. **Winner decisions need an evidence snapshot, not just a winner id and notes.**

   Why this matters: Six months later, strategy metrics and assets may have changed. The operator must be able to answer: "Why did we select this winner at the time?"

   Mandatory amendment:

   - When `adopt_ab_winner()` runs, write `group.decision_json["evidence_snapshot"]`.
   - When `mark_ab_no_winner()` runs, write the same evidence snapshot with `decision="no_winner"`.
   - Snapshot must include:
     - all attempt ids, task ids, strategy ids, strategy versions, model ids, statuses
     - approved asset ids available at decision time
     - estimated/actual cost fields available at decision time
     - review state and `approved_asset_ready`
     - selected winner attempt id or `null`
     - user reason/notes
     - decision timestamp
   - Do not store secrets, provider raw errors, or full provider config.

   Required tests:

   - `test_adopt_ab_winner_stores_decision_evidence_snapshot`
   - `test_mark_ab_no_winner_stores_all_attempt_evidence`

3. **Observability must show whether A/B is improving production or just adding spend.**

   Why this matters: Metrics rows show quality after refresh, but operators still need an operational trail for experiment creation, partial failures, final decisions, and spend risk.

   Mandatory amendment:

   - Add structured log or audit event emission for:
     - `image_ab.preview`
     - `image_ab.create`
     - `image_ab.partial_failed`
     - `image_ab.winner_selected`
     - `image_ab.no_winner`
   - Each event includes `group_id`, strategy count, total estimated cost, status, winner attempt id when present, and redacted error code when present.
   - If existing `ProductionAuditEvent` is too video-production-specific, use application logs in this phase; do not add a new audit table in Phase 4.
   - Add a runbook note to the plan: if A/B spend increases but winner/no-winner decisions are not being recorded, pause A/B usage and inspect review workflow adoption.

   Required tests:

   - Service tests assert audit/log helper is called on create, partial failure, winner, and no-winner paths using monkeypatch.

### 11-Section CEO Review

| Section | Verdict | Notes |
|---|---|---|
| Architecture | Pass with amendments | Correctly wraps existing image execution instead of creating a second renderer. Add spend hard cap and decision evidence snapshot. |
| Error and rescue map | Pass with amendment | Existing named errors are good; add `IMAGE_AB_TEST_COST_LIMIT_EXCEEDED`. |
| Security and threat model | Pass | Admin-gated routes and provider option validation remain inside existing paths. Evidence snapshots must exclude secrets/raw provider config. |
| Data flow and edge cases | Pass with amendment | Partial failure was already fixed by engineering review. Add hard cap and evidence snapshot paths. |
| Code quality | Pass | Keep A/B orchestration in one service and metrics in one service. Do not create dashboard abstractions. |
| Tests | Pass with amendment | Add cost-cap, decision-evidence, and audit/log tests. |
| Observability | Needs amendment | Add structured events and runbook note. This is the biggest CEO-level gap. |
| Database and state | Pass | New A/B and metrics tables are justified. No additional table needed for this review. |
| API contract | Pass | Endpoint shape is coherent and backward-compatible. Add cost-limit error to interface section. |
| Performance and scalability | Pass | Strategy metrics batching from engineering review handles the main query risk. |
| Design and UX | Pass | Design review correctly keeps A/B secondary and makes cost/winner eligibility visible. |

### Accepted Scope

- A/B strategy preview for 2-4 active strategies.
- Group-level idempotency and derived attempt idempotency.
- Cost multiplication preview, explicit confirmation, and hard group-level cost cap when configured.
- One normal `ImageCreationTask` per attempt.
- Partial-failure visibility through `partial_failed`.
- Manual winner/no-winner decision.
- Decision evidence snapshot for winner/no-winner.
- Strategy metrics feedback into the strategy center.
- Structured A/B operational events or logs.

### Deferred

- Standalone experiment analytics dashboard.
- Scheduled metrics worker.
- Automatic winner selection.
- Automatic strategy mutation.
- Provider-online E2E.
- New audit table dedicated only to image A/B.

### Not In Scope

- Replacing the image task execution path.
- Building a visual A/B gallery or pixel comparison tool.
- Changing Pixelle/Seedream provider integration.
- Creating a separate experimentation product.
- Making A/B mode the default generation path.

### CEO REVIEW SUMMARY

- **Mode:** HOLD SCOPE.
- **Strongest challenges:** hard spend guard, decision evidence snapshot, A/B operational observability.
- **Recommended path:** implement Phase 4 as planned with the three mandatory trust amendments above.
- **Accepted scope:** A/B comparison, attempt ledger, winner/no-winner, metrics, cost hardening, evidence snapshot, and operational events.
- **Deferred:** analytics dashboard, scheduled worker, auto winner, auto mutation, provider-online E2E.
- **Completion status:** DONE.

## Post-OpenClaw Engineering Review Addendum

This review validates the OpenClaw CEO amendments against the current codebase. The amendments are accepted, but they must be wired into concrete Phase 4 tasks instead of remaining as plan-level principles.

### Findings Applied

1. **[P1] (confidence: 9/10) OpenClaw cost cap requirement needs a deterministic policy source and aggregation rule.**

   The existing cost policy runtime already reads `ImageProductionPolicyVersion.snapshot_json` through `estimate_image_cost()`. Do not create a separate A/B policy table. Extend the existing cost policy shape with optional `ab_max_group_cost`.

   Mandatory implementation details:

   - Modify `DEFAULT_COST_POLICY` in `server/app/services/image_production_policy_runtime.py`:

     ```python
     DEFAULT_COST_POLICY = {
         "unit_cost": 1.0,
         "currency": "CNY",
         "confirmation_threshold": 1.0,
         "latency_seconds_per_image": 10,
         "ab_max_group_cost": None,
     }
     ```

   - Modify `estimate_image_cost()` to include `ab_max_group_cost` when configured:

     ```python
     cap = policy.get("ab_max_group_cost")
     if cap is not None:
         result["ab_max_group_cost"] = float(cap)
     ```

   - In `preview_ab_group()`, collect non-null `ab_max_group_cost` values from attempt previews and use the strictest cap:

     ```python
     caps = [
         float((preview.get("cost_estimate") or {}).get("ab_max_group_cost"))
         for preview in previews
         if (preview.get("cost_estimate") or {}).get("ab_max_group_cost") is not None
     ]
     group_cap = min(caps) if caps else None
     total["ab_max_group_cost"] = group_cap
     total["cost_limit_exceeded"] = group_cap is not None and total["amount"] > group_cap
     ```

   - In `_ensure_preview_matches()`, reject create when the limit is exceeded even if `cost_confirmation=true`:

     ```python
     if preview["total_cost_estimate"].get("cost_limit_exceeded"):
         raise image_error(
             409,
             "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED",
             "A/B comparison exceeds the configured group cost limit.",
             "Lower strategy count, reduce image count/options, or adjust the cost policy.",
             retryable=False,
             details={"total_cost_estimate": preview["total_cost_estimate"]},
         )
     ```

   Required tests:

   - Add to `server/tests/test_image_production_policy_runtime.py`: `test_estimate_image_cost_includes_ab_group_cap`.
   - Add to `server/tests/test_image_ab_service.py`: `test_preview_ab_group_returns_group_cost_cap_when_policy_sets_it`.
   - Add to `server/tests/test_image_ab_service.py`: `test_create_ab_group_rejects_when_total_cost_exceeds_ab_group_cap`.
   - Add to `web/src/__tests__/image-creation-page.test.js`: frontend displays the cost-cap block and disables A/B create.

2. **[P1] (confidence: 9/10) Evidence snapshot must be a stable helper, not ad hoc JSON built inside winner methods.**

   Winner and no-winner decisions are long-lived records. Build one helper and reuse it from both decision paths.

   Mandatory implementation details:

   - Add `_ab_decision_evidence_snapshot(db, group, winner_attempt_id, decision)` to `image_ab_test_service.py`.
   - Snapshot shape:

     ```python
     {
         "decision": "winner" | "no_winner",
         "winner_attempt_id": winner_attempt_id,
         "reason": decision.get("reason") or "",
         "notes": decision.get("notes") or "",
         "decided_at": bj_now().isoformat(),
         "attempts": [{
             "attempt_id": attempt.id,
             "task_id": attempt.task_id,
             "strategy_id": attempt.strategy_id,
             "strategy_version": attempt.strategy_version,
             "model_id": attempt.model_id,
             "status": attempt.status,
             "approved_asset_ready": approved,
             "approved_asset_ids": approved_asset_ids,
             "metrics": attempt.metrics_snapshot_json or {},
             "task_status": task.status if task else None,
             "estimated_cost": task.estimated_cost_json if task else {},
         }],
     }
     ```

   - Do not include `provider_response_json`, `model_trace_json`, `pixelle_payload_json`, API keys, provider config, or raw provider errors.
   - `adopt_ab_winner()` sets:

     ```python
     group.decision_json = {
         "winner_attempt_id": attempt.id,
         **(decision or {}),
         "evidence_snapshot": _ab_decision_evidence_snapshot(db, group, attempt.id, decision or {}),
     }
     ```

   - `mark_ab_no_winner()` sets the same snapshot with `winner_attempt_id=None`.

   Required tests:

   - `test_adopt_ab_winner_stores_decision_evidence_snapshot`.
   - `test_mark_ab_no_winner_stores_all_attempt_evidence`.
   - A negative assertion that the snapshot does not contain `provider_response_json`, `model_trace_json`, `pixelle_payload_json`, or `api_key`.

3. **[P2] (confidence: 8/10) A/B observability should reuse `ProductionAuditEvent`, not invent a logging-only path.**

   The existing `server/app/services/production_observability.py` has `record_production_event()` and redacts secret-like keys. `ProductionAuditEvent` fields are nullable except `event_type`, so image A/B can reuse it without adding a new table.

   Mandatory implementation details:

   - Import:

     ```python
     from app.services.production_observability import record_production_event
     ```

   - Add helper:

     ```python
     def _record_ab_event(db: Session, event_type: str, payload: dict[str, Any]) -> None:
         record_production_event(
             db,
             event_type=event_type,
             payload={
                 "scope": "image_ab",
                 **payload,
             },
         )
     ```

   - Emit these events:

     | Event | Trigger |
     |---|---|
     | `image_ab.preview` | preview returns request hash and cost summary |
     | `image_ab.create` | group created or reused by idempotency |
     | `image_ab.partial_failed` | one or more attempts fail during group creation |
     | `image_ab.winner_selected` | winner decision is saved |
     | `image_ab.no_winner` | no-winner decision is saved |

   - Event payload must include `group_id` when available, `strategy_count`, `total_cost_estimate`, `status`, `winner_attempt_id` when present, and redacted `error_code` when present.
   - Because `create_selection_preview()` already persists preview rows, recording `image_ab.preview` in the same request is acceptable.

   Required tests:

   - `test_preview_ab_group_records_audit_event`.
   - `test_create_ab_group_records_create_and_partial_failure_events`.
   - `test_adopt_ab_winner_records_audit_event`.
   - `test_mark_ab_no_winner_records_audit_event`.
   - Assert `ProductionAuditEvent` cleanup remains in `server/tests/conftest.py`; it already is, so no new cleanup work is required.

4. **[P2] (confidence: 8/10) API and UI contracts must expose the new cost-limit state before users pay.**

   The backend can reject create, but the workbench should show the blocked state immediately after preview.

   Mandatory implementation details:

   - Add `IMAGE_AB_TEST_COST_LIMIT_EXCEEDED` to the error catalog near the existing A/B errors.
   - Ensure `previewImageAbTest()` response surfaces:

     ```json
     {
       "total_cost_estimate": {
         "amount": 6.0,
         "currency": "CNY",
         "ab_max_group_cost": 5.0,
         "cost_limit_exceeded": true
       }
     }
     ```

   - `ImageCreationPage.vue` must disable `data-testid="ab-create-button"` when `abPreview.total_cost_estimate.cost_limit_exceeded` is true.
   - The disabled state must show visible Chinese text, for example `已超出A/B成本上限`.
   - Add API test asserting `POST /api/image-production/ab-tests` returns `IMAGE_AB_TEST_COST_LIMIT_EXCEEDED`.

5. **[P2] (confidence: 8/10) OpenClaw additions need to be reflected in the Phase 4 verification command list.**

   Add these focused tests to Task 7:

   ```powershell
   cd D:\devWorkspace\jsProjects\dy_auto\server
   python -m pytest tests/test_image_production_policy_runtime.py tests/test_image_ab_service.py tests/test_image_ab_api.py -k "ab_group_cap or evidence_snapshot or audit_event or COST_LIMIT" -v -p no:cacheprovider
   ```

   ```powershell
   cd D:\devWorkspace\jsProjects\dy_auto\web
   npx vitest run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js --run
   ```

### Updated Flow Diagram

```text
A/B preview
  -> create_selection_preview() per strategy
  -> estimate_image_cost() includes optional ab_max_group_cost
  -> strictest cap becomes total_cost_estimate.ab_max_group_cost
  -> if amount > cap, preview returns cost_limit_exceeded=true
  -> record ProductionAuditEvent(image_ab.preview)

A/B create
  -> recompute preview and hash
  -> reject preview drift
  -> reject unconfirmed cost
  -> reject IMAGE_AB_TEST_COST_LIMIT_EXCEEDED if cap exceeded
  -> create/reuse group by idempotency
  -> create attempts through create_image_task()
  -> record image_ab.create
  -> record image_ab.partial_failed if needed

Winner/no-winner
  -> validate final-decision conflict
  -> winner path requires approved asset
  -> build _ab_decision_evidence_snapshot()
  -> write group.decision_json.evidence_snapshot
  -> record image_ab.winner_selected or image_ab.no_winner
```

### Updated Test Coverage Diagram

```text
CODE PATHS                                             USER FLOWS
[+] policy runtime                                     [+] A/B preview
  |-- [added] ab_max_group_cost in estimate              |-- [added] shows cap and blocked state

[+] image_ab_test_service.py                           [+] A/B create
  |-- [added] strictest cap aggregation                  |-- [added] create disabled when cap exceeded
  |-- [added] cost-limit rejection                       |-- [covered] cost confirmation still required
  |-- [added] evidence snapshot for winner               |-- [covered] approved asset required
  |-- [added] evidence snapshot for no-winner            |-- [added] no-winner keeps evidence trail
  |-- [added] audit events for preview/create/decision   |-- [added] operator can inspect audit trail

[+] image_production.py API
  |-- [added] create returns IMAGE_AB_TEST_COST_LIMIT_EXCEEDED

[+] ImageCreationPage.vue
  |-- [added] visible Chinese cost-limit message
  |-- [added] disabled create button for exceeded cap
```

### Failure Modes Registry Update

| Code path | Realistic failure | Planned handling | Test |
|---|---|---|---|
| A/B preview combines strategies with different caps | Higher cap strategy masks lower cap strategy | Use strictest non-null cap | `test_preview_ab_group_returns_group_cost_cap_when_policy_sets_it` |
| A/B create runs after cap-exceeded preview | Paid tasks start despite policy cap | 409 `IMAGE_AB_TEST_COST_LIMIT_EXCEEDED` before attempts | service and API tests |
| Winner decision is reviewed months later | Current assets/metrics differ from decision time | Persist `evidence_snapshot` | winner/no-winner tests |
| A/B action fails silently in production | No operational trail | Record `ProductionAuditEvent` with `scope=image_ab` | audit-event tests |
| Frontend receives cap-exceeded preview | Operator can still click create | Disable create and show `已超出A/B成本上限` | Vitest page test |

Critical gaps after this addendum: **0**.

### What Already Exists

- Cost policy snapshots already flow through `ImageProductionPolicyVersion` and `estimate_image_cost()`.
- `ProductionAuditEvent` and `record_production_event()` already provide a redacted audit trail.
- `ImageCreationTask`, `ImageCreationAsset`, and `ImageProductionCostEvent` already contain evidence needed for winner snapshots.
- The image workbench already has visible cost, error, and disabled-action patterns to reuse.

### Not In Scope

- A new A/B policy table.
- A new image-specific audit event table.
- A scheduled observability worker or alerting service.
- Any automatic strategy mutation based on the new evidence snapshot.
- Provider-online E2E.

### ENG PLAN REVIEW RERUN - COMPLETION SUMMARY

- Step 0: Scope Challenge - scope accepted as-is; OpenClaw additions are trust hardening, not product expansion.
- Architecture Review: 2 issues found and fixed in plan (cost-cap source/aggregation, audit event reuse).
- Code Quality Review: 1 issue found and fixed in plan (shared evidence snapshot helper).
- Test Review: diagram produced, 5 gaps identified and fixed in plan.
- Performance Review: 0 new issues; prior batched metrics fix still covers query risk.
- Not in scope: written.
- What already exists: written.
- Backlog updates: 0 items proposed.
- Failure modes: 0 critical gaps after fixes.
- Outside voice: skipped; this was a focused rerun after OpenClaw amendments.
- Parallelization: unchanged from prior engineering review.
- Lake Score: 5/5 findings chose the complete option.

Unresolved engineering decisions after OpenClaw rerun: **0**.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| CEO Review | `/plan-ceo-review` + `/gstack-openclaw-ceo-review` | Scope and strategy | 2 | CLEAR | Hold scope; OpenClaw added hard spend guard, decision evidence snapshot, and A/B operational events |
| Codex Review | `/codex review` | Independent second opinion | 0 | not run | Not required for this plan-stage pass |
| Eng Review | `/plan-eng-review` | Architecture and tests | 3 | CLEAR | 17 total plan issues fixed; latest rerun made OpenClaw cost cap, evidence snapshot, audit events, and UI/API cap handling executable |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR | score: 7.6/10 -> 8.9/10, 5 decisions added |
| DX Review | `/plan-devex-review` | Developer experience gaps | 1 | CLEAR | 8.3/10, TTHW unchanged but fewer ambiguous test failures |

- **UNRESOLVED:** 0 decisions across current plan reviews.
- **VERDICT:** CEO + ENG + DESIGN + DX cleared. Ready to implement Phase 4.
