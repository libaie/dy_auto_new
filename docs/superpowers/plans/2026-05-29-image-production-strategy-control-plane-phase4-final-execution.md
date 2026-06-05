# Image Production Strategy Control Plane Phase 4 Final Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add A/B image strategy comparison, attempt ledger, explicit winner/no-winner decisions, strategy metrics, cost hard limits, decision evidence snapshots, and A/B audit events.

**Architecture:** Keep `POST /api/image-creation/tasks` as the only authoritative image execution path. Phase 4 wraps existing image tasks with A/B group/attempt records, reuses selection preview for cost/model/capacity checks, derives metrics from existing task/asset/review/cost rows, and writes final decisions as auditable group state.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Vite, Vitest, existing image production strategy/control-plane services.

---

## Source Material

- `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-29-image-production-strategy-control-plane-phase4.md`
- `D:\devWorkspace\jsProjects\dy_auto\memory\2026-05-29-image-production-phase4-openclaw-ceo-review.md`

## File Structure

Backend:

- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
  - Add `ImageProductionAbGroup`, `ImageProductionAbAttempt`, and `ImageProductionMetric`.
- Create `D:\devWorkspace\jsProjects\dy_auto\server\alembic\versions\3c4d5e6f7081_image_production_phase4_ab_metrics.py`
  - Add A/B group, A/B attempt, and strategy metrics tables.
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\tests\conftest.py`
  - Add new tables to cleanup order.
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_policy_runtime.py`
  - Add optional `ab_max_group_cost` to cost policy output.
- Create `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_metrics_service.py`
  - Refresh and serialize strategy metrics.
- Create `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_ab_test_service.py`
  - Own A/B preview, group creation, idempotency, partial failure handling, refresh, winner/no-winner, evidence snapshots, and audit events.
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
  - Add A/B endpoints and `include_metrics` support.
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
  - Include `ab_test_group_id` in task construction and serialization.

Frontend:

- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\api\imageProduction.js`
  - Add A/B API functions.
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
  - Add A/B workbench controls, preview, create, refresh, winner/no-winner, cost cap blocked state, and accessibility attributes.
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`
  - Show pre-aggregated strategy metrics.

Tests:

- Modify `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_migration.py`
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_policy_runtime.py`
- Create `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_metrics_service.py`
- Create `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_ab_service.py`
- Create `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_ab_api.py`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-page.test.js`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-a11y.test.js`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-production-strategy-page.test.js`

## Named Error Contract

| Error code | HTTP | Trigger |
|---|---:|---|
| `IMAGE_AB_TEST_STRATEGY_COUNT_INVALID` | 422 | A/B uses fewer than 2 or more than 4 strategies |
| `IMAGE_AB_TEST_STRATEGY_INACTIVE` | 422 | Any chosen strategy is not active |
| `IMAGE_AB_TEST_PREVIEW_DRIFT` | 409 | Create request differs from confirmed preview hash |
| `IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED` | 409 | Cost requires confirmation and caller did not confirm |
| `IMAGE_AB_TEST_COST_LIMIT_EXCEEDED` | 409 | Total A/B estimate exceeds `ab_max_group_cost` |
| `IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT` | 409 | Same A/B idempotency key used with a different request |
| `IMAGE_AB_TEST_GROUP_NOT_FOUND` | 404 | A/B group id does not exist |
| `IMAGE_AB_TEST_ATTEMPT_NOT_READY` | 409 | Winner attempt has no approved image asset |
| `IMAGE_AB_TEST_WINNER_CONFLICT` | 409 | Winner/no-winner decision already exists |

## Task 0: Schema And Migration

**Files:**

- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- Create `D:\devWorkspace\jsProjects\dy_auto\server\alembic\versions\3c4d5e6f7081_image_production_phase4_ab_metrics.py`
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_migration.py`
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\tests\conftest.py`

- [ ] **Step 1: Add failing migration tests**

Add these tests to `server/tests/test_image_production_migration.py`:

```python
def test_image_production_phase4_revision_depends_on_phase3(script):
    revision = script.get_revision("3c4d5e6f7081")
    assert revision.down_revision == "2b3c4d5e6f70"
    assert script.get_heads() == ["3c4d5e6f7081"]


def test_image_production_phase4_tables_exist(engine):
    from sqlalchemy import inspect

    inspector = inspect(engine)
    assert "image_production_ab_groups" in inspector.get_table_names()
    assert "image_production_ab_attempts" in inspector.get_table_names()
    assert "image_production_metrics" in inspector.get_table_names()
    group_columns = {column["name"] for column in inspector.get_columns("image_production_ab_groups")}
    assert {
        "id",
        "user_id",
        "idempotency_key",
        "source_request_hash",
        "prompt_snapshot_json",
        "cost_confirmation_json",
        "winner_attempt_id",
        "decision_json",
        "status",
    }.issubset(group_columns)
    attempt_columns = {column["name"] for column in inspector.get_columns("image_production_ab_attempts")}
    assert {
        "id",
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

- [ ] **Step 2: Run migration tests to verify failure**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py::test_image_production_phase4_revision_depends_on_phase3 tests/test_image_production_migration.py::test_image_production_phase4_tables_exist -v -p no:cacheprovider
```

Expected: FAIL because the Phase 4 migration and ORM models do not exist.

- [ ] **Step 3: Add ORM models**

Add after `ImageProductionCostEvent` in `server/app/db_models.py`:

```python
class ImageProductionAbGroup(Base):
    __tablename__ = "image_production_ab_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(160), nullable=True)
    source_request_hash = Column(String(80), nullable=False)
    prompt_snapshot_json = Column(JSON, nullable=False, default=dict)
    cost_confirmation_json = Column(JSON, nullable=True, default=dict)
    winner_attempt_id = Column(String(36), nullable=True)
    decision_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="running")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_image_ab_group_idempotency_key"),
        Index("idx_image_ab_groups_status", "status"),
        Index("idx_image_ab_groups_created", "created_at"),
        Index("idx_image_ab_groups_winner", "winner_attempt_id"),
    )


class ImageProductionAbAttempt(Base):
    __tablename__ = "image_production_ab_attempts"

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("image_production_ab_groups.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String(36), nullable=False)
    strategy_version = Column(Integer, nullable=False)
    model_id = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="creating")
    metrics_snapshot_json = Column(JSON, nullable=True, default=dict)
    human_decision_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("group_id", "strategy_id", "strategy_version", name="uq_image_ab_attempt_strategy"),
        Index("idx_image_ab_attempts_group", "group_id"),
        Index("idx_image_ab_attempts_task", "task_id"),
        Index("idx_image_ab_attempts_status", "status"),
    )


class ImageProductionMetric(Base):
    __tablename__ = "image_production_metrics"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), nullable=False)
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
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("strategy_id", "strategy_version", "model_id", name="uq_image_metric_strategy_version_model"),
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
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c4d5e6f7081"
down_revision: Union[str, Sequence[str], None] = "2b3c4d5e6f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_production_ab_groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("source_request_hash", sa.String(length=80), nullable=False),
        sa.Column("prompt_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("cost_confirmation_json", sa.JSON(), nullable=True),
        sa.Column("winner_attempt_id", sa.String(length=36), nullable=True),
        sa.Column("decision_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("idempotency_key", name="uq_image_ab_group_idempotency_key"),
    )
    op.create_index("idx_image_ab_groups_status", "image_production_ab_groups", ["status"])
    op.create_index("idx_image_ab_groups_created", "image_production_ab_groups", ["created_at"])
    op.create_index("idx_image_ab_groups_winner", "image_production_ab_groups", ["winner_attempt_id"])

    op.create_table(
        "image_production_ab_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("image_production_ab_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("image_creation_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="creating"),
        sa.Column("metrics_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("human_decision_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("group_id", "strategy_id", "strategy_version", name="uq_image_ab_attempt_strategy"),
    )
    op.create_index("idx_image_ab_attempts_group", "image_production_ab_attempts", ["group_id"])
    op.create_index("idx_image_ab_attempts_task", "image_production_ab_attempts", ["task_id"])
    op.create_index("idx_image_ab_attempts_status", "image_production_ab_attempts", ["status"])

    op.create_table(
        "image_production_metrics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("human_pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repaint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_latency_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("average_cost_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("strategy_id", "strategy_version", "model_id", name="uq_image_metric_strategy_version_model"),
    )
    op.create_index("idx_image_metrics_strategy", "image_production_metrics", ["strategy_id", "strategy_version"])
    op.create_index("idx_image_metrics_updated", "image_production_metrics", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_image_metrics_updated", table_name="image_production_metrics")
    op.drop_index("idx_image_metrics_strategy", table_name="image_production_metrics")
    op.drop_table("image_production_metrics")

    op.drop_index("idx_image_ab_attempts_status", table_name="image_production_ab_attempts")
    op.drop_index("idx_image_ab_attempts_task", table_name="image_production_ab_attempts")
    op.drop_index("idx_image_ab_attempts_group", table_name="image_production_ab_attempts")
    op.drop_table("image_production_ab_attempts")

    op.drop_index("idx_image_ab_groups_winner", table_name="image_production_ab_groups")
    op.drop_index("idx_image_ab_groups_created", table_name="image_production_ab_groups")
    op.drop_index("idx_image_ab_groups_status", table_name="image_production_ab_groups")
    op.drop_table("image_production_ab_groups")
```

- [ ] **Step 5: Update test cleanup**

Modify imports in `server/tests/conftest.py`:

```python
from app.db_models import (
    Base,
    Task,
    ChainInstance,
    DailyStats,
    Account,
    AccountGroup,
    AccountGroupMember,
    Channel,
    ChannelItem,
    Character,
    Scene,
    Series,
    Episode,
    PipelineRun,
    GeneratedVideo,
    AuditReport,
    ReferenceData,
    AIModel,
    User,
    VideoProductionRun,
    VideoProductionAsset,
    VideoReviewRecord,
    ImageProductionPolicyVersion,
    ImageProductionStrategy,
    ImageProductionStrategyVersion,
    ImageSelectionPreview,
    ImageCreationTask,
    ImageCreationAsset,
    ImageProductionCostEvent,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionMetric,
    ImageCreationReviewRecord,
    AgencyExpertInvocation,
    ProductionAuditEvent,
    ProductionCostEvent,
    ProductionJob,
    ProductionSegment,
    ProductionShot,
    ProductionScene,
    ProductionEpisode,
    ProductionPlanVersion,
    ProductionPlan,
    VideoCollection,
    series_characters,
    series_scenes,
)
```

Add cleanup order before `ImageCreationReviewRecord`:

```python
ImageProductionAbAttempt,
ImageProductionAbGroup,
ImageProductionMetric,
```

- [ ] **Step 6: Run migration tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 1: Cost Policy A/B Group Hard Cap

**Files:**

- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_policy_runtime.py`
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_policy_runtime.py`

- [ ] **Step 1: Add failing policy runtime test**

Add to `server/tests/test_image_production_policy_runtime.py`:

```python
def test_estimate_image_cost_includes_ab_group_cap(db):
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2.0,
        "currency": "CNY",
        "confirmation_threshold": 1.0,
        "latency_seconds_per_image": 8,
        "ab_max_group_cost": 5.0,
    })
    strategy = _strategy(db, cost_policy=cost_policy)

    result = estimate_image_cost(db, {"count": 2}, strategy, {"provider": "mock"})

    assert result["amount"] == 4.0
    assert result["ab_max_group_cost"] == 5.0
```

- [ ] **Step 2: Run test to verify failure**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py::test_estimate_image_cost_includes_ab_group_cap -v -p no:cacheprovider
```

Expected: FAIL because `ab_max_group_cost` is not returned.

- [ ] **Step 3: Add hard cap to policy runtime**

Modify `DEFAULT_COST_POLICY`:

```python
DEFAULT_COST_POLICY = {
    "unit_cost": 1.0,
    "currency": "CNY",
    "confirmation_threshold": 1.0,
    "latency_seconds_per_image": 10,
    "ab_max_group_cost": None,
}
```

Modify `estimate_image_cost()` to build a `result` dict and append the cap:

```python
result = {
    "amount": amount,
    "currency": currency,
    "estimate_source": "policy",
    "requires_confirmation": amount > threshold,
    "confirmation_threshold": threshold,
    "units": {"images": count, "unit_cost": unit_cost},
    "policy_version_id": policy_id,
    "time_estimate": {"estimated_seconds": latency, "estimate_source": "policy"},
}
cap = policy.get("ab_max_group_cost")
if cap is not None:
    result["ab_max_group_cost"] = float(cap)
return result
```

- [ ] **Step 4: Run policy runtime tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 2: Strategy Metrics Service

**Files:**

- Create `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_metrics_service.py`
- Create `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_metrics_service.py`

- [ ] **Step 1: Add failing metrics tests**

Create `server/tests/test_image_production_metrics_service.py` with these tests:

```python
from datetime import timedelta

from app.config import bj_now
from app.db_models import ImageCreationAsset, ImageCreationReviewRecord, ImageCreationTask, ImageProductionCostEvent
from app.services.image_production_metrics_service import refresh_image_strategy_metrics, strategy_metrics_payload


def _task(db, *, task_id, status="completed", strategy_id="strategy-1", strategy_version=1, model_id="model-1"):
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
        strategy_version=strategy_version,
        model_id=model_id,
        created_at=bj_now() - timedelta(seconds=10),
        completed_at=bj_now(),
    )
    db.add(task)
    db.flush()
    return task


def test_refresh_image_strategy_metrics_counts_task_asset_review_and_cost(db):
    task = _task(db, task_id="metric-task-1", strategy_version=2)
    asset = ImageCreationAsset(task_id=task.id, url="https://img.example/a.png", status="approved", audit_status="approved")
    db.add(asset)
    db.flush()
    db.add(ImageCreationReviewRecord(
        asset_id=asset.id,
        task_id=task.id,
        review_type="manual",
        status="approved",
        action="approve",
        asset_version=1,
        is_latest_asset_review=True,
    ))
    db.add(ImageProductionCostEvent(
        event_key="metric-task-1:actual:current",
        task_id=task.id,
        event_type="actual",
        actual_cost=1.2,
        estimated_cost=1.0,
        currency="CNY",
    ))
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 2, "model-1")
    payload = strategy_metrics_payload(metric)

    assert payload["attempt_count"] == 1
    assert payload["success_rate"] == 1.0
    assert payload["ai_pass_rate"] == 1.0
    assert payload["human_pass_rate"] == 1.0
    assert payload["average_cost_amount"] == 1.2
    assert payload["low_sample"] is True


def test_refresh_image_strategy_metrics_counts_latest_actual_cost_once_per_task(db):
    task = _task(db, task_id="metric-task-2")
    db.add(ImageProductionCostEvent(event_key="metric-task-2:actual:first", task_id=task.id, event_type="actual", actual_cost=2.0, estimated_cost=1.0, currency="CNY", created_at=bj_now() - timedelta(seconds=2)))
    db.add(ImageProductionCostEvent(event_key="metric-task-2:actual:second", task_id=task.id, event_type="actual", actual_cost=3.0, estimated_cost=1.0, currency="CNY", created_at=bj_now()))
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")

    assert strategy_metrics_payload(metric)["average_cost_amount"] == 3.0
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_metrics_service.py -v -p no:cacheprovider
```

Expected: FAIL because the service does not exist.

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
    return [float(row.actual_cost or 0.0) for row in latest_by_task.values()], rows[0].currency if rows else "CNY"


def refresh_image_strategy_metrics(db: Session, strategy_id: str, strategy_version: int, model_id: str | None) -> ImageProductionMetric:
    query = (
        db.query(ImageCreationTask)
        .filter(ImageCreationTask.strategy_id == strategy_id)
        .filter(ImageCreationTask.strategy_version == strategy_version)
    )
    query = query.filter(ImageCreationTask.model_id == model_id) if model_id is not None else query.filter(ImageCreationTask.model_id.is_(None))
    tasks = query.all()
    task_ids = [task.id for task in tasks]
    assets = db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id.in_(task_ids)).all() if task_ids else []
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
        metric = ImageProductionMetric(strategy_id=strategy_id, strategy_version=strategy_version, model_id=model_id)
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
            "repaint_count": 0,
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

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_metrics_service.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 3: A/B Service

**Files:**

- Create `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_ab_test_service.py`
- Create `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_ab_service.py`
- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`

- [ ] **Step 1: Add failing A/B service tests**

Create `server/tests/test_image_ab_service.py`:

```python
import pytest
from fastapi import HTTPException

from app.db_models import (
    AIModel,
    ImageCreationAsset,
    ImageCreationTask,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionPolicyVersion,
    ImageProductionStrategy,
    ProductionAuditEvent,
)
from app.services import image_ab_test_service as service
from app.services.crypto import encrypt


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


def _cost_policy(db, cap=None, unit_cost=1.5):
    row = ImageProductionPolicyVersion(
        policy_type="cost",
        name="ab-cost",
        version=1,
        snapshot_json={
            "unit_cost": unit_cost,
            "currency": "CNY",
            "confirmation_threshold": 1.0,
            "ab_max_group_cost": cap,
        },
        status="active",
    )
    db.add(row)
    db.commit()
    return row


def _strategy(db, model, slug, cost_policy=None):
    row = ImageProductionStrategy(
        slug=slug,
        name=slug,
        destination_role="storyboard_first_frame",
        supported_modes_json=["text_to_image"],
        default_model_id=model.id,
        fallback_model_ids_json=[],
        common_parameters_json={},
        provider_options_json={},
        cost_policy_version_id=cost_policy.id if cost_policy else None,
        status="active",
        version=1,
    )
    db.add(row)
    db.commit()
    return row


def _payload(strategies, **overrides):
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "negative_prompt": "",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": [strategy.id for strategy in strategies],
        "count": 1,
        "provider_options": {},
        "cost_confirmation": True,
        "idempotency_key": "ab-group-1",
    }
    payload.update(overrides)
    return payload


def _task(db, *, status="completed", strategy=None, idempotency_key=None, ab_group_id=None):
    row = ImageCreationTask(
        idempotency_key=idempotency_key,
        request_hash=f"request-{idempotency_key or status}",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status=status,
        prompt="attempt frame",
        count=1,
        target_count=1,
        completed_count=1 if status == "completed" else 0,
        failed_count=1 if status == "failed" else 0,
        model_id=strategy.default_model_id if strategy else "model-1",
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        ab_test_group_id=ab_group_id,
    )
    db.add(row)
    db.commit()
    return row


def _approved_asset(db, task):
    row = ImageCreationAsset(
        task_id=task.id,
        url="https://img.example/approved.png",
        prompt=task.prompt,
        status="approved",
        version=1,
        slot_key="default",
    )
    db.add(row)
    db.commit()
    return row


def _group_with_attempts(db, strategies, *, task_status="completed", approved=False):
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key="decision-group",
        source_request_hash="hash-decision",
        prompt_snapshot_json=_payload(strategies),
        cost_confirmation_json={"confirmed": True},
        status="completed",
    )
    db.add(group)
    db.flush()
    attempts = []
    for index, strategy in enumerate(strategies):
        task = _task(db, status=task_status, strategy=strategy, idempotency_key=f"decision-{index}", ab_group_id=group.id)
        if approved and index == 0:
            _approved_asset(db, task)
        attempt = ImageProductionAbAttempt(
            group_id=group.id,
            task_id=task.id,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            model_id=strategy.default_model_id,
            status=task_status,
            metrics_snapshot_json={"latency_seconds": 8 + index, "cost_amount": 1.5},
        )
        db.add(attempt)
        attempts.append(attempt)
    db.commit()
    return group, attempts


def _assert_image_error(exc_info, status_code, error_code):
    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail["error_code"] == error_code


def test_preview_ab_group_requires_multiple_strategies(db):
    model = _model(db)
    strategy = _strategy(db, model, "only-one")

    with pytest.raises(HTTPException) as exc:
        service.preview_ab_group(db, _payload([strategy]), user_id="test-user-id")

    _assert_image_error(exc, 422, "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID")


def test_preview_ab_group_returns_total_cost_and_request_hash(db):
    model = _model(db)
    cost_policy = _cost_policy(db)
    strategies = [
        _strategy(db, model, "variant-a", cost_policy),
        _strategy(db, model, "variant-b", cost_policy),
    ]

    preview = service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    assert preview["ok"] is True
    assert preview["strategy_count"] == 2
    assert preview["request_hash"]
    assert preview["total_cost_estimate"]["amount"] == 3.0
    assert preview["total_cost_estimate"]["currency"] == "CNY"
    assert preview["previews"][0]["strategy_id"] == strategies[0].id


def test_preview_ab_group_returns_group_cost_cap_when_policy_sets_it(db):
    model = _model(db)
    capped = _cost_policy(db, cap=2.0)
    uncapped = _cost_policy(db, cap=None)
    strategies = [
        _strategy(db, model, "capped", capped),
        _strategy(db, model, "uncapped", uncapped),
    ]

    preview = service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    assert preview["total_cost_estimate"]["ab_max_group_cost"] == 2.0
    assert preview["total_cost_estimate"]["cost_limit_exceeded"] is True


@pytest.mark.asyncio
async def test_create_ab_group_creates_attempt_tasks_with_derived_idempotency(db, monkeypatch):
    model = _model(db)
    strategies = [
        _strategy(db, model, "variant-a"),
        _strategy(db, model, "variant-b"),
    ]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        return _task(
            db,
            status="queued",
            strategy=strategies[len(calls) - 1],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)

    payload = _payload(strategies, idempotency_key="ab-fixed-key")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    group = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).order_by(ImageProductionAbAttempt.created_at.asc()).all()
    assert group.status == "running"
    assert len(attempts) == 2
    assert calls[0]["ab_test_group_id"] == group.id
    assert calls[0]["idempotency_key"] == f"ab-fixed-key:attempt:0:{strategies[0].id}:{strategies[0].version}"
    assert calls[1]["idempotency_key"] == f"ab-fixed-key:attempt:1:{strategies[1].id}:{strategies[1].version}"


@pytest.mark.asyncio
async def test_create_ab_group_reuses_group_idempotency_key_for_same_request(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(db, status="queued", strategy=strategies[0], idempotency_key=task_payload["idempotency_key"], ab_group_id=task_payload["ab_test_group_id"])

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="stable-ab-key")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    first = await service.create_ab_group(db, payload, user_id="test-user-id")
    second = await service.create_ab_group(db, payload, user_id="test-user-id")

    assert second.id == first.id
    assert db.query(ImageProductionAbGroup).filter_by(idempotency_key="stable-ab-key").count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_rejects_when_total_cost_exceeds_ab_group_cap(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=2.0)
    strategies = [_strategy(db, model, "variant-a", policy), _strategy(db, model, "variant-b", policy)]
    payload = _payload(strategies, idempotency_key="too-expensive")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED")


@pytest.mark.asyncio
async def test_create_ab_group_records_partial_failure_when_one_attempt_fails(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        if len(calls) == 2:
            raise RuntimeError("provider unavailable")
        return _task(db, status="queued", strategy=strategies[0], idempotency_key=task_payload["idempotency_key"], ab_group_id=task_payload["ab_test_group_id"])

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="partial-failure")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).all()
    assert group.status == "partial_failed"
    assert {attempt.status for attempt in attempts} == {"creating", "failed"}


def test_refresh_ab_group_marks_completed_when_all_attempts_terminal(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    refreshed = service.refresh_ab_group(db, group.id)

    assert refreshed.status == "completed"


def test_adopt_ab_winner_requires_approved_asset(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    with pytest.raises(HTTPException) as exc:
        service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "best composition"})

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_WINNER_NOT_READY")


def test_adopt_ab_winner_records_decision_for_approved_attempt(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)

    updated = service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "approved winner", "notes": "Use this frame"})

    assert updated.status == "winner_selected"
    assert updated.winner_attempt_id == attempts[0].id
    assert updated.decision_json["reason"] == "approved winner"
    assert updated.decision_json["evidence_snapshot"]["winner_attempt_id"] == attempts[0].id


def test_adopt_ab_winner_stores_decision_evidence_snapshot(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)

    updated = service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "face consistent"})
    snapshot = updated.decision_json["evidence_snapshot"]

    assert len(snapshot["attempts"]) == 2
    assert snapshot["attempts"][0]["approved_asset_ready"] is True
    assert snapshot["attempts"][0]["approved_asset_ids"]


def test_mark_ab_no_winner_stores_all_attempt_evidence(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    updated = service.mark_ab_no_winner(db, group.id, {"reason": "both off style"})

    assert updated.status == "no_winner"
    assert updated.decision_json["reason"] == "both off style"
    assert updated.decision_json["evidence_snapshot"]["decision"] == "no_winner"
    assert len(updated.decision_json["evidence_snapshot"]["attempts"]) == 2


def test_preview_ab_group_records_audit_event(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]

    service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_records_create_and_partial_failure_events(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        if len(calls) == 2:
            raise RuntimeError("provider unavailable")
        return _task(db, status="queued", strategy=strategies[0], idempotency_key=task_payload["idempotency_key"], ab_group_id=task_payload["ab_test_group_id"])

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="audit-partial")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    await service.create_ab_group(db, payload, user_id="test-user-id")

    event_types = {row.event_type for row in db.query(ProductionAuditEvent).all()}
    assert {"image_ab.preview", "image_ab.create", "image_ab.partial_failed"}.issubset(event_types)


def test_adopt_ab_winner_records_audit_event(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)

    service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "winner"})

    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.winner").count() == 1


def test_mark_ab_no_winner_records_audit_event(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    service.mark_ab_no_winner(db, group.id, {"reason": "reject all"})

    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.no_winner").count() == 1
```

- [ ] **Step 2: Run service tests to verify failure**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_service.py -v -p no:cacheprovider
```

Expected: FAIL because `image_ab_test_service.py` does not exist.

- [ ] **Step 3: Update image task association**

Modify the `ImageCreationTask` construction block in `create_image_task()`:

```python
ab_test_group_id=payload.get("ab_test_group_id"),
```

Modify `task_payload()`:

```python
"ab_test_group_id": task.ab_test_group_id,
```

- [ ] **Step 4: Implement A/B service**

Create `server/app/services/image_ab_test_service.py` with this service surface and helper structure:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import (
    ImageCreationAsset,
    ImageCreationTask,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionStrategy,
)
from app.services.image_creation_errors import image_error
from app.services.image_creation_service import create_image_task
from app.services.image_selection_preview_service import create_selection_preview
from app.services.production_observability import record_production_event


TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _strategy_rows(db: Session, strategy_ids: list[str]) -> list[ImageProductionStrategy]:
    unique_ids = [strategy_id for index, strategy_id in enumerate(strategy_ids) if strategy_id not in strategy_ids[:index]]
    if len(unique_ids) < 2:
        raise image_error(
            422,
            "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID",
            "A/B comparison requires at least two unique strategies.",
            "Select at least two image production strategies.",
            retryable=False,
        )
    rows = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id.in_(unique_ids)).all()
    by_id = {row.id: row for row in rows}
    missing = [strategy_id for strategy_id in unique_ids if strategy_id not in by_id]
    if missing:
        raise image_error(
            404,
            "IMAGE_STRATEGY_NOT_FOUND",
            "One or more A/B strategies were not found.",
            "Reload strategies and retry.",
            retryable=False,
            affected_ids=missing,
        )
    inactive = [row.id for row in rows if row.status != "active"]
    if inactive:
        raise image_error(
            409,
            "IMAGE_STRATEGY_ARCHIVED",
            "One or more A/B strategies are archived.",
            "Choose active strategies.",
            retryable=False,
            affected_ids=inactive,
        )
    return [by_id[strategy_id] for strategy_id in unique_ids]


def _payload_for_strategy(payload: dict[str, Any], strategy: ImageProductionStrategy) -> dict[str, Any]:
    task_payload = dict(payload)
    task_payload.pop("strategy_ids", None)
    task_payload.pop("preview_request_hash", None)
    task_payload.pop("cost_confirmation", None)
    task_payload["strategy_id"] = strategy.id
    task_payload["strategy_version"] = strategy.version
    return task_payload


def _amount(preview: dict[str, Any]) -> float:
    return float((preview.get("cost_estimate") or {}).get("amount") or 0)


def _currency(previews: list[dict[str, Any]]) -> str:
    for preview in previews:
        currency = (preview.get("cost_estimate") or {}).get("currency")
        if currency:
            return currency
    return "CNY"


def _group_cap(previews: list[dict[str, Any]]) -> float | None:
    values = [
        float(preview["cost_estimate"]["ab_max_group_cost"])
        for preview in previews
        if (preview.get("cost_estimate") or {}).get("ab_max_group_cost") is not None
    ]
    return min(values) if values else None


def _total_cost(previews: list[dict[str, Any]]) -> dict[str, Any]:
    amount = sum(_amount(preview) for preview in previews)
    cap = _group_cap(previews)
    return {
        "amount": amount,
        "currency": _currency(previews),
        "requires_confirmation": any((preview.get("cost_estimate") or {}).get("requires_confirmation") for preview in previews),
        "ab_max_group_cost": cap,
        "cost_limit_exceeded": cap is not None and amount > cap,
    }


def _record(db: Session, event_type: str, payload: dict[str, Any]) -> None:
    record_production_event(db, event_type=event_type, payload={"scope": "image_ab", **payload})


def preview_ab_group(db: Session, payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    strategies = _strategy_rows(db, list(payload.get("strategy_ids") or []))
    previews = []
    for strategy in strategies:
        preview = create_selection_preview(db, _payload_for_strategy(payload, strategy), user_id=user_id)
        preview["strategy_id"] = strategy.id
        preview["strategy_version"] = strategy.version
        previews.append(preview)
    total_cost = _total_cost(previews)
    request_hash = _hash({
        "mode": payload.get("mode"),
        "prompt": payload.get("prompt"),
        "negative_prompt": payload.get("negative_prompt") or "",
        "destination_role": payload.get("destination_role"),
        "strategy_ids": [strategy.id for strategy in strategies],
        "preview_hashes": [preview.get("request_hash") for preview in previews],
        "count": payload.get("count", 1),
        "provider_options": payload.get("provider_options") or {},
    })
    result = {
        "ok": True,
        "request_hash": request_hash,
        "strategy_count": len(strategies),
        "total_cost_estimate": total_cost,
        "previews": previews,
    }
    _record(db, "image_ab.preview", {"request_hash": request_hash, "strategy_count": len(strategies), "total_cost_estimate": total_cost})
    db.commit()
    return result


def _ensure_preview_matches(db: Session, payload: dict[str, Any], user_id: str | None) -> dict[str, Any]:
    preview = preview_ab_group(db, payload, user_id=user_id)
    expected_hash = payload.get("preview_request_hash")
    if expected_hash and expected_hash != preview["request_hash"]:
        raise image_error(
            409,
            "IMAGE_AB_TEST_PREVIEW_STALE",
            "A/B preview is stale.",
            "Run A/B preview again before creating tasks.",
            retryable=False,
        )
    if preview["total_cost_estimate"]["cost_limit_exceeded"]:
        raise image_error(
            409,
            "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED",
            "A/B comparison exceeds the configured group cost limit.",
            "Reduce count, choose cheaper strategies, or adjust policy.",
            retryable=False,
            details={"total_cost_estimate": preview["total_cost_estimate"]},
        )
    return preview


def _attempt_key(payload: dict[str, Any], group: ImageProductionAbGroup, index: int, attempt: ImageProductionAbAttempt) -> str:
    base_key = payload.get("idempotency_key") or group.id
    return f"{base_key}:attempt:{index}:{attempt.strategy_id}:{attempt.strategy_version}"


async def create_ab_group(db: Session, payload: dict[str, Any], user_id: str | None = None) -> ImageProductionAbGroup:
    preview = _ensure_preview_matches(db, payload, user_id)
    idempotency_key = payload.get("idempotency_key")
    if idempotency_key:
        existing = db.query(ImageProductionAbGroup).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            if existing.source_request_hash != preview["request_hash"]:
                raise image_error(
                    409,
                    "IMAGE_AB_TEST_CONFLICT",
                    "A/B idempotency key was reused for a different request.",
                    "Use a new idempotency key.",
                    retryable=False,
                    affected_ids=[existing.id],
                )
            return existing

    group = ImageProductionAbGroup(
        user_id=user_id,
        idempotency_key=idempotency_key,
        source_request_hash=preview["request_hash"],
        prompt_snapshot_json=payload,
        cost_confirmation_json={
            "confirmed": bool(payload.get("cost_confirmation")),
            "total_cost_estimate": preview["total_cost_estimate"],
        },
        status="running",
    )
    db.add(group)
    db.flush()

    strategies = _strategy_rows(db, list(payload.get("strategy_ids") or []))
    successes = 0
    failures = 0
    for index, strategy in enumerate(strategies):
        attempt = ImageProductionAbAttempt(
            group_id=group.id,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            model_id=strategy.default_model_id,
            status="creating",
            metrics_snapshot_json={},
        )
        db.add(attempt)
        db.flush()
        task_payload = _payload_for_strategy(payload, strategy)
        task_payload["ab_test_group_id"] = group.id
        task_payload["idempotency_key"] = _attempt_key(payload, group, index, attempt)
        task_payload["cost_confirmation"] = bool(payload.get("cost_confirmation"))
        try:
            task = await create_image_task(db, task_payload)
            attempt.task_id = task.id
            attempt.model_id = task.model_id
            attempt.status = "creating" if task.status in {"queued", "running"} else task.status
            attempt.metrics_snapshot_json = {"estimated_cost": task.estimated_cost_json or {}}
            successes += 1
        except Exception as exc:
            attempt.status = "failed"
            attempt.metrics_snapshot_json = {"error": str(exc)}
            failures += 1

    if failures and successes:
        group.status = "partial_failed"
        _record(db, "image_ab.partial_failed", {"group_id": group.id, "failure_count": failures, "success_count": successes})
    elif failures:
        group.status = "failed"
    else:
        group.status = "running"
    _record(db, "image_ab.create", {"group_id": group.id, "status": group.status, "strategy_count": len(strategies)})
    db.commit()
    db.refresh(group)
    return group


def get_ab_group(db: Session, group_id: str) -> ImageProductionAbGroup:
    group = db.query(ImageProductionAbGroup).filter_by(id=group_id).first()
    if not group:
        raise image_error(
            404,
            "IMAGE_AB_TEST_GROUP_NOT_FOUND",
            "A/B group was not found.",
            "Reload A/B comparisons.",
            retryable=False,
            affected_ids=[group_id],
        )
    return group


def _attempt_rows(db: Session, group_id: str) -> list[ImageProductionAbAttempt]:
    return (
        db.query(ImageProductionAbAttempt)
        .filter_by(group_id=group_id)
        .order_by(ImageProductionAbAttempt.created_at.asc())
        .all()
    )


def refresh_ab_group(db: Session, group_id: str) -> ImageProductionAbGroup:
    group = get_ab_group(db, group_id)
    attempts = _attempt_rows(db, group.id)
    for attempt in attempts:
        task = db.query(ImageCreationTask).filter_by(id=attempt.task_id).first() if attempt.task_id else None
        if task:
            attempt.status = task.status
            attempt.model_id = task.model_id
            attempt.metrics_snapshot_json = {"estimated_cost": task.estimated_cost_json or {}}
    statuses = {attempt.status for attempt in attempts}
    if statuses and statuses.issubset(TERMINAL_TASK_STATUSES):
        group.status = "completed" if statuses == {"completed"} else "partial_failed"
    db.commit()
    db.refresh(group)
    return group


def _assert_no_decision(group: ImageProductionAbGroup) -> None:
    if group.winner_attempt_id or group.status in {"winner_selected", "no_winner"}:
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_CONFLICT",
            "This A/B group already has a decision.",
            "Reload the group and review the recorded decision.",
            retryable=False,
            affected_ids=[group.id],
        )


def _approved_assets(db: Session, attempt: ImageProductionAbAttempt) -> list[ImageCreationAsset]:
    if not attempt.task_id:
        return []
    return (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id == attempt.task_id)
        .filter(ImageCreationAsset.status == "approved")
        .all()
    )
```

Append the decision and serialization functions in the same file:

```python
def _ab_decision_evidence_snapshot(db: Session, group: ImageProductionAbGroup, winner_attempt_id: str | None, decision: dict[str, Any]) -> dict[str, Any]:
    attempts = []
    for attempt in _attempt_rows(db, group.id):
        task = db.query(ImageCreationTask).filter(ImageCreationTask.id == attempt.task_id).first() if attempt.task_id else None
        approved_assets = (
            db.query(ImageCreationAsset)
            .filter(ImageCreationAsset.task_id == attempt.task_id)
            .filter(ImageCreationAsset.status == "approved")
            .all()
            if attempt.task_id else []
        )
        attempts.append({
            "attempt_id": attempt.id,
            "task_id": attempt.task_id,
            "strategy_id": attempt.strategy_id,
            "strategy_version": attempt.strategy_version,
            "model_id": attempt.model_id,
            "status": attempt.status,
            "approved_asset_ready": bool(approved_assets),
            "approved_asset_ids": [asset.id for asset in approved_assets],
            "metrics": attempt.metrics_snapshot_json or {},
            "task_status": task.status if task else None,
            "estimated_cost": task.estimated_cost_json if task else {},
        })
    return {
        "decision": "winner" if winner_attempt_id else "no_winner",
        "winner_attempt_id": winner_attempt_id,
        "reason": decision.get("reason") or "",
        "notes": decision.get("notes") or "",
        "decided_at": bj_now().isoformat(),
        "attempts": attempts,
    }


def adopt_ab_winner(db: Session, group_id: str, attempt_id: str, decision: dict[str, Any]) -> ImageProductionAbGroup:
    group = get_ab_group(db, group_id)
    _assert_no_decision(group)
    attempt = db.query(ImageProductionAbAttempt).filter_by(id=attempt_id, group_id=group.id).first()
    if not attempt:
        raise image_error(
            404,
            "IMAGE_AB_TEST_ATTEMPT_NOT_FOUND",
            "A/B attempt was not found.",
            "Reload the A/B group.",
            retryable=False,
            affected_ids=[attempt_id],
        )
    approved_assets = _approved_assets(db, attempt)
    if not approved_assets:
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_NOT_READY",
            "Winner attempt must have at least one approved image asset.",
            "Approve an image asset before choosing the winner.",
            retryable=False,
            affected_ids=[attempt_id],
        )
    snapshot = _ab_decision_evidence_snapshot(db, group, attempt.id, decision)
    group.winner_attempt_id = attempt.id
    group.status = "winner_selected"
    group.decision_json = {
        "reason": decision.get("reason") or "",
        "notes": decision.get("notes") or "",
        "evidence_snapshot": snapshot,
    }
    attempt.human_decision_json = {"decision": "winner", "decided_at": bj_now().isoformat()}
    _record(db, "image_ab.winner", {"group_id": group.id, "attempt_id": attempt.id})
    db.commit()
    db.refresh(group)
    return group


def mark_ab_no_winner(db: Session, group_id: str, decision: dict[str, Any]) -> ImageProductionAbGroup:
    group = get_ab_group(db, group_id)
    _assert_no_decision(group)
    snapshot = _ab_decision_evidence_snapshot(db, group, None, decision)
    group.status = "no_winner"
    group.decision_json = {
        "reason": decision.get("reason") or "",
        "notes": decision.get("notes") or "",
        "evidence_snapshot": snapshot,
    }
    _record(db, "image_ab.no_winner", {"group_id": group.id})
    db.commit()
    db.refresh(group)
    return group


def serialize_ab_group(db: Session, group: ImageProductionAbGroup) -> dict[str, Any]:
    attempts = []
    for attempt in _attempt_rows(db, group.id):
        task = db.query(ImageCreationTask).filter_by(id=attempt.task_id).first() if attempt.task_id else None
        approved_assets = _approved_assets(db, attempt)
        attempts.append({
            "id": attempt.id,
            "group_id": attempt.group_id,
            "task_id": attempt.task_id,
            "strategy_id": attempt.strategy_id,
            "strategy_version": attempt.strategy_version,
            "model_id": attempt.model_id,
            "status": attempt.status,
            "metrics_snapshot": attempt.metrics_snapshot_json or {},
            "human_decision": attempt.human_decision_json or {},
            "task_status": task.status if task else None,
            "approved_asset_ready": bool(approved_assets),
            "approved_asset_ids": [asset.id for asset in approved_assets],
        })
    return {
        "id": group.id,
        "status": group.status,
        "source_request_hash": group.source_request_hash,
        "winner_attempt_id": group.winner_attempt_id,
        "decision": group.decision_json or {},
        "cost_confirmation": group.cost_confirmation_json or {},
        "attempts": attempts,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }
```

- [ ] **Step 5: Run A/B service tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_service.py tests/test_image_production_policy_runtime.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 4: A/B API Endpoints

**Files:**

- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Create `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_ab_api.py`

- [ ] **Step 1: Add failing API tests**

Create `server/tests/test_image_ab_api.py`:

```python
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import image_production as router_module
from app.services.image_creation_errors import image_error


client = TestClient(app)


def test_ab_preview_rejects_single_strategy(monkeypatch):
    def fake_preview(db, payload, user_id=None):
        raise image_error(
            422,
            "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID",
            "A/B comparison requires at least two unique strategies.",
            "Select at least two image production strategies.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "preview_ab_group", fake_preview)

    resp = client.post("/api/image-production/ab-tests/preview", json={
        "mode": "text_to_image",
        "prompt": "api ab",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": ["one"],
        "count": 1,
    })
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID"


def test_ab_preview_route_returns_preview(monkeypatch):
    def fake_preview(db, payload, user_id=None):
        assert payload["strategy_ids"] == ["strategy-a", "strategy-b"]
        return {
            "ok": True,
            "request_hash": "hash-api",
            "strategy_count": 2,
            "total_cost_estimate": {"amount": 3.0, "currency": "CNY", "cost_limit_exceeded": False},
            "previews": [],
        }

    monkeypatch.setattr(router_module, "preview_ab_group", fake_preview)

    resp = client.post("/api/image-production/ab-tests/preview", json={
        "mode": "text_to_image",
        "prompt": "api ab",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": ["strategy-a", "strategy-b"],
        "count": 1,
    })

    assert resp.status_code == 200
    assert resp.json()["request_hash"] == "hash-api"
    assert resp.json()["total_cost_estimate"]["amount"] == 3.0


def test_ab_create_route_returns_serialized_group(monkeypatch):
    async def fake_create(db, payload, user_id=None):
        assert payload["preview_request_hash"] == "hash-api"
        assert payload["cost_confirmation"] is True
        return SimpleNamespace(id="ab-group-1", status="running")

    def fake_serialize(db, group):
        return {"id": group.id, "status": group.status, "attempts": [{"id": "attempt-1", "status": "creating"}]}

    monkeypatch.setattr(router_module, "create_ab_group", fake_create)
    monkeypatch.setattr(router_module, "serialize_ab_group", fake_serialize)

    resp = client.post("/api/image-production/ab-tests", json={
        "mode": "text_to_image",
        "prompt": "api ab",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": ["strategy-a", "strategy-b"],
        "count": 1,
        "preview_request_hash": "hash-api",
        "cost_confirmation": True,
        "idempotency_key": "ab-api-key",
    })

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["ab_group"]["id"] == "ab-group-1"
    assert resp.json()["ab_group"]["attempts"][0]["id"] == "attempt-1"


def test_ab_create_route_returns_cost_limit_error(monkeypatch):
    async def fake_create(db, payload, user_id=None):
        raise image_error(
            409,
            "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED",
            "A/B comparison exceeds the configured group cost limit.",
            "Reduce count, choose cheaper strategies, or adjust policy.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "create_ab_group", fake_create)

    resp = client.post("/api/image-production/ab-tests", json={
        "mode": "text_to_image",
        "prompt": "api ab",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": ["strategy-a", "strategy-b"],
        "count": 2,
        "preview_request_hash": "hash-api",
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED"


def test_ab_winner_route_rejects_unapproved_attempt(monkeypatch):
    def fake_winner(db, group_id, attempt_id, decision):
        assert group_id == "ab-group-1"
        assert attempt_id == "attempt-1"
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_NOT_READY",
            "Winner attempt must have at least one approved image asset.",
            "Approve an image asset before choosing the winner.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "adopt_ab_winner", fake_winner)

    resp = client.post("/api/image-production/ab-tests/ab-group-1/winner/attempt-1", json={"reason": "best"})

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_WINNER_NOT_READY"


def test_ab_group_read_returns_not_found(monkeypatch):
    def fake_get(db, group_id):
        raise image_error(
            404,
            "IMAGE_AB_TEST_GROUP_NOT_FOUND",
            "A/B group was not found.",
            "Reload A/B comparisons.",
            retryable=False,
        )

    monkeypatch.setattr(router_module, "get_ab_group", fake_get)

    resp = client.get("/api/image-production/ab-tests/missing")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "IMAGE_AB_TEST_GROUP_NOT_FOUND"
```

- [ ] **Step 2: Run API tests to verify failure**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_api.py -v -p no:cacheprovider
```

Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Add request models and endpoints**

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

Add routes:

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
    return {"ok": True, "ab_group": serialize_ab_group(db, refresh_ab_group(db, group_id))}


@router.post("/ab-tests/{group_id}/winner/{attempt_id}")
def ab_winner(group_id: str, attempt_id: str, body: AbDecisionRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return {"ok": True, "ab_group": serialize_ab_group(db, adopt_ab_winner(db, group_id, attempt_id, body.model_dump()))}


@router.post("/ab-tests/{group_id}/no-winner")
def ab_no_winner(group_id: str, body: AbDecisionRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return {"ok": True, "ab_group": serialize_ab_group(db, mark_ab_no_winner(db, group_id, body.model_dump()))}
```

- [ ] **Step 4: Run API tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_ab_api.py tests/test_image_ab_service.py -v -p no:cacheprovider
```

Expected: PASS.

## Task 5: Frontend A/B Workbench

**Files:**

- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\api\imageProduction.js`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-page.test.js`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-a11y.test.js`

- [ ] **Step 1: Extend frontend API wrapper**

Add to `web/src/api/imageProduction.js`:

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

- [ ] **Step 2: Add failing workbench tests**

Extend `web/src/__tests__/image-creation-page.test.js` mocks with the six API functions above:

```javascript
const mocks = vi.hoisted(() => ({
  uploadImageSource: vi.fn(),
  createImageTask: vi.fn(),
  getImageTask: vi.fn(),
  listImageAssets: vi.fn(),
  listModels: vi.fn(),
  syncImageTask: vi.fn(),
  dispatchQueuedImageTask: vi.fn(),
  reviewImageAsset: vi.fn(),
  editImageAsset: vi.fn(),
  listImageProductionStrategies: vi.fn(),
  previewImageSelection: vi.fn(),
  promoteImageAssetToVideo: vi.fn(),
  previewImageAbTest: vi.fn(),
  createImageAbTest: vi.fn(),
  getImageAbTest: vi.fn(),
  refreshImageAbTest: vi.fn(),
  chooseImageAbWinner: vi.fn(),
  chooseImageAbNoWinner: vi.fn(),
}))

vi.mock('../api/imageProduction.js', () => ({
  listImageProductionStrategies: mocks.listImageProductionStrategies,
  previewImageSelection: mocks.previewImageSelection,
  promoteImageAssetToVideo: mocks.promoteImageAssetToVideo,
  previewImageAbTest: mocks.previewImageAbTest,
  createImageAbTest: mocks.createImageAbTest,
  getImageAbTest: mocks.getImageAbTest,
  refreshImageAbTest: mocks.refreshImageAbTest,
  chooseImageAbWinner: mocks.chooseImageAbWinner,
  chooseImageAbNoWinner: mocks.chooseImageAbNoWinner,
}))
```

Add tests:

```javascript
it('previews and creates A/B image comparison with explicit cost confirmation', async () => {
  mocks.listImageProductionStrategies.mockResolvedValueOnce({
    data: {
      strategies: [
        { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
      ],
    },
  })
  mocks.previewImageAbTest.mockResolvedValueOnce({
    data: {
      ok: true,
      request_hash: 'ab-hash-1',
      strategy_count: 2,
      total_cost_estimate: { amount: 3, currency: 'CNY', requires_confirmation: true, cost_limit_exceeded: false },
      previews: [],
    },
  })
  mocks.createImageAbTest.mockResolvedValueOnce({
    data: { ok: true, ab_group: { id: 'ab-group-1', status: 'running', attempts: [] } },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('A/B frame prompt')
  await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
  await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
  await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
  await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
  await flushPromises()

  expect(wrapper.text()).toContain('3 CNY')
  expect(wrapper.get('[data-testid="ab-create-button"]').attributes('disabled')).toBeDefined()

  await wrapper.get('[data-testid="ab-cost-confirmation"]').setValue(true)
  await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
  await flushPromises()

  expect(mocks.previewImageAbTest).toHaveBeenCalledWith(expect.objectContaining({
    prompt: 'A/B frame prompt',
    strategy_ids: ['strategy-a', 'strategy-b'],
  }))
  expect(mocks.createImageAbTest).toHaveBeenCalledWith(expect.objectContaining({
    preview_request_hash: 'ab-hash-1',
    cost_confirmation: true,
    strategy_ids: ['strategy-a', 'strategy-b'],
  }))
})

it('blocks A/B create when preview exceeds configured cost cap', async () => {
  mocks.listImageProductionStrategies.mockResolvedValueOnce({
    data: {
      strategies: [
        { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
      ],
    },
  })
  mocks.previewImageAbTest.mockResolvedValueOnce({
    data: {
      ok: true,
      request_hash: 'ab-hash-expensive',
      strategy_count: 2,
      total_cost_estimate: { amount: 9, currency: 'CNY', requires_confirmation: true, ab_max_group_cost: 5, cost_limit_exceeded: true },
      previews: [],
    },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('Expensive A/B frame')
  await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
  await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
  await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
  await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
  await flushPromises()

  expect(wrapper.text()).toContain('已超出A/B成本上限')
  expect(wrapper.get('[data-testid="ab-create-button"]').attributes('disabled')).toBeDefined()
  expect(mocks.createImageAbTest).not.toHaveBeenCalled()
})

it('refreshes A/B comparison and only enables winner action for approved attempts', async () => {
  mocks.listImageProductionStrategies.mockResolvedValueOnce({
    data: {
      strategies: [
        { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
      ],
    },
  })
  mocks.previewImageAbTest.mockResolvedValueOnce({
    data: {
      ok: true,
      request_hash: 'ab-hash-2',
      strategy_count: 2,
      total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
      previews: [],
    },
  })
  mocks.createImageAbTest.mockResolvedValueOnce({
    data: { ok: true, ab_group: { id: 'ab-group-2', status: 'running', attempts: [] } },
  })
  mocks.refreshImageAbTest.mockResolvedValueOnce({
    data: {
      ok: true,
      ab_group: {
        id: 'ab-group-2',
        status: 'completed',
        attempts: [
          { id: 'attempt-approved', status: 'completed', approved_asset_ready: true, approved_asset_ids: ['asset-1'] },
          { id: 'attempt-pending', status: 'completed', approved_asset_ready: false, approved_asset_ids: [] },
        ],
      },
    },
  })
  mocks.chooseImageAbWinner.mockResolvedValueOnce({
    data: { ok: true, ab_group: { id: 'ab-group-2', status: 'winner_selected', winner_attempt_id: 'attempt-approved', attempts: [] } },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('Winner A/B frame')
  await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
  await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
  await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
  await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
  await flushPromises()
  await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
  await flushPromises()
  await wrapper.get('[data-testid="ab-refresh-button"]').trigger('click')
  await flushPromises()

  expect(wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').attributes('disabled')).toBeUndefined()
  expect(wrapper.get('[data-testid="ab-choose-winner-attempt-pending"]').attributes('disabled')).toBeDefined()

  await wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').trigger('click')
  await flushPromises()

  expect(mocks.chooseImageAbWinner).toHaveBeenCalledWith('ab-group-2', 'attempt-approved', expect.objectContaining({
    reason: 'manual_selection',
  }))
})
```

- [ ] **Step 3: Add accessibility tests**

Add to `web/src/__tests__/image-creation-a11y.test.js`:

```javascript
it('exposes accessible A/B toggle, live region, and disabled winner reason', async () => {
  const Page = (await import('../views/ImageCreationPage.vue')).default
  const wrapper = mount(Page)
  await flushPromises()

  const toggle = wrapper.get('[data-testid="ab-mode-toggle"]')
  expect(toggle.attributes('aria-pressed')).toBeDefined()
  expect(wrapper.get('[data-testid="ab-status-live"]').attributes('aria-live')).toBe('polite')
  expect(wrapper.text()).toContain('需先通过审查')
})
```

- [ ] **Step 4: Implement A/B workbench state**

Add Vue state in `ImageCreationPage.vue`:

```javascript
const abModeEnabled = ref(false)
const abSelectedStrategyIds = ref([])
const abPreview = ref(null)
const abGroup = ref(null)
const abLoading = ref(false)
const abError = ref('')
const abCostConfirmed = ref(false)

const abHasEnoughStrategies = computed(() => abSelectedStrategyIds.value.length >= 2)
const abCostLimitExceeded = computed(() => Boolean(abPreview.value?.total_cost_estimate?.cost_limit_exceeded))
const abCreateDisabled = computed(() => {
  if (!abHasEnoughStrategies.value) return true
  if (!abPreview.value || abLoading.value || abCostLimitExceeded.value) return true
  if (abPreview.value.total_cost_estimate?.requires_confirmation && !abCostConfirmed.value) return true
  return false
})
```

Add the A/B payload builder immediately after the existing `buildSelectionPreviewPayload()` function. It must reuse the same mode, prompt, source, references, model parameters, provider options, size, count, output format, response format, and watermark values as normal image creation, but it must emit `strategy_ids` instead of `strategy_id`:

```javascript
function buildAbPayload() {
  const base = buildSelectionPreviewPayload()
  const payload = {
    mode: base.mode,
    prompt: base.prompt,
    negative_prompt: base.negative_prompt || '',
    destination_role: base.destination_role,
    strategy_ids: Array.from(abSelectedStrategyIds.value),
    count: base.count,
    provider_options: base.provider_options || {},
    size: base.size || null,
    output_format: base.output_format || null,
    response_format: base.response_format || null,
    watermark: Boolean(base.watermark),
  }
  if (base.model_id) payload.model_id = base.model_id
  if (base.source) payload.source = base.source
  if (base.source_url) payload.source_url = base.source_url
  if (base.source_asset_id) payload.source_asset_id = base.source_asset_id
  if (base.reference_images?.length) payload.reference_images = base.reference_images
  return payload
}
```

Add methods:

```javascript
async function previewAbComparison() {
  abLoading.value = true
  abError.value = ''
  try {
    const resp = await previewImageAbTest(buildAbPayload())
    abPreview.value = resp.data
    abCostConfirmed.value = false
  } catch (error) {
    abError.value = error?.response?.data?.detail?.message || 'A/B 预览失败'
  } finally {
    abLoading.value = false
  }
}

async function createAbComparison() {
  if (abCreateDisabled.value) return
  abLoading.value = true
  abError.value = ''
  try {
    const resp = await createImageAbTest(Object.assign({}, buildAbPayload(), {
      preview_request_hash: abPreview.value.request_hash,
      cost_confirmation: abCostConfirmed.value,
      idempotency_key: `ab-${Date.now()}`,
    }))
    abGroup.value = resp.data.ab_group
  } catch (error) {
    abError.value = error?.response?.data?.detail?.message || 'A/B 创建失败'
  } finally {
    abLoading.value = false
  }
}

async function refreshAbComparison() {
  if (!abGroup.value?.id) return
  abLoading.value = true
  abError.value = ''
  try {
    const resp = await refreshImageAbTest(abGroup.value.id)
    abGroup.value = resp.data.ab_group
  } catch (error) {
    abError.value = error?.response?.data?.detail?.message || 'A/B 刷新失败'
  } finally {
    abLoading.value = false
  }
}

async function chooseAbWinner(attemptId) {
  if (!abGroup.value?.id || !attemptId) return
  abLoading.value = true
  abError.value = ''
  try {
    const resp = await chooseImageAbWinner(abGroup.value.id, attemptId, { reason: 'manual_selection' })
    abGroup.value = resp.data.ab_group
  } catch (error) {
    abError.value = error?.response?.data?.detail?.message || 'A/B winner 选择失败'
  } finally {
    abLoading.value = false
  }
}
```

- [ ] **Step 5: Add markup**

Add A/B panel with these required `data-testid` values:

```vue
<button
  type="button"
  data-testid="ab-mode-toggle"
  :aria-pressed="String(abModeEnabled)"
  @click="abModeEnabled = !abModeEnabled"
>
  A/B 对比
</button>

<section v-if="abModeEnabled" data-testid="ab-panel">
  <fieldset data-testid="ab-strategy-selector">
    <legend>A/B 策略</legend>
    <label v-for="strategy in imageStrategies" :key="strategy.id">
      <input
        v-model="abSelectedStrategyIds"
        type="checkbox"
        :value="strategy.id"
        :data-testid="`ab-strategy-option-${strategy.id}`"
      />
      {{ strategy.name }}
    </label>
  </fieldset>

  <div data-testid="ab-status-live" aria-live="polite">
    <p v-if="abError">{{ abError }}</p>
    <p v-if="abPreview">
      {{ abPreview.total_cost_estimate?.amount || 0 }} {{ abPreview.total_cost_estimate?.currency || 'CNY' }}
    </p>
    <p v-if="abCostLimitExceeded">已超出A/B成本上限</p>
  </div>

  <button
    type="button"
    data-testid="ab-preview-button"
    :disabled="!abHasEnoughStrategies || abLoading"
    @click="previewAbComparison"
  >
    预览 A/B 成本
  </button>

  <label>
    <input v-model="abCostConfirmed" data-testid="ab-cost-confirmation" type="checkbox" />
    我确认本次 A/B 会同时创建 {{ abPreview?.strategy_count || 0 }} 个图片任务
  </label>

  <button type="button" data-testid="ab-create-button" :disabled="abCreateDisabled" @click="createAbComparison">
    创建 A/B 对比
  </button>

  <button v-if="abGroup?.id" type="button" data-testid="ab-refresh-button" @click="refreshAbComparison">
    刷新 A/B 结果
  </button>

  <div v-if="abGroup?.attempts?.length" data-testid="ab-attempt-list">
    <article v-for="attempt in abGroup.attempts" :key="attempt.id" :data-testid="`ab-attempt-${attempt.id}`">
      <span>{{ attempt.status }}</span>
      <button
        type="button"
        :data-testid="`ab-choose-winner-${attempt.id}`"
        :disabled="!attempt.approved_asset_ready"
        @click="chooseAbWinner(attempt.id)"
      >
        选为 winner
      </button>
      <span v-if="!attempt.approved_asset_ready">需先通过审查</span>
    </article>
  </div>
</section>
```

- [ ] **Step 6: Run frontend A/B tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js --run
```

Expected: PASS.

## Task 6: Strategy Center Metrics

**Files:**

- Modify `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`
- Modify `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-production-strategy-page.test.js`

- [ ] **Step 1: Add failing frontend strategy metrics test**

Add:

```javascript
it('shows strategy metrics and low sample warning', async () => {
  vi.spyOn(api, 'listImageProductionStrategies').mockResolvedValue({
    data: {
      strategies: [{
        id: 'strategy-1',
        name: '策略 A',
        status: 'active',
        version: 1,
        metrics: {
          attempt_count: 3,
          success_rate: 0.67,
          average_cost_amount: 1.2,
          currency: 'CNY',
          average_latency_seconds: 8,
          low_sample: true,
        },
      }],
    },
  })
  const wrapper = mount(Page)
  await flushPromises()
  expect(wrapper.text()).toContain('67%')
  expect(wrapper.text()).toContain('1.2 CNY')
  expect(wrapper.text()).toContain('样本不足')
})
```

- [ ] **Step 2: Add batched metrics payload**

Modify strategy route to accept:

```python
include_metrics: bool = Query(False)
```

Add helper:

```python
def _metrics_by_strategy(db: Session, rows: list[ImageProductionStrategy]) -> dict[tuple[str, int, str | None], ImageProductionMetric]:
    if not rows:
        return {}
    strategy_ids = [row.id for row in rows]
    metrics = db.query(ImageProductionMetric).filter(ImageProductionMetric.strategy_id.in_(strategy_ids)).all()
    return {(metric.strategy_id, metric.strategy_version, metric.model_id): metric for metric in metrics}
```

Serialize:

```python
metric_map = _metrics_by_strategy(db, rows) if include_metrics else {}
return {
    "ok": True,
    "strategies": [
        _strategy_payload_with_metric(row, metric_map.get((row.id, row.version, row.default_model_id)))
        if include_metrics else strategy_payload(row)
        for row in rows
    ],
}
```

- [ ] **Step 3: Render metrics**

Add to strategy row:

```vue
<span>{{ Math.round((strategy.metrics?.success_rate || 0) * 100) }}%</span>
<span>{{ strategy.metrics?.average_cost_amount || 0 }} {{ strategy.metrics?.currency || 'CNY' }}</span>
<span>{{ strategy.metrics?.average_latency_seconds || 0 }}s</span>
<span v-if="strategy.metrics?.low_sample" class="text-xs text-amber-300">样本不足</span>
```

Load with metrics:

```javascript
const resp = await listImageProductionStrategies({ include_metrics: true })
```

- [ ] **Step 4: Run strategy page tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-production-strategy-page.test.js --run
```

Expected: PASS.

## Task 7: Full Verification

**Files:** no new implementation files.

- [ ] **Step 1: Run backend Phase 4 tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_policy_runtime.py tests/test_image_production_metrics_service.py tests/test_image_ab_service.py tests/test_image_ab_api.py tests/test_image_production_migration.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run backend image production regression**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_api.py tests/test_image_creation_strategy_snapshot.py tests/test_image_selection_preview_service.py tests/test_image_production_strategy_service.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 3: Run frontend tests**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/image-production-strategy-page.test.js --run
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run build
```

Expected: PASS.

- [ ] **Step 5: Review changed files**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short server/app/db_models.py server/alembic/versions/3c4d5e6f7081_image_production_phase4_ab_metrics.py server/app/services/image_ab_test_service.py server/app/services/image_production_metrics_service.py server/app/services/image_production_policy_runtime.py server/app/routers/image_production.py server/app/services/image_creation_service.py web/src/api/imageProduction.js web/src/views/ImageCreationPage.vue web/src/views/ImageProductionStrategiesPage.vue
```

Expected: only Phase 4 implementation files are modified or added.

## Completion Criteria

- A/B preview accepts 2-4 active strategies and rejects invalid strategy counts.
- A/B preview returns total cost, request hash, strictest `ab_max_group_cost`, and `cost_limit_exceeded`.
- A/B create rejects preview drift, missing confirmation, and cost-limit exceedance before starting attempts.
- A/B create writes one group and one attempt per strategy.
- Every attempt creates a normal `ImageCreationTask`.
- Retry with the same idempotency key reuses the same group.
- Partial attempt failure is visible as `partial_failed`.
- Winner requires an approved asset.
- Winner/no-winner writes `evidence_snapshot`.
- A/B events are recorded through `ProductionAuditEvent`.
- Strategy metrics are refreshed and shown in the strategy center without per-row metric queries.
- Frontend A/B UI is optional, Chinese, accessible, and does not interrupt normal generation.

## Not In Scope

- Automatic winner selection.
- Automatic strategy mutation.
- Scheduled metrics worker.
- Standalone experiment analytics dashboard.
- Provider-online E2E against real models.
- Visual zoom/pixel comparison gallery.

## Self-Review

Spec coverage:

- A/B orchestration: Task 3 and Task 4.
- Cost hard cap: Task 1, Task 3, Task 5.
- Evidence snapshot: Task 3.
- Audit events: Task 3.
- Metrics: Task 2 and Task 6.
- Frontend workflow: Task 5 and Task 6.
- Regression verification: Task 7.

Placeholder scan required after saving:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
$patterns = @("TB"+"D", "TO"+"DO", "implement"+" later", "fill"+" in", "Add"+" appropriate", "Write tests"+" for the above", "Similar"+" to Task")
rg -n ($patterns -join "|") docs/superpowers/plans/2026-05-29-image-production-strategy-control-plane-phase4-final-execution.md
```

Expected: no matches.

## Execution Handoff

Recommended execution order:

1. Task 0
2. Task 1
3. Task 2
4. Task 3
5. Task 4
6. Task 5 and Task 6 in parallel after API contracts are stable
7. Task 7

Use `superpowers:subagent-driven-development` for implementation. Fresh subagents can split backend A/B service, frontend workbench, and strategy metrics after schema is complete.

## Plan Engineering Review Revision Report

Review status: **RESOLVED_BY_PLAN_REVISION**. The five engineering review findings have been addressed inside this execution plan. The architecture and task order are unchanged.

### Scope Challenge

Scope is accepted as-is. A/B groups, attempts, cost hard limits, evidence snapshots, audit events, metrics, and the UI workbench belong in one Phase 4 slice because each one is needed to make the strategy feedback loop trustworthy. No new subsystem, dashboard, scheduler, or provider-online E2E should be added to this phase.

### Resolved Findings

1. **[P1] (confidence: 10/10) Task 3 service tests and service implementation are now explicit.**

   Location: Task 3, Step 1 and Step 4.

   Why it matters: `superpowers:subagent-driven-development` relies on executable task instructions. The revised plan now provides concrete pytest assertions, fixtures, errors, persistence checks, and service bodies.

   Revision applied:

   - Replace every Task 3 test stub with executable pytest code.
   - Replace the service implementation signature block with full helper/function bodies or split Task 3 into smaller tasks with complete code per function.
   - Minimum required concrete tests:
     - `test_preview_ab_group_requires_multiple_strategies`
     - `test_preview_ab_group_returns_total_cost_and_request_hash`
     - `test_preview_ab_group_returns_group_cost_cap_when_policy_sets_it`
     - `test_create_ab_group_creates_attempt_tasks_with_derived_idempotency`
     - `test_create_ab_group_reuses_group_idempotency_key_for_same_request`
     - `test_create_ab_group_rejects_when_total_cost_exceeds_ab_group_cap`
     - `test_create_ab_group_records_partial_failure_when_one_attempt_fails`
     - `test_adopt_ab_winner_stores_decision_evidence_snapshot`
     - `test_mark_ab_no_winner_stores_all_attempt_evidence`
     - audit event tests for preview, create, partial failure, winner, and no-winner.

2. **[P1] (confidence: 9/10) Task 4 says to add route tests later instead of providing the test code.**

   Location: Task 4, Step 1.

   Why it matters: route wiring is where async/sync mistakes, dependency overrides, payload serialization, and named-error shapes commonly break. The plan currently has tests for invalid count and not found, but the success path and cost-limit path are described only in prose.

   Revision applied:

   - Add executable `test_ab_create_route_returns_serialized_group`.
   - Add executable `test_ab_winner_route_rejects_unapproved_attempt`.
   - Add executable `test_ab_create_route_returns_cost_limit_error`.
   - Each test must assert HTTP status, `detail.error_code` when applicable, and response keys for the success path.

3. **[P1] (confidence: 9/10) Task 5 frontend tests are now executable.**

   Location: Task 5, Step 2.

   Why it matters: the revised plan now uses concrete Vitest actions and assertions, so the frontend A/B behavior can fail before implementation.

   Revision applied:

   - Replace comment blocks with real Vitest code using the existing `mountPage()` and hoisted mock pattern from `web/src/__tests__/image-creation-page.test.js`.
   - Tests must use concrete selectors: `ab-mode-toggle`, `ab-preview-button`, `ab-cost-confirmation`, `ab-create-button`, `ab-status-live`, and `ab-choose-winner-{attemptId}`.
   - The cost-cap test must assert visible Chinese text `已超出A/B成本上限` and disabled create button.

4. **[P2] (confidence: 8/10) Task 5 implementation references `buildAbPayload()` without defining it.**

   Location: Task 5, Step 4.

   Why it matters: this is a hidden integration point between the existing image task payload and the new A/B payload. If each implementer invents it, normal single-strategy generation and A/B generation can diverge.

   Revision applied:

   - Define `buildAbPayload()` in the plan.
   - It must share the same prompt, mode, source, references, model parameters, common parameters, provider options, size, count, output format, response format, and watermark values used by normal image creation.
   - It must add only `strategy_ids`, not `strategy_id`, for A/B preview/create.

5. **[P2] (confidence: 8/10) Task 0 migration step now includes the migration body.**

   Location: Task 0, Step 4.

   Why it matters: the revised plan pins the Alembic upgrade and downgrade code directly, reducing ORM and migration drift.

   Revision applied:

   - Add full Alembic `upgrade()` and `downgrade()` code.
   - Include create/drop order for foreign keys.
   - Include all unique constraints and indexes named in ORM.

### Architecture Review

Architecture is sound after revision: A/B orchestration stays around `create_image_task()` and does not create a second image execution path. The only architecture gap is document executability, not system shape.

```text
UI A/B panel
  -> imageProduction.js A/B wrappers
  -> /api/image-production/ab-tests/*
  -> image_ab_test_service.py
     -> create_selection_preview()
     -> create_image_task()
     -> refresh_image_strategy_metrics()
     -> record_production_event()
  -> ImageProductionAbGroup / ImageProductionAbAttempt / ImageProductionMetric
```

### Code Quality Review

The planned module boundaries are good:

- A/B orchestration belongs in `image_ab_test_service.py`.
- Metric refresh belongs in `image_production_metrics_service.py`.
- Cost-cap policy belongs in `image_production_policy_runtime.py`.
- API shape belongs in `image_production.py`.
- UI state belongs in `ImageCreationPage.vue`.

Task 3 remains the largest implementation task, but the revised plan now separates the work inside the task into these concrete areas:

- Task 3A: preview, cost cap, idempotency.
- Task 3B: group create and partial failure.
- Task 3C: refresh, winner/no-winner, evidence snapshot.
- Task 3D: audit events.

### Test Review

Revised coverage status:

```text
CODE PATHS                                        STATUS
[+] schema and migration                          concrete ORM and migration body
[+] cost policy hard cap                          covered by concrete test
[+] metrics service                               covered by concrete tests
[+] A/B service preview/create/decision           concrete pytest file
[+] A/B API success/error route contracts         concrete route tests
[+] frontend A/B workbench                        concrete Vitest cases
[+] strategy center metrics                       partial: UI test present, route batch test missing
```

Required before implementation: run the verification scans in Task 7, then start with Task 0 schema work.

### Performance Review

No new performance blockers found beyond the already captured batched metrics query. The plan correctly avoids scanning tasks/assets on strategy page load by using pre-aggregated `ImageProductionMetric` rows.

### Failure Modes

| Failure mode | Revised plan status | Evidence in plan |
|---|---|---|
| Migration differs from ORM | Addressed | Task 0 Step 4 |
| A/B service behavior underspecified | Addressed | Task 3 Step 1 and Step 4 |
| API route returns wrong shape despite service passing | Addressed | Task 4 Step 1 |
| Frontend cost-cap state not actually tested | Addressed | Task 5 Step 2 |
| Normal generation payload diverges from A/B payload | Addressed | Task 5 Step 4 |

Critical gaps after revision: **0**.

### What Already Exists

- `create_image_task()` already owns image execution, cost estimation, capacity, provider submission, and task serialization.
- `create_selection_preview()` already owns preview persistence and model/cost/capacity/review checks.
- `record_production_event()` already provides redacted audit event persistence.
- Existing image creation and strategy page tests provide mock patterns to copy.

### Not In Scope

- Implementing Phase 4 business code in this review.
- Adding a new A/B audit table.
- Adding scheduled metrics jobs.
- Adding provider-online E2E.
- Adding a standalone analytics dashboard.

### ENG PLAN REVIEW - COMPLETION SUMMARY

- Step 0: Scope Challenge - scope accepted as-is.
- Architecture Review: system shape is sound.
- Code Quality Review: Task 3 is explicit enough for subagent execution.
- Test Review: previously missing executable tests are now written into the plan.
- Performance Review: 0 new issues.
- Not in scope: written.
- What already exists: written.
- Backlog updates: 0 items proposed.
- Failure modes: 5 previously flagged gaps are addressed.
- Outside voice: skipped.
- Parallelization: implementation subagents may start after Task 0 schema work is complete.
- Lake Score: 5/5 for execution readiness after this revision.

Verdict: **READY FOR IMPLEMENTATION** after the verification scans below show no high-risk plan markers.
