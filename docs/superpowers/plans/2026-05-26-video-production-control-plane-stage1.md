# Video Production Control Plane Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Stage 1 episode-level AI video production control plane so one series/episode start action creates a linked production plan/run, starts autopilot production, exposes every Segment, and makes failures repairable.

**Architecture:** `production_*` tables become the source of truth for linked runs. `VideoProductionRun` remains a stage execution record with explicit `production_plan_id`, `production_episode_id`, and `production_link_status`; linked stage payloads read `ProductionSegment`, while legacy unlinked runs keep the existing `storyboard_json` path. The frontend uses a run summary, sparse tree, Segment detail, retry impact, costs, and control APIs instead of inferring state from run assets.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Vitest, Tailwind utility classes, existing Pixelle stage client.

---

## Source Inputs

- Spec: `docs/superpowers/specs/2026-05-26-video-production-control-plane-convergence-design.md`
- Existing staged production router: `server/app/routers/video_production.py`
- Existing director router: `server/app/routers/director.py`
- Existing production models: `server/app/db_models.py`
- Existing production planning service: `server/app/services/production_plan_service.py`
- Existing staged execution service: `server/app/services/video_production_service.py`
- Existing control room page: `web/src/views/VideoProductionMonitorPage.vue`

## Out Of Scope For This Plan

- `ProductionVolume`
- 240+ minute collection production
- Douyin publishing
- visual timeline editor
- multi-user reviewer assignment
- provider fallback chains
- paid-provider E2E as a merge gate

## Plan Engineering Review Corrections

`/plan-eng-review` was run against this plan before implementation. The following corrections are part of the executable plan:

- Model tests must create real parent rows for all new foreign keys. Do not use placeholder ids such as `"plan-id"` after the migration adds FK constraints.
- `record_production_event()` must not call `db.commit()` internally. It should `flush()` only and let the caller own the transaction boundary.
- Director planning must make `include_segments` deterministic. `include_segments=false` creates plan/episode/scene/shot rows only; `include_segments=true` creates or reuses Segment rows through one idempotent service.
- Linked execution helpers must preserve legacy call compatibility. Keep `image_stage_frames(run)` valid and add `db` as an optional keyword argument.
- Linked stage tests must define their own fixtures/helpers in the test file instead of referencing undeclared fixtures.

## File Structure

Create:

- `server/alembic/versions/d4e5f6a7b8c9_control_plane_convergence.py` - nullable links, version fields, review target fields, job resume fields, observability table.
- `server/app/services/production_errors.py` - named repairable error contract.
- `server/app/services/production_observability.py` - structured event writer and summary helpers.
- `server/app/services/production_run_service.py` - linked run resolution, start flow, run summary.
- `server/app/services/production_segment_detail_service.py` - Segment detail payloads.
- `server/app/services/production_retry_service.py` - retry impact dry-run and mutation wrapper.
- `server/app/services/production_cost_summary_service.py` - run cost summaries.
- `server/app/services/production_status_aggregation.py` - bottom-up status recomputation.
- `server/tests/test_video_production_control_plane_models.py`
- `server/tests/test_video_production_named_errors.py`
- `server/tests/test_video_production_start_flow_contract.py`
- `server/tests/test_video_production_segment_detail_api.py`
- `server/tests/test_video_production_costs_api.py`
- `server/tests/test_video_production_retry_impact.py`
- `server/tests/test_video_production_pause_resume.py`
- `server/tests/test_video_production_linked_stage_execution.py`
- `server/tests/test_video_production_observability_events.py`
- `web/src/__tests__/production-control-room-autopilot.test.js`
- `web/src/__tests__/production-control-room-empty-states.test.js`
- `web/src/__tests__/production-control-room-a11y.test.js`

Modify:

- `server/app/db_models.py` - add model columns and `ProductionAuditEvent`.
- `server/app/routers/director.py` - add `/episode-plan` and `/shot-segments` aliases.
- `server/app/routers/video_production.py` - add start, pause, resume, retry, costs, detail, retry-impact routes and structured error responses.
- `server/app/services/production_plan_service.py` - split idempotent plan and segment creation.
- `server/app/services/production_queue_service.py` - pause/resume with recorded resume status.
- `server/app/services/production_cost_service.py` - route-ready cost helpers and budget block event.
- `server/app/services/production_review_service.py` - write review target/version snapshots.
- `server/app/services/production_segment_service.py` - delegate retry to impact-aware service.
- `server/app/services/production_tree_service.py` - keep tree sparse; add exception counts.
- `server/app/services/video_production_service.py` - linked/legacy execution paths and latest asset invariant.
- `server/app/services/video_production_state.py` - preserve legacy run gates while linked runs use production state.
- `web/src/api/director.js` - add `createEpisodePlan` and `createShotSegments`.
- `web/src/api/videoProduction.js` - add start flow, run controls, costs, Segment detail, retry impact.
- `web/src/views/SeriesDetailPage.vue` - call one user-facing start flow.
- `web/src/views/VideoProductionMonitorPage.vue` - rebuild control room around summary/tree/detail/actions.

## Data Contracts

Named repairable error response:

```json
{
  "error_code": "SEGMENT_PLAN_MISSING",
  "message": "No production segments exist for this episode.",
  "repair_action": "Generate shot segments",
  "repair_route": "/series/{series_id}",
  "retryable": true,
  "affected_ids": ["episode-id"]
}
```

Linked run summary response:

```json
{
  "ok": true,
  "run": {
    "id": "run-id",
    "series_id": "series-id",
    "episode_id": "episode-id",
    "production_plan_id": "plan-id",
    "production_episode_id": "production-episode-id",
    "production_link_status": "linked",
    "status": "image_batch_running",
    "current_stage": "image_generation",
    "counts": {
      "segments": 30,
      "failed": 0,
      "human_review": 0,
      "retry_wait": 0
    }
  }
}
```

Segment detail response:

```json
{
  "ok": true,
  "segment": {"id": "seg-id", "segment_id": "shot-1-seg-01", "status": "failed_retryable", "version": 1},
  "path": {"plan_id": "plan-id", "episode_plan_id": "pe-id", "scene_id": "scene-id", "shot_id": "shot-id"},
  "latest_assets": {"image": {"id": "asset-image", "version": 1}, "video_segment": null},
  "asset_history": {"image": [], "video_segment": []},
  "reviews": [],
  "provider_trace": {"provider_task_id": "task-id"},
  "cost": {"actual_cost": 0.02, "estimated_remaining_cost": 0.4, "estimate_status": "known"},
  "allowed_actions": ["retry"],
  "repair": null
}
```

### Task 1: Model And Migration Convergence

**Files:**
- Create: `server/alembic/versions/d4e5f6a7b8c9_control_plane_convergence.py`
- Modify: `server/app/db_models.py`
- Test: `server/tests/test_video_production_control_plane_models.py`

- [ ] **Step 1: Write failing model tests**

Add `server/tests/test_video_production_control_plane_models.py`:

```python
from app.db_models import (
    Episode,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)


def _linked_context(db):
    series = Series(title="Control Plane", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        active_version=1,
        target_total_duration_seconds=8,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=8,
    )
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(
        episode_plan_id=production_episode.id,
        scene_id="scene-1",
        order_index=1,
        status="ready",
    )
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-1",
        order_index=1,
        status="ready",
        character_ids=[],
        action="walk forward",
        shot_type="medium",
        duration_seconds=8,
    )
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status="planned",
        duration_seconds=8,
        continuity_mode="narrative_cut",
        version=1,
        image_prompt="image prompt",
        video_prompt="video prompt",
        reference_roles_json=[],
    )
    db.add(segment)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id)
    db.add(run)
    db.flush()
    return {
        "series": series,
        "episode": episode,
        "plan": plan,
        "production_episode": production_episode,
        "shot": shot,
        "segment": segment,
        "run": run,
    }


def test_video_production_run_has_real_production_links(db):
    ctx = _linked_context(db)
    run = ctx["run"]
    plan = ctx["plan"]
    production_episode = ctx["production_episode"]

    run.production_plan_id = plan.id
    run.production_episode_id = production_episode.id
    run.production_link_status = "linked"
    db.commit()

    saved = db.query(VideoProductionRun).filter_by(id=run.id).one()
    assert saved.production_plan_id == plan.id
    assert saved.production_episode_id == production_episode.id
    assert saved.production_link_status == "linked"


def test_asset_and_review_store_latest_version_truth(db):
    ctx = _linked_context(db)
    run = VideoProductionRun(
        series_id=ctx["series"].id,
        episode_id=ctx["episode"].id,
        production_plan_id=ctx["plan"].id,
        production_episode_id=ctx["production_episode"].id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=ctx["episode"].id,
        frame_id=ctx["segment"].id,
        asset_type="image",
        stage="image_generation",
        production_segment_id=ctx["segment"].id,
        production_shot_id=ctx["shot"].id,
        target_type="production_segment",
        target_id=ctx["segment"].id,
        version=2,
        is_latest=True,
        source_version=2,
        copy_status="registered",
        checksum="sha256:test",
        size_bytes=12,
    )
    db.add(asset)
    db.flush()
    review = VideoReviewRecord(
        asset_id=asset.id,
        run_id=run.id,
        review_type="human",
        status="approved",
        target_type="production_segment",
        target_id=ctx["segment"].id,
        production_segment_id=ctx["segment"].id,
        asset_version=2,
        is_latest_asset_review=True,
    )
    db.add(review)
    db.commit()

    assert db.query(VideoProductionAsset).one().is_latest is True
    assert db.query(VideoReviewRecord).one().asset_version == 2


def test_job_pause_resume_fields_and_audit_event(db):
    ctx = _linked_context(db)
    job = ProductionJob(
        plan_id=ctx["plan"].id,
        target_type="production_segment",
        target_id=ctx["segment"].id,
        stage="image_generation",
        status="blocked",
        resume_status="queued",
        blocked_reason="PAUSED_BY_OPERATOR",
        idempotency_key="plan:seg:image:v1",
    )
    db.add(job)
    event = ProductionAuditEvent(
        event_type="run.created",
        run_id=ctx["run"].id,
        production_plan_id=ctx["plan"].id,
        production_episode_id=ctx["production_episode"].id,
        production_segment_id=ctx["segment"].id,
        payload_json={"redacted": True},
    )
    db.add(event)
    db.commit()

    assert db.query(ProductionJob).one().resume_status == "queued"
    assert db.query(ProductionAuditEvent).one().event_type == "run.created"
```

- [ ] **Step 2: Run model tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_video_production_control_plane_models.py -v
```

Expected: FAIL because the new columns and `ProductionAuditEvent` do not exist.

- [ ] **Step 3: Add SQLAlchemy fields**

In `server/app/db_models.py`, add these fields to `VideoProductionRun`:

```python
production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
production_link_status = Column(String(30), nullable=False, default="legacy_unlinked")
```

Add these indexes to `VideoProductionRun.__table_args__`:

```python
Index("idx_video_production_runs_production_links", "production_plan_id", "production_episode_id"),
Index("idx_video_production_runs_link_status", "production_link_status"),
```

Add these fields to `VideoProductionAsset`:

```python
production_shot_id = Column(String(36), ForeignKey("production_shots.id", ondelete="SET NULL"), nullable=True)
is_latest = Column(Boolean, nullable=False, default=True)
source_version = Column(Integer, nullable=False, default=1)
copy_status = Column(String(30), nullable=False, default="registered")
checksum = Column(String(120), nullable=True)
size_bytes = Column(Integer, nullable=True)
```

Add these indexes to `VideoProductionAsset.__table_args__`:

```python
Index("idx_video_assets_production_shot", "production_shot_id"),
Index("idx_video_assets_segment_latest", "production_segment_id", "asset_type", "is_latest"),
```

Add these fields to `VideoReviewRecord`:

```python
target_type = Column(String(30), nullable=True)
target_id = Column(String(36), nullable=True)
production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
asset_version = Column(Integer, nullable=True)
is_latest_asset_review = Column(Boolean, nullable=False, default=True)
```

Add this index to `VideoReviewRecord.__table_args__`:

```python
Index("idx_video_review_target_version", "target_type", "target_id", "asset_version"),
```

Add these fields to `ProductionJob`:

```python
resume_status = Column(String(30), nullable=True)
blocked_reason = Column(String(120), nullable=True)
paused_at = Column(DateTime, nullable=True)
```

Add this index to `ProductionJob.__table_args__`:

```python
Index("idx_production_jobs_plan_status_resume", "plan_id", "status", "resume_status"),
```

Add this new model below `ProductionCostEvent`:

```python
class ProductionAuditEvent(Base):
    __tablename__ = "production_audit_events"
    __table_args__ = (
        Index("idx_production_audit_events_run_id", "run_id"),
        Index("idx_production_audit_events_plan_id", "production_plan_id"),
        Index("idx_production_audit_events_segment_id", "production_segment_id"),
        Index("idx_production_audit_events_type", "event_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(String(80), nullable=False)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    payload_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
```

- [ ] **Step 4: Add Alembic migration**

Create `server/alembic/versions/d4e5f6a7b8c9_control_plane_convergence.py` with `down_revision = "c3d4e5f6a8b9"`. Use `op.create_table()` for `production_audit_events`. Use `op.batch_alter_table()` for every existing table that receives new columns, indexes, or foreign keys so the migration works under the SQLite test database as well as the deployed SQL engine.

Migration shape:

```python
with op.batch_alter_table("video_production_runs") as batch:
    batch.add_column(sa.Column("production_plan_id", sa.String(length=36), nullable=True))
    batch.add_column(sa.Column("production_episode_id", sa.String(length=36), nullable=True))
    batch.add_column(sa.Column("production_link_status", sa.String(length=30), nullable=False, server_default="legacy_unlinked"))
    batch.create_foreign_key("fk_video_runs_production_plan", "production_plans", ["production_plan_id"], ["id"], ondelete="SET NULL")
    batch.create_foreign_key("fk_video_runs_production_episode", "production_episodes", ["production_episode_id"], ["id"], ondelete="SET NULL")
    batch.create_index("idx_video_production_runs_production_links", ["production_plan_id", "production_episode_id"])
    batch.create_index("idx_video_production_runs_link_status", ["production_link_status"])
```

Repeat the same `batch_alter_table()` pattern for `video_production_assets`, `video_review_records`, and `production_jobs`. Use nullable columns for links/version metadata so existing rows remain valid. Set `production_link_status` server default to `"legacy_unlinked"` and `is_latest` server default to `"1"` for SQLite compatibility.

- [ ] **Step 5: Run model tests and migration smoke**

Run:

```powershell
cd server
pytest tests/test_video_production_control_plane_models.py -v
alembic upgrade head
```

Expected: PASS, and Alembic reaches revision `d4e5f6a7b8c9`.

- [ ] **Step 6: Commit**

```powershell
git add server/app/db_models.py server/alembic/versions/d4e5f6a7b8c9_control_plane_convergence.py server/tests/test_video_production_control_plane_models.py
git commit -m "feat: add video production control plane model links"
```

### Task 2: Named Errors And Observability

**Files:**
- Create: `server/app/services/production_errors.py`
- Create: `server/app/services/production_observability.py`
- Modify: `server/app/routers/video_production.py`
- Test: `server/tests/test_video_production_named_errors.py`
- Test: `server/tests/test_video_production_observability_events.py`

- [ ] **Step 1: Write failing named error tests**

Add `server/tests/test_video_production_named_errors.py`:

```python
from app.services.production_errors import (
    ProductionErrorCode,
    ProductionRepairableError,
    to_http_detail,
)


def test_repairable_error_serializes_contract():
    error = ProductionRepairableError(
        code=ProductionErrorCode.SEGMENT_PLAN_MISSING,
        message="No production segments exist for this episode.",
        repair_action="Generate shot segments",
        repair_route="/series/series-id",
        retryable=True,
        affected_ids=["episode-id"],
    )

    assert to_http_detail(error) == {
        "error_code": "SEGMENT_PLAN_MISSING",
        "message": "No production segments exist for this episode.",
        "repair_action": "Generate shot segments",
        "repair_route": "/series/series-id",
        "retryable": True,
        "affected_ids": ["episode-id"],
    }
```

Add `server/tests/test_video_production_observability_events.py`:

```python
from app.db_models import ProductionAuditEvent
from app.services.production_observability import record_production_event


def test_record_production_event_redacts_secret_like_fields(db):
    event = record_production_event(
        db,
        event_type="stage.submitted",
        run_id="run-id",
        production_plan_id="plan-id",
        production_episode_id="episode-id",
        production_segment_id="seg-id",
        provider_task_id="task-id",
        payload={"api_key": "secret", "provider": "ark", "model": "doubao-seedance-2.0"},
    )

    saved = db.query(ProductionAuditEvent).filter_by(id=event.id).one()
    assert saved.payload_json["api_key"] == "[REDACTED]"
    assert saved.payload_json["provider"] == "ark"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_video_production_named_errors.py tests/test_video_production_observability_events.py -v
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Add named error service**

Create `server/app/services/production_errors.py`:

```python
from dataclasses import dataclass, field
from enum import Enum


class ProductionErrorCode(str, Enum):
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
    PAUSED_BY_OPERATOR = "PAUSED_BY_OPERATOR"
    RETRY_IMPACT_BLOCKED = "RETRY_IMPACT_BLOCKED"


@dataclass
class ProductionRepairableError(ValueError):
    code: ProductionErrorCode
    message: str
    repair_action: str
    repair_route: str | None = None
    retryable: bool = False
    affected_ids: list[str] = field(default_factory=list)


def to_http_detail(error: ProductionRepairableError) -> dict:
    return {
        "error_code": error.code.value,
        "message": error.message,
        "repair_action": error.repair_action,
        "repair_route": error.repair_route,
        "retryable": error.retryable,
        "affected_ids": error.affected_ids,
    }
```

- [ ] **Step 4: Add observability service**

Create `server/app/services/production_observability.py`:

```python
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import ProductionAuditEvent

SECRET_KEYS = {"api_key", "api_secret", "authorization", "token", "secret"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SECRET_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def record_production_event(
    db: Session,
    *,
    event_type: str,
    run_id: str | None = None,
    production_plan_id: str | None = None,
    production_episode_id: str | None = None,
    production_segment_id: str | None = None,
    provider_task_id: str | None = None,
    payload: dict | None = None,
) -> ProductionAuditEvent:
    event = ProductionAuditEvent(
        event_type=event_type,
        run_id=run_id,
        production_plan_id=production_plan_id,
        production_episode_id=production_episode_id,
        production_segment_id=production_segment_id,
        provider_task_id=provider_task_id,
        payload_json=_redact(payload or {}),
    )
    db.add(event)
    db.flush()
    return event
```

- [ ] **Step 5: Wire router error handling**

In `server/app/routers/video_production.py`, import:

```python
from app.services.production_errors import ProductionRepairableError, to_http_detail
```

Wrap route service calls that can raise repairable errors:

```python
except ProductionRepairableError as exc:
    raise HTTPException(409, to_http_detail(exc))
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd server
pytest tests/test_video_production_named_errors.py tests/test_video_production_observability_events.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/production_errors.py server/app/services/production_observability.py server/app/routers/video_production.py server/tests/test_video_production_named_errors.py server/tests/test_video_production_observability_events.py
git commit -m "feat: add repairable production errors and events"
```

### Task 3: Idempotent Director Planning Routes

**Files:**
- Modify: `server/app/services/production_plan_service.py`
- Modify: `server/app/routers/director.py`
- Test: `server/tests/test_director_episode_plan.py`
- Test: `server/tests/test_director_shot_segments.py`

- [ ] **Step 1: Write failing route alias tests**

Add `server/tests/test_director_episode_plan.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, ProductionEpisode, ProductionPlan, ProductionSegment, Series
from app.main import app


def _locked_episode(db):
    series = Series(
        title="Episode Plan",
        logline="Test",
        genre="drama",
        story_bible_json={"style_lock": {"locked": True, "version": 1, "visual_style": {}}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-1", "duration": 10, "image_prompt": "A", "video_prompt": "B"}]},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_episode_plan_alias_creates_plan_and_segments_idempotently(db):
    series, episode = _locked_episode(db)
    client = TestClient(app)

    first = client.post("/api/director/episode-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "include_segments": True,
    })
    second = client.post("/api/director/episode-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "include_segments": True,
    })

    assert first.status_code == 200
    assert second.status_code == 200
    assert db.query(ProductionPlan).count() == 1
    assert db.query(ProductionEpisode).count() == 1
    assert db.query(ProductionSegment).count() == 2
```

Add `server/tests/test_director_shot_segments.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, ProductionEpisode, ProductionPlan, ProductionScene, ProductionShot, ProductionSegment, Series
from app.main import app


def test_shot_segments_route_is_idempotent(db):
    series = Series(title="Segments", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, target_total_duration_seconds=10)
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready", target_duration_seconds=10)
    db.add(prod_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready", duration_seconds=10)
    db.add(shot)
    db.commit()

    client = TestClient(app)
    for _ in range(2):
        resp = client.post("/api/director/shot-segments", json={
            "production_episode_id": prod_episode.id,
            "preferred_segment_seconds": 8,
        })
        assert resp.status_code == 200

    assert db.query(ProductionSegment).count() == 2
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_director_episode_plan.py tests/test_director_shot_segments.py -v
```

Expected: FAIL because `/episode-plan` and `/shot-segments` do not exist and plan creation creates duplicates.

- [ ] **Step 3: Split idempotent service functions**

In `server/app/services/production_plan_service.py`, add:

```python
def ensure_episode_production_plan(
    db: Session,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
    include_segments: bool = True,
) -> ProductionPlan:
    existing = (
        db.query(ProductionPlan)
        .join(ProductionEpisode, ProductionEpisode.plan_id == ProductionPlan.id)
        .filter(ProductionPlan.series_id == series_id, ProductionEpisode.episode_id == episode_id)
        .order_by(ProductionPlan.updated_at.desc(), ProductionPlan.created_at.desc())
        .first()
    )
    if existing:
        if include_segments:
            production_episode = db.query(ProductionEpisode).filter(
                ProductionEpisode.plan_id == existing.id,
                ProductionEpisode.episode_id == episode_id,
            ).one()
            ensure_shot_segments(db, production_episode.id)
        return existing
    return create_episode_production_plan(
        db,
        series_id,
        episode_id,
        target_duration_seconds=target_duration_seconds,
        budget_limit=budget_limit,
        include_segments=include_segments,
    )


def ensure_shot_segments(
    db: Session,
    production_episode_id: str,
    preferred_segment_seconds: float = MAX_SEGMENT_SECONDS,
) -> list[ProductionSegment]:
    production_episode = db.query(ProductionEpisode).filter(ProductionEpisode.id == production_episode_id).first()
    if not production_episode:
        raise ValueError("Production episode not found")
    existing = (
        db.query(ProductionSegment)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == production_episode_id)
        .order_by(ProductionSegment.order_index.asc(), ProductionSegment.id.asc())
        .all()
    )
    if existing:
        return existing
    shots = (
        db.query(ProductionShot)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == production_episode_id)
        .order_by(ProductionScene.order_index.asc(), ProductionShot.order_index.asc())
        .all()
    )
    created: list[ProductionSegment] = []
    for shot in shots:
        previous: ProductionSegment | None = None
        durations = _segment_durations(float(shot.duration_seconds or DEFAULT_FRAME_SECONDS), preferred_segment_seconds)
        for index, duration in enumerate(durations, start=1):
            segment = ProductionSegment(
                shot_plan_id=shot.id,
                previous_segment_id=previous.id if previous else None,
                segment_id=f"{shot.shot_id}-seg-{index:02d}",
                order_index=index,
                status=SEGMENT_PLANNED,
                duration_seconds=duration,
                continuity_mode=CONTINUITY_CONTINUOUS_ACTION if len(durations) > 1 else CONTINUITY_NARRATIVE_CUT,
                version=1,
                image_prompt=shot.action or "",
                video_prompt=shot.action or "",
                reference_roles_json=[],
            )
            db.add(segment)
            db.flush()
            created.append(segment)
            previous = segment
    db.commit()
    return created
```

Update `create_episode_production_plan()` so `include_segments` is deterministic:

```python
def create_episode_production_plan(
    db: Session,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
    include_segments: bool = True,
) -> ProductionPlan:
    ...
    for frame_index, frame in enumerate(frames, start=1):
        ...
        db.add(shot)
        db.flush()

        if not include_segments:
            continue

        segment_durations = _segment_durations(frame_duration)
        ...
```

`include_segments=False` must create only `ProductionPlan`, `ProductionEpisode`, `ProductionScene`, and `ProductionShot`. `include_segments=True` must create or reuse `ProductionSegment` rows through the same idempotent semantics used by `/shot-segments`.

- [ ] **Step 4: Add director route contracts**

In `server/app/routers/director.py`, add request models:

```python
class EpisodePlanRequest(EpisodeProductionPlanRequest):
    include_segments: bool = True


class ShotSegmentsRequest(BaseModel):
    production_episode_id: str
    preferred_segment_seconds: float = 8.0
```

Add routes:

```python
@router.post("/episode-plan")
def create_episode_plan_endpoint(body: EpisodePlanRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.db_models import ProductionEpisode, ProductionSegment, ProductionScene, ProductionShot
    from app.services.production_plan_service import ensure_episode_production_plan, ensure_shot_segments

    try:
        plan = ensure_episode_production_plan(
            db,
            body.series_id,
            body.episode_id,
            target_duration_seconds=body.target_duration_seconds or body.target_duration,
            budget_limit=body.budget_limit,
            include_segments=body.include_segments,
        )
        production_episode = db.query(ProductionEpisode).filter(
            ProductionEpisode.plan_id == plan.id,
            ProductionEpisode.episode_id == body.episode_id,
        ).one()
        segments = ensure_shot_segments(db, production_episode.id) if body.include_segments else []
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "plan": {"id": plan.id, "series_id": plan.series_id, "status": plan.status}, "production_episode_id": production_episode.id, "segment_count": len(segments)}


@router.post("/shot-segments")
def create_shot_segments_endpoint(body: ShotSegmentsRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_plan_service import ensure_shot_segments

    try:
        segments = ensure_shot_segments(db, body.production_episode_id, body.preferred_segment_seconds)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "segments": [{"id": item.id, "segment_id": item.segment_id, "version": item.version} for item in segments], "segment_count": len(segments)}
```

Keep `/episode-production-plan` as a compatibility alias by calling `ensure_episode_production_plan()` and `ensure_shot_segments()`.

- [ ] **Step 5: Run tests**

Run:

```powershell
cd server
pytest tests/test_director_episode_plan.py tests/test_director_shot_segments.py tests/test_production_plan_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/services/production_plan_service.py server/app/routers/director.py server/tests/test_director_episode_plan.py server/tests/test_director_shot_segments.py
git commit -m "feat: add idempotent episode planning routes"
```

### Task 4: Linked Run Resolver And One Start Flow

**Files:**
- Create: `server/app/services/production_run_service.py`
- Modify: `server/app/routers/video_production.py`
- Modify: `server/app/services/video_production_service.py`
- Test: `server/tests/test_video_production_start_flow_contract.py`
- Test: `server/tests/test_video_production_run_binding.py`

- [ ] **Step 1: Write failing start-flow tests**

Add `server/tests/test_video_production_start_flow_contract.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, ProductionSegment, Series, VideoProductionRun
from app.main import app


def _series_episode(db):
    series = Series(
        title="Start Flow",
        logline="One sentence",
        genre="drama",
        target_duration=10,
        story_bible_json={"style_lock": {"locked": True, "version": 1, "visual_style": {}}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-1", "duration": 10, "image_prompt": "A", "video_prompt": "B"}]},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_start_flow_creates_plan_segments_linked_run_and_returns_route(db, monkeypatch):
    async def fake_start_image_stage(db, run_id):
        run = db.query(VideoProductionRun).filter_by(id=run_id).one()
        run.status = "image_batch_running"
        run.current_stage = "image_generation"
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr("app.services.production_run_service.start_image_stage", fake_start_image_stage)
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": True,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["route"] == f"/video-production/{body['run']['id']}"
    assert body["run"]["production_link_status"] == "linked"
    assert db.query(ProductionSegment).count() == 2
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
cd server
pytest tests/test_video_production_start_flow_contract.py -v
```

Expected: FAIL because `/runs/start` and `production_run_service` do not exist.

- [ ] **Step 3: Add linked run service**

First update `server/app/services/video_production_service.py` so linked run creation can avoid the legacy helper's internal commit:

```python
def create_run_from_episode(
    db: Session,
    series_id: str,
    episode_id: str,
    *,
    commit: bool = True,
) -> VideoProductionRun:
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise VideoProductionError("Episode not found")
    storyboard = episode.storyboard_json or {}
    frames = storyboard.get("frames") or []
    if not frames:
        raise VideoProductionError("Episode storyboard_json is empty")

    normalized_frames = []
    for index, frame in enumerate(frames):
        normalized_frames.append({**frame, "frame_id": _frame_id(frame, index)})

    run = VideoProductionRun(
        series_id=series_id,
        episode_id=episode_id,
        status="draft",
        current_stage="storyboard_ready",
        storyboard_json={**storyboard, "frames": normalized_frames},
    )
    db.add(run)
    db.flush()
    if commit:
        db.commit()
        db.refresh(run)
    return run
```

The existing `/runs` legacy route keeps using the default `commit=True`. Linked start flow must pass `commit=False` so the run link, audit event, and run creation are committed together.

Create `server/app/services/production_run_service.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import Episode, ProductionEpisode, ProductionPlan, ProductionSegment, ProductionScene, ProductionShot, Series, VideoProductionRun
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.production_observability import record_production_event
from app.services.production_plan_service import ensure_episode_production_plan, ensure_shot_segments
from app.services.video_production_service import create_run_from_episode, start_image_stage


def _style_lock(series: Series) -> dict:
    story_bible = series.story_bible_json if isinstance(series.story_bible_json, dict) else {}
    style_lock = story_bible.get("style_lock") or {}
    return style_lock if isinstance(style_lock, dict) else {}


def _production_episode_for_plan(db: Session, plan_id: str, episode_id: str) -> ProductionEpisode:
    return db.query(ProductionEpisode).filter(
        ProductionEpisode.plan_id == plan_id,
        ProductionEpisode.episode_id == episode_id,
    ).one()


def segment_count_for_episode(db: Session, production_episode_id: str) -> int:
    return (
        db.query(ProductionSegment)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == production_episode_id)
        .count()
    )


def create_linked_run(db: Session, series_id: str, episode_id: str, production_plan_id: str | None = None) -> VideoProductionRun:
    query = (
        db.query(ProductionPlan)
        .join(ProductionEpisode, ProductionEpisode.plan_id == ProductionPlan.id)
        .filter(ProductionPlan.series_id == series_id, ProductionEpisode.episode_id == episode_id)
    )
    if production_plan_id:
        query = query.filter(ProductionPlan.id == production_plan_id)
    candidates = query.order_by(ProductionPlan.updated_at.desc(), ProductionPlan.created_at.desc()).all()
    if not candidates:
        raise ProductionRepairableError(
            code=ProductionErrorCode.SEGMENT_PLAN_MISSING,
            message="No production plan exists for this episode.",
            repair_action="Generate episode plan",
            repair_route=f"/series/{series_id}",
            retryable=True,
            affected_ids=[episode_id],
        )
    if len(candidates) > 1 and not production_plan_id:
        raise ProductionRepairableError(
            code=ProductionErrorCode.RUN_LINK_AMBIGUOUS,
            message="This episode has multiple production plans. Choose one before creating a run.",
            repair_action="Repair run-plan link",
            repair_route=f"/series/{series_id}",
            retryable=False,
            affected_ids=[episode_id],
        )
    plan = candidates[0]
    production_episode = _production_episode_for_plan(db, plan.id, episode_id)
    if segment_count_for_episode(db, production_episode.id) == 0:
        raise ProductionRepairableError(
            code=ProductionErrorCode.SEGMENT_PLAN_MISSING,
            message="No production segments exist for this episode.",
            repair_action="Generate shot segments",
            repair_route=f"/series/{series_id}",
            retryable=True,
            affected_ids=[production_episode.id],
        )
    run = create_run_from_episode(db, series_id, episode_id, commit=False)
    run.production_plan_id = plan.id
    run.production_episode_id = production_episode.id
    run.production_link_status = "linked"
    trace = run.model_trace_json or {}
    trace["production_plan_id"] = plan.id
    trace["production_episode_id"] = production_episode.id
    run.model_trace_json = trace
    record_production_event(db, event_type="run.created", run_id=run.id, production_plan_id=plan.id, production_episode_id=production_episode.id, payload={"link_status": "linked"})
    db.commit()
    db.refresh(run)
    return run


async def start_episode_production(
    db: Session,
    *,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
    autostart_images: bool = True,
) -> VideoProductionRun:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ProductionRepairableError(
            code=ProductionErrorCode.RUN_LINK_MISSING,
            message="Series not found.",
            repair_action="Open a valid series",
            affected_ids=[series_id],
        )
    if _style_lock(series).get("locked") is not True:
        raise ProductionRepairableError(
            code=ProductionErrorCode.STYLE_LOCK_MISSING,
            message="Series style is not locked.",
            repair_action="Lock style before production",
            repair_route=f"/series/{series_id}",
            retryable=True,
            affected_ids=[series_id],
        )
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise ProductionRepairableError(
            code=ProductionErrorCode.RUN_LINK_MISSING,
            message="Episode not found.",
            repair_action="Open a valid episode",
            repair_route=f"/series/{series_id}",
            affected_ids=[episode_id],
        )
    storyboard = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
    if not storyboard.get("frames"):
        raise ProductionRepairableError(
            code=ProductionErrorCode.STORYBOARD_MISSING,
            message="Episode storyboard is missing.",
            repair_action="Generate automatic storyboard",
            repair_route=f"/series/{series_id}",
            retryable=True,
            affected_ids=[episode_id],
        )
    plan = ensure_episode_production_plan(db, series_id, episode_id, target_duration_seconds, budget_limit)
    production_episode = _production_episode_for_plan(db, plan.id, episode_id)
    ensure_shot_segments(db, production_episode.id)
    run = create_linked_run(db, series_id, episode_id, production_plan_id=plan.id)
    if autostart_images:
        run = await start_image_stage(db, run.id)
    return run
```

- [ ] **Step 4: Add `/runs/start` route and linked run payload fields**

In `server/app/routers/video_production.py`, add request model:

```python
class StartRunRequest(BaseModel):
    series_id: str
    episode_id: str
    target_duration_seconds: int | None = None
    budget_limit: float | None = None
    autostart_images: bool = True
```

Extend `_run_payload()` with:

```python
"production_plan_id": run.production_plan_id,
"production_episode_id": run.production_episode_id,
"production_link_status": run.production_link_status,
```

Add route:

```python
@router.post("/runs/start")
async def start_run_flow(body: StartRunRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_run_service import start_episode_production
    try:
        run = await start_episode_production(
            db,
            series_id=body.series_id,
            episode_id=body.episode_id,
            target_duration_seconds=body.target_duration_seconds,
            budget_limit=body.budget_limit,
            autostart_images=body.autostart_images,
        )
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run), "route": f"/video-production/{run.id}"}
```

- [ ] **Step 5: Run tests**

Run:

```powershell
cd server
pytest tests/test_video_production_start_flow_contract.py tests/test_video_production_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/services/production_run_service.py server/app/routers/video_production.py server/tests/test_video_production_start_flow_contract.py
git commit -m "feat: add linked production start flow"
```

### Task 5: Segment Detail, Costs, And Retry Impact Read APIs

**Files:**
- Create: `server/app/services/production_segment_detail_service.py`
- Create: `server/app/services/production_retry_service.py`
- Create: `server/app/services/production_cost_summary_service.py`
- Modify: `server/app/routers/video_production.py`
- Modify: `web/src/api/videoProduction.js`
- Test: `server/tests/test_video_production_segment_detail_api.py`
- Test: `server/tests/test_video_production_costs_api.py`
- Test: `server/tests/test_video_production_retry_impact.py`

- [ ] **Step 1: Write failing API tests**

Add `server/tests/test_video_production_segment_detail_api.py`, `server/tests/test_video_production_costs_api.py`, and `server/tests/test_video_production_retry_impact.py`. Use this shared helper in each file or move it into a local fixture in the first file and duplicate only the fields needed by the other two tests:

```python
from fastapi.testclient import TestClient

from app.db_models import (
    Episode,
    ProductionCostEvent,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.main import app


def _linked_segment_context(db, *, segment_status="failed_retryable"):
    series = Series(title="Detail", logline="Detail", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, current_cost=0.0)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready", duration_seconds=8)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status=segment_status,
        duration_seconds=8,
        image_prompt="image",
        video_prompt="video",
        reference_roles_json=[],
    )
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type="image",
        stage="image_generation",
        production_segment_id=segment.id,
        production_shot_id=shot.id,
        target_type="production_segment",
        target_id=segment.id,
        version=1,
        is_latest=True,
        source_version=segment.version,
        status="approved",
        url="https://example.test/image.png",
    )
    db.add(asset)
    db.add(ProductionCostEvent(plan_id=plan.id, episode_plan_id=production_episode.id, segment_id=segment.id, stage="image_generation", actual_cost=0.02, provider="mock", model_name="mock-image"))
    db.commit()
    return run, segment


def test_segment_detail_returns_latest_assets_and_actions(db):
    run, segment = _linked_segment_context(db)
    client = TestClient(app)

    resp = client.get(f"/api/video-production/segments/{segment.id}/detail")

    assert resp.status_code == 200
    detail = resp.json()
    assert detail["segment"]["id"] == segment.id
    assert detail["latest_assets"]["image"]["is_latest"] is True
    assert "retry" in detail["allowed_actions"]


def test_retry_impact_returns_local_scope(db):
    run, segment = _linked_segment_context(db)
    client = TestClient(app)

    resp = client.get(f"/api/video-production/segments/{segment.id}/retry-impact")

    assert resp.status_code == 200
    impact = resp.json()
    assert impact["allowed"] is True
    assert impact["target_new_version"] == segment.version + 1


def test_run_costs_returns_known_or_unknown_estimate(db):
    run, segment = _linked_segment_context(db)
    client = TestClient(app)

    resp = client.get(f"/api/video-production/runs/{run.id}/costs")

    assert resp.status_code == 200
    costs = resp.json()
    assert costs["actual_cost"] >= 0.02
    assert costs["estimate_status"] in {"known", "unknown"}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_video_production_segment_detail_api.py tests/test_video_production_costs_api.py tests/test_video_production_retry_impact.py -v
```

Expected: FAIL because endpoints and services do not exist.

- [ ] **Step 3: Add Segment detail service**

Create `server/app/services/production_segment_detail_service.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionEpisode, ProductionScene, ProductionSegment, ProductionShot, VideoProductionAsset, VideoReviewRecord


def _asset_payload(asset: VideoProductionAsset | None) -> dict | None:
    if not asset:
        return None
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "version": asset.version,
        "is_latest": asset.is_latest,
        "status": asset.status,
        "url": asset.url,
        "provider_task_id": asset.provider_task_id or asset.pixelle_task_id,
        "prompt_hash": asset.prompt_hash,
        "source_version": asset.source_version,
    }


def get_segment_detail(db: Session, segment_id: str, history_limit: int = 10) -> dict:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not segment:
        raise ValueError("Production segment not found")
    shot = db.query(ProductionShot).filter(ProductionShot.id == segment.shot_plan_id).one()
    scene = db.query(ProductionScene).filter(ProductionScene.id == shot.scene_plan_id).one()
    episode = db.query(ProductionEpisode).filter(ProductionEpisode.id == scene.episode_plan_id).one()
    assets = (
        db.query(VideoProductionAsset)
        .filter(VideoProductionAsset.production_segment_id == segment.id)
        .order_by(VideoProductionAsset.asset_type.asc(), VideoProductionAsset.version.desc())
        .limit(history_limit * 2)
        .all()
    )
    latest = {}
    history = {"image": [], "video_segment": []}
    for asset in assets:
        if asset.asset_type in history:
            history[asset.asset_type].append(_asset_payload(asset))
        if asset.is_latest and asset.asset_type not in latest:
            latest[asset.asset_type] = _asset_payload(asset)
    reviews = db.query(VideoReviewRecord).filter(VideoReviewRecord.production_segment_id == segment.id).order_by(VideoReviewRecord.created_at.desc()).limit(history_limit).all()
    return {
        "segment": {
            "id": segment.id,
            "segment_id": segment.segment_id,
            "status": segment.status,
            "version": segment.version,
            "duration_seconds": segment.duration_seconds,
            "continuity_mode": segment.continuity_mode,
            "image_prompt": segment.image_prompt,
            "video_prompt": segment.video_prompt,
            "narration": segment.narration,
            "reference_roles": segment.reference_roles_json or [],
        },
        "path": {"plan_id": episode.plan_id, "episode_plan_id": episode.id, "scene_id": scene.id, "shot_id": shot.id},
        "latest_assets": {"image": latest.get("image"), "video_segment": latest.get("video_segment")},
        "asset_history": history,
        "reviews": [{"id": row.id, "status": row.status, "review_type": row.review_type, "asset_version": row.asset_version} for row in reviews],
        "allowed_actions": ["retry"] if segment.status in {"failed", "failed_retryable", "retry_queued"} else [],
        "repair": None,
    }
```

- [ ] **Step 4: Add retry impact service**

Create `server/app/services/production_retry_service.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionSegment, VideoProductionAsset


def get_retry_impact(db: Session, segment_id: str) -> dict:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not segment:
        raise ValueError("Production segment not found")
    downstream = db.query(ProductionSegment).filter(ProductionSegment.previous_segment_id == segment.id).all()
    old_latest = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.production_segment_id == segment.id,
        VideoProductionAsset.is_latest.is_(True),
    ).all()
    allowed = segment.status in {"failed", "failed_retryable", "retry_queued"}
    return {
        "current_segment_version": segment.version,
        "target_new_version": segment.version + 1,
        "affected_downstream_segments": [{"id": item.id, "segment_id": item.segment_id, "continuity_mode": item.continuity_mode} for item in downstream],
        "old_latest_assets": [{"id": item.id, "asset_type": item.asset_type, "version": item.version} for item in old_latest],
        "estimated_extra_cost": 0.0,
        "estimate_status": "unknown",
        "unknown_estimate_reasons": ["pricing metadata unavailable"],
        "allowed": allowed,
    }
```

- [ ] **Step 5: Add costs summary service**

Create `server/app/services/production_cost_summary_service.py`:

```python
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db_models import ProductionCostEvent, VideoProductionRun


def get_run_costs(db: Session, run_id: str) -> dict:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    plan_id = run.production_plan_id
    if not plan_id:
        return {"actual_cost": 0.0, "estimated_remaining_cost": 0.0, "estimate_status": "unknown", "unknown_estimate_reasons": ["run is not linked"], "by_stage": [], "by_provider_model": [], "budget_status": "ok"}
    actual = db.query(func.coalesce(func.sum(ProductionCostEvent.actual_cost), 0.0)).filter(ProductionCostEvent.plan_id == plan_id).scalar()
    by_stage = db.query(ProductionCostEvent.stage, func.sum(ProductionCostEvent.actual_cost)).filter(ProductionCostEvent.plan_id == plan_id).group_by(ProductionCostEvent.stage).all()
    by_provider = db.query(ProductionCostEvent.provider, ProductionCostEvent.model_name, func.sum(ProductionCostEvent.actual_cost)).filter(ProductionCostEvent.plan_id == plan_id).group_by(ProductionCostEvent.provider, ProductionCostEvent.model_name).all()
    return {
        "actual_cost": float(actual or 0.0),
        "estimated_remaining_cost": 0.0,
        "estimate_status": "unknown",
        "unknown_estimate_reasons": ["pricing metadata unavailable"],
        "by_stage": [{"stage": stage, "actual_cost": float(cost or 0.0)} for stage, cost in by_stage],
        "by_provider_model": [{"provider": provider, "model_name": model, "actual_cost": float(cost or 0.0)} for provider, model, cost in by_provider],
        "budget_status": "ok",
    }
```

- [ ] **Step 6: Add router endpoints and frontend clients**

In `server/app/routers/video_production.py`, add:

```python
@router.get("/runs/{run_id}/costs")
def run_costs(run_id: str, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_cost_summary_service import get_run_costs
    try:
        return {"ok": True, **get_run_costs(db, run_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/segments/{segment_id}/detail")
def segment_detail(segment_id: str, history_limit: int = 10, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_segment_detail_service import get_segment_detail
    try:
        return {"ok": True, **get_segment_detail(db, segment_id, history_limit)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/segments/{segment_id}/retry-impact")
def segment_retry_impact(segment_id: str, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_retry_service import get_retry_impact
    try:
        return {"ok": True, **get_retry_impact(db, segment_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
```

In `web/src/api/videoProduction.js`, add:

```javascript
export function getRunCosts(runId) {
  return client.get(`/video-production/runs/${runId}/costs`)
}

export function getSegmentDetail(segmentId, params = {}) {
  return client.get(`/video-production/segments/${segmentId}/detail`, { params })
}

export function getSegmentRetryImpact(segmentId) {
  return client.get(`/video-production/segments/${segmentId}/retry-impact`)
}
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd server
pytest tests/test_video_production_segment_detail_api.py tests/test_video_production_costs_api.py tests/test_video_production_retry_impact.py -v
cd ..\web
npx vitest run src/__tests__/api-clients.test.js
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/app/services/production_segment_detail_service.py server/app/services/production_retry_service.py server/app/services/production_cost_summary_service.py server/app/routers/video_production.py web/src/api/videoProduction.js server/tests/test_video_production_segment_detail_api.py server/tests/test_video_production_costs_api.py server/tests/test_video_production_retry_impact.py
git commit -m "feat: add production segment detail and cost APIs"
```

### Task 6: Pause, Resume, Retry Mutation, And Status Aggregation

**Files:**
- Create: `server/app/services/production_status_aggregation.py`
- Modify: `server/app/services/production_queue_service.py`
- Modify: `server/app/services/production_retry_service.py`
- Modify: `server/app/services/production_segment_service.py`
- Modify: `server/app/routers/video_production.py`
- Test: `server/tests/test_video_production_pause_resume.py`
- Test: `server/tests/test_video_production_retry_impact.py`

- [ ] **Step 1: Write failing pause/resume tests**

Add tests that create queued and retry-wait `ProductionJob` rows, call:

```python
client.post(f"/api/video-production/runs/{run.id}/pause")
client.post(f"/api/video-production/runs/{run.id}/resume")
```

Assert:

```python
assert blocked_job.status == "blocked"
assert blocked_job.resume_status == "queued"
assert resumed_job.status == "queued"
assert failed_terminal_job.status == "failed"
```

- [ ] **Step 2: Add aggregation service**

Create `server/app/services/production_status_aggregation.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionEpisode, ProductionPlan, ProductionScene, ProductionSegment, ProductionShot


def _parent_status(child_statuses: list[str]) -> str:
    if not child_statuses:
        return "planned"
    if any(status in {"failed_terminal"} for status in child_statuses):
        return "failed_terminal"
    if any(status in {"failed", "failed_retryable"} for status in child_statuses):
        return "failed_retryable"
    if any(status in {"image_running", "video_running", "composing"} for status in child_statuses):
        return "running"
    if any(status in {"image_review_pending", "video_review_pending", "blocked_by_review"} for status in child_statuses):
        return "blocked_by_review"
    if all(status == "completed" for status in child_statuses):
        return "completed"
    if all(status == "paused" for status in child_statuses):
        return "paused"
    return "running"


def recompute_from_segment(db: Session, segment_id: str) -> None:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not segment:
        return
    shot = db.query(ProductionShot).filter(ProductionShot.id == segment.shot_plan_id).one()
    shot.status = _parent_status([row.status for row in db.query(ProductionSegment).filter(ProductionSegment.shot_plan_id == shot.id).all()])
    scene = db.query(ProductionScene).filter(ProductionScene.id == shot.scene_plan_id).one()
    scene.status = _parent_status([row.status for row in db.query(ProductionShot).filter(ProductionShot.scene_plan_id == scene.id).all()])
    episode = db.query(ProductionEpisode).filter(ProductionEpisode.id == scene.episode_plan_id).one()
    episode.status = _parent_status([row.status for row in db.query(ProductionScene).filter(ProductionScene.episode_plan_id == episode.id).all()])
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == episode.plan_id).one()
    plan.status = _parent_status([row.status for row in db.query(ProductionEpisode).filter(ProductionEpisode.plan_id == plan.id).all()])
    db.commit()
```

- [ ] **Step 3: Implement pause/resume helpers**

In `server/app/services/production_queue_service.py`, update `pause_plan_jobs()`:

```python
def pause_plan_jobs(db: Session, plan_id: str, reason: str) -> int:
    now = bj_now()
    jobs = db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]),
    ).all()
    for job in jobs:
        job.resume_status = job.status
        job.status = JOB_BLOCKED
        job.blocked_reason = reason
        job.error_code = reason
        job.paused_at = now
        job.updated_at = now
    db.commit()
    return len(jobs)


def resume_plan_jobs(db: Session, plan_id: str) -> int:
    now = bj_now()
    jobs = db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.status == JOB_BLOCKED,
        ProductionJob.resume_status.isnot(None),
    ).all()
    for job in jobs:
        job.status = job.resume_status
        job.resume_status = None
        job.blocked_reason = None
        job.paused_at = None
        job.updated_at = now
    db.commit()
    return len(jobs)
```

- [ ] **Step 4: Add run-level controls**

In `server/app/routers/video_production.py`, add:

```python
@router.post("/runs/{run_id}/pause")
def pause_run(run_id: str, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_queue_service import pause_plan_jobs
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run or not run.production_plan_id:
        raise HTTPException(404, "Linked run not found")
    count = pause_plan_jobs(db, run.production_plan_id, "PAUSED_BY_OPERATOR")
    run.status = "paused"
    db.commit()
    return {"ok": True, "paused_jobs": count, "run": _run_payload(run)}


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: str, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_queue_service import resume_plan_jobs
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run or not run.production_plan_id:
        raise HTTPException(404, "Linked run not found")
    count = resume_plan_jobs(db, run.production_plan_id)
    run.status = "running"
    db.commit()
    return {"ok": True, "resumed_jobs": count, "run": _run_payload(run)}
```

- [ ] **Step 5: Make Segment retry use dry-run impact**

In `server/app/services/production_retry_service.py`, add:

```python
def retry_segment_with_impact(db: Session, segment_id: str) -> ProductionSegment:
    impact = get_retry_impact(db, segment_id)
    if not impact["allowed"]:
        raise ValueError("Production segment retry is not allowed")
    old = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).with_for_update().first()
    if not old:
        raise ValueError("Production segment not found")
    db.query(VideoProductionAsset).filter(
        VideoProductionAsset.production_segment_id == old.id,
        VideoProductionAsset.is_latest.is_(True),
    ).update({"is_latest": False}, synchronize_session=False)
    old.status = "superseded"
    new_segment = ProductionSegment(
        shot_plan_id=old.shot_plan_id,
        previous_segment_id=old.previous_segment_id,
        segment_id=old.segment_id,
        order_index=old.order_index,
        status="retry_queued",
        duration_seconds=old.duration_seconds,
        continuity_mode=old.continuity_mode,
        version=old.version + 1,
        previous_end_frame_url=old.previous_end_frame_url,
        expected_end_state=old.expected_end_state,
        retry_count=old.retry_count + 1,
        image_prompt=old.image_prompt,
        video_prompt=old.video_prompt,
        narration=old.narration,
        reference_roles_json=old.reference_roles_json or [],
    )
    db.add(new_segment)
    db.commit()
    db.refresh(new_segment)
    return new_segment
```

Update `production_segment_service.retry_segment()` to call `retry_segment_with_impact()`.

- [ ] **Step 6: Run tests**

Run:

```powershell
cd server
pytest tests/test_video_production_pause_resume.py tests/test_video_production_retry_impact.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/production_status_aggregation.py server/app/services/production_queue_service.py server/app/services/production_retry_service.py server/app/services/production_segment_service.py server/app/routers/video_production.py server/tests/test_video_production_pause_resume.py server/tests/test_video_production_retry_impact.py
git commit -m "feat: add production pause resume and retry impact"
```

### Task 7: Linked Stage Execution

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/video_production_state.py`
- Modify: `server/app/services/production_observability.py`
- Test: `server/tests/test_video_production_linked_stage_execution.py`
- Test: `server/tests/test_video_production_full_mocked_e2e.py`

- [ ] **Step 1: Write failing linked builder tests**

Add `server/tests/test_video_production_linked_stage_execution.py`:

```python
def _linked_run_with_segment(db):
    from app.db_models import (
        Episode,
        ProductionEpisode,
        ProductionPlan,
        ProductionScene,
        ProductionSegment,
        ProductionShot,
        Series,
        VideoProductionRun,
    )

    series = Series(title="Linked", logline="Linked", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-1",
        order_index=1,
        status="ready",
        character_ids=["hero"],
        action="hero looks at the city",
        shot_type="medium",
        duration_seconds=8,
    )
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status="planned",
        duration_seconds=8,
        continuity_mode="narrative_cut",
        version=1,
        image_prompt="hero on rooftop",
        video_prompt="slow push in",
        reference_roles_json=[{"role": "character_anchor", "url": "https://example.test/hero.png"}],
    )
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    return run, segment


def _legacy_run(db):
    from app.db_models import Episode, Series, VideoProductionRun

    series = Series(title="Legacy", logline="Legacy", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_link_status="legacy_unlinked",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "legacy prompt", "reference_urls": []}]},
    )
    db.add(run)
    db.flush()
    return run


def test_linked_run_image_frames_are_built_from_segments(db):
    from app.services.video_production_service import image_stage_frames

    run, segment = _linked_run_with_segment(db)
    frames = image_stage_frames(run, db=db)

    assert frames[0]["frame_id"] == segment.id
    assert frames[0]["production_segment_id"] == segment.id
    assert frames[0]["image_prompt"] == segment.image_prompt
    assert frames[0]["reference_urls"]


def test_legacy_run_image_frames_still_use_storyboard(db):
    from app.services.video_production_service import image_stage_frames

    run = _legacy_run(db)
    frames = image_stage_frames(run)

    assert frames[0]["frame_id"] == "frame-001"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_video_production_linked_stage_execution.py -v
```

Expected: FAIL because `image_stage_frames()` only accepts `run` and uses `storyboard_json`.

- [ ] **Step 3: Add linked/legacy helpers**

In `server/app/services/video_production_service.py`, change `image_stage_frames(run)` to:

```python
from sqlalchemy.orm import Session


def _is_linked_run(run: VideoProductionRun) -> bool:
    return bool(run.production_plan_id and run.production_episode_id and run.production_link_status == "linked")


def image_stage_frames(run: VideoProductionRun, db: Session | None = None) -> list[dict]:
    if _is_linked_run(run):
        if db is None:
            raise VideoProductionError("Linked production run requires a database session")
        return build_image_stage_frames_for_segments(db, run)
    frames = (run.storyboard_json or {}).get("frames") or []
    return [{
        "frame_id": _frame_id(frame, index),
        "image_prompt": frame.get("image_prompt", ""),
        "reference_urls": frame.get("reference_urls") or [],
        "style_constraints": {
            "character_ids": frame.get("character_ids") or [],
            "scene_id": frame.get("scene_id"),
            "continuity_notes": frame.get("continuity_notes", ""),
        },
        "duration": float(frame.get("duration") or 5),
    } for index, frame in enumerate(frames)]
```

Add:

```python
def build_image_stage_frames_for_segments(db: Session, run: VideoProductionRun) -> list[dict]:
    from app.db_models import ProductionScene, ProductionSegment, ProductionShot

    rows = (
        db.query(ProductionSegment)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == run.production_episode_id)
        .order_by(ProductionScene.order_index.asc(), ProductionShot.order_index.asc(), ProductionSegment.order_index.asc())
        .all()
    )
    return [{
        "frame_id": segment.id,
        "production_segment_id": segment.id,
        "image_prompt": segment.image_prompt,
        "video_prompt": segment.video_prompt,
        "narration": segment.narration or "",
        "reference_urls": [item.get("url") for item in (segment.reference_roles_json or []) if item.get("url")],
        "style_constraints": {
            "continuity_notes": segment.expected_end_state or "",
            "continuity_mode": segment.continuity_mode,
            "source_version": segment.version,
        },
        "duration": float(segment.duration_seconds or 5),
    } for segment in rows]
```

Update `start_image_stage()` to call `image_stage_frames(run, db=db)`. Existing legacy callers that use `image_stage_frames(run)` must continue to work.
Use the existing `VideoProductionError` class from this module for the missing-session guard.

- [ ] **Step 4: Add latest asset invariant helper**

In `server/app/services/video_production_service.py`, add:

```python
def _next_asset_version_for_target(db: Session, run_id: str, frame_id: str, asset_type: str, production_segment_id: str | None = None) -> int:
    query = db.query(VideoProductionAsset).filter(VideoProductionAsset.run_id == run_id, VideoProductionAsset.asset_type == asset_type)
    if production_segment_id:
        query = query.filter(VideoProductionAsset.production_segment_id == production_segment_id)
    else:
        query = query.filter(VideoProductionAsset.frame_id == frame_id)
    latest = query.order_by(VideoProductionAsset.version.desc()).first()
    return (latest.version + 1) if latest else 1


def _demote_latest_assets(db: Session, run_id: str, asset_type: str, production_segment_id: str | None = None, frame_id: str | None = None) -> None:
    query = db.query(VideoProductionAsset).filter(VideoProductionAsset.run_id == run_id, VideoProductionAsset.asset_type == asset_type, VideoProductionAsset.is_latest.is_(True))
    if production_segment_id:
        query = query.filter(VideoProductionAsset.production_segment_id == production_segment_id)
    elif frame_id:
        query = query.filter(VideoProductionAsset.frame_id == frame_id)
    query.update({"is_latest": False}, synchronize_session=False)
```

Use `_demote_latest_assets()` before inserting new linked assets in `mark_image_stage_assets()` and `mark_video_stage_assets()`.

For linked runs, asset insertion must copy Segment identity and version at write time:

```python
production_segment_id = item.get("production_segment_id")
if production_segment_id:
    _demote_latest_assets(db, run.id, "image", production_segment_id=production_segment_id)
    version = _next_asset_version_for_target(db, run.id, production_segment_id, "image", production_segment_id)
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=production_segment_id,
        asset_type="image",
        stage="image_generation",
        url=item.get("url", ""),
        local_path=item.get("local_path", ""),
        thumbnail_url=item.get("thumbnail_url", ""),
        version=version,
        metadata_json=item.get("metadata", {}),
        status="review_pending",
        pixelle_task_id=pixelle_task_id,
        provider_task_id=item.get("provider_task_id") or pixelle_task_id,
        production_segment_id=production_segment_id,
        target_type="production_segment",
        target_id=production_segment_id,
        source_version=item.get("source_version") or 1,
        is_latest=True,
    )
```

Use the same target/version copy pattern for linked `video_segment` assets in `mark_video_stage_assets()`. Legacy assets continue to use `frame_id` and `_next_asset_version()`.

- [ ] **Step 5: Add linked video and compose builders**

Add:

```python
def build_video_stage_frames_for_segments(db: Session, run: VideoProductionRun) -> list[dict]:
    image_assets = {
        asset.production_segment_id: asset
        for asset in db.query(VideoProductionAsset).filter(
            VideoProductionAsset.run_id == run.id,
            VideoProductionAsset.asset_type == "image",
            VideoProductionAsset.is_latest.is_(True),
            VideoProductionAsset.status == "approved",
        ).all()
    }
    frames = []
    for frame in build_image_stage_frames_for_segments(db, run):
        image = image_assets.get(frame["production_segment_id"])
        if not image:
            raise VideoProductionError(f"Approved image missing for segment {frame['production_segment_id']}")
        frames.append({
            "frame_id": frame["production_segment_id"],
            "production_segment_id": frame["production_segment_id"],
            "approved_image_url": image.url,
            "video_prompt": frame["video_prompt"],
            "reference_urls": frame["reference_urls"],
            "duration": frame["duration"],
            "audio_mode": "tts",
        })
    return frames


def build_compose_segments_for_production(db: Session, run: VideoProductionRun) -> list[dict]:
    video_assets = {
        asset.production_segment_id: asset
        for asset in db.query(VideoProductionAsset).filter(
            VideoProductionAsset.run_id == run.id,
            VideoProductionAsset.asset_type == "video_segment",
            VideoProductionAsset.is_latest.is_(True),
            VideoProductionAsset.status == "approved",
        ).all()
    }
    ordered_frames = build_image_stage_frames_for_segments(db, run)
    segments = []
    for frame in ordered_frames:
        asset = video_assets.get(frame["production_segment_id"])
        if not asset:
            raise VideoProductionError(f"Approved video segment missing for segment {frame['production_segment_id']}")
        segments.append({
            "frame_id": frame["production_segment_id"],
            "video_url": asset.url,
            "duration": float(asset.duration_seconds or frame["duration"]),
            "narration": frame["narration"],
        })
    return segments
```

Make `video_stage_frames()` and `compose_segments()` dispatch to these functions when `_is_linked_run(run)` is true.

- [ ] **Step 6: Run linked execution tests**

Run:

```powershell
cd server
pytest tests/test_video_production_linked_stage_execution.py tests/test_video_production_full_mocked_e2e.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/video_production_service.py server/app/services/video_production_state.py server/app/services/production_observability.py server/tests/test_video_production_linked_stage_execution.py server/tests/test_video_production_full_mocked_e2e.py
git commit -m "feat: execute linked runs from production segments"
```

### Task 8: Review Target Snapshots And Stale-Version Safety

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/production_review_service.py`
- Modify: `server/app/routers/video_production.py`
- Test: `server/tests/test_video_production_review_latest_version.py`
- Test: `server/tests/test_production_bulk_review.py`

- [ ] **Step 1: Write failing review snapshot assertions**

In `server/tests/test_video_production_review_latest_version.py`, add:

```python
def test_human_review_snapshots_asset_target_fields(db):
    from app.db_models import VideoReviewRecord
    from app.services.video_production_service import approve_asset

    asset = _linked_asset(db, version=2, is_latest=True)

    approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="ok")

    review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="human").one()
    assert review.target_type == asset.target_type
    assert review.target_id == asset.target_id
    assert review.production_segment_id == asset.production_segment_id
    assert review.asset_version == asset.version
    assert review.is_latest_asset_review is True


def test_stale_asset_approval_returns_named_conflict(db):
    old_asset = _linked_asset(db, version=1, is_latest=False)
    _linked_asset(db, run_id=old_asset.run_id, production_segment_id=old_asset.production_segment_id, version=2, is_latest=True)
    client = TestClient(app)

    resp = client.post(f"/api/video-production/assets/{old_asset.id}/review", json={"action": "approve"})

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "STALE_ASSET_VERSION"
```

Add `_linked_asset()` as a local helper in this test file that creates a real Series, Episode, ProductionPlan, ProductionEpisode, ProductionScene, ProductionShot, ProductionSegment, VideoProductionRun, and VideoProductionAsset with matching `target_type`, `target_id`, and `production_segment_id`.

- [ ] **Step 2: Add review snapshot helper**

In `server/app/services/video_production_service.py`, add:

```python
def _review_snapshot(asset: VideoProductionAsset) -> dict:
    return {
        "target_type": asset.target_type,
        "target_id": asset.target_id,
        "production_segment_id": asset.production_segment_id,
        "asset_version": asset.version,
        "is_latest_asset_review": bool(asset.is_latest),
    }
```

Use `**_review_snapshot(asset)` in every `VideoReviewRecord(...)` creation in this file.

- [ ] **Step 3: Convert stale approval to named error**

When stale approval is detected:

```python
raise ProductionRepairableError(
    code=ProductionErrorCode.STALE_ASSET_VERSION,
    message="A newer asset version exists. Reload before reviewing.",
    repair_action="Reload latest version",
    repair_route=f"/video-production/{asset.run_id}",
    retryable=True,
    affected_ids=[asset.id],
)
```

- [ ] **Step 4: Run review tests**

Run:

```powershell
cd server
pytest tests/test_video_production_review_latest_version.py tests/test_production_bulk_review.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/video_production_service.py server/app/services/production_review_service.py server/app/routers/video_production.py server/tests/test_video_production_review_latest_version.py server/tests/test_production_bulk_review.py
git commit -m "feat: snapshot production review targets"
```

### Task 9: Frontend API And One User-Facing Start Flow

**Files:**
- Modify: `web/src/api/director.js`
- Modify: `web/src/api/videoProduction.js`
- Modify: `web/src/views/SeriesDetailPage.vue`
- Test: `web/src/__tests__/api-clients.test.js`
- Test: `web/src/__tests__/series-detail-video-production.test.js`

- [ ] **Step 1: Write failing frontend tests**

In `web/src/__tests__/api-clients.test.js`, add:

```javascript
it('startEpisodeProduction calls POST /video-production/runs/start', async () => {
  const { startEpisodeProduction } = await import('../api/videoProduction.js')
  await startEpisodeProduction({ series_id: 'sid', episode_id: 'eid', target_duration_seconds: 60 })
  expect(client.post).toHaveBeenCalledWith('/video-production/runs/start', {
    series_id: 'sid',
    episode_id: 'eid',
    target_duration_seconds: 60,
    budget_limit: undefined,
    autostart_images: true,
  })
})
```

In `web/src/__tests__/series-detail-video-production.test.js`, assert the production button calls only `startEpisodeProduction()` and navigates to returned `route`.

- [ ] **Step 2: Add API clients**

In `web/src/api/director.js`, add:

```javascript
export function createEpisodePlan(payload) {
  return client.post('/director/episode-plan', payload)
}

export function createShotSegments(payload) {
  return client.post('/director/shot-segments', payload)
}
```

In `web/src/api/videoProduction.js`, add:

```javascript
export function startEpisodeProduction({ series_id, episode_id, target_duration_seconds, budget_limit, autostart_images = true }) {
  return client.post('/video-production/runs/start', {
    series_id,
    episode_id,
    target_duration_seconds,
    budget_limit,
    autostart_images,
  })
}

export function pauseProductionRun(runId) {
  return client.post(`/video-production/runs/${runId}/pause`)
}

export function resumeProductionRun(runId) {
  return client.post(`/video-production/runs/${runId}/resume`)
}
```

- [ ] **Step 3: Update Series detail start action**

In `web/src/views/SeriesDetailPage.vue`, replace manual `autoPlanEpisode() -> createVideoProductionRun() -> startImageStage()` sequencing with:

```javascript
import { startEpisodeProduction } from '../api/videoProduction.js'

async function startPipelineRun() {
  pipelineStarting.value = true
  error.value = ''
  try {
    const ep = nextEpisode()
    if (!ep) throw new Error('没有可启动的剧集')
    const { data } = await startEpisodeProduction({
      series_id: route.params.id,
      episode_id: ep.id,
      target_duration_seconds: series.value?.target_duration,
      autostart_images: true,
    })
    if (!data?.route) throw new Error('Production run was not created')
    router.push(data.route)
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value = detail?.message || detail || e.message || '启动失败'
  } finally {
    pipelineStarting.value = false
  }
}
```

- [ ] **Step 4: Run frontend API tests**

Run:

```powershell
cd web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add web/src/api/director.js web/src/api/videoProduction.js web/src/views/SeriesDetailPage.vue web/src/__tests__/api-clients.test.js web/src/__tests__/series-detail-video-production.test.js
git commit -m "feat: add one-click episode production start"
```

### Task 10: Operator Control Room UI

**Files:**
- Modify: `web/src/views/VideoProductionMonitorPage.vue`
- Modify: `web/src/api/videoProduction.js`
- Test: `web/src/__tests__/video-production-monitor-page.test.js`
- Test: `web/src/__tests__/production-control-room-autopilot.test.js`
- Test: `web/src/__tests__/production-control-room-empty-states.test.js`
- Test: `web/src/__tests__/production-control-room-a11y.test.js`
- Test: `web/src/__tests__/production-monitor-responsive.test.js`

- [ ] **Step 1: Write failing control room tests**

In `web/src/__tests__/video-production-monitor-page.test.js`, add:

```javascript
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import VideoProductionMonitorPage from '../views/VideoProductionMonitorPage.vue'

const mocks = vi.hoisted(() => ({
  getRun: vi.fn(),
  getRunTree: vi.fn(),
  getSegmentDetail: vi.fn(),
  getRunCosts: vi.fn(),
}))

vi.mock('../api/videoProduction.js', () => mocks)

it('renders operator control room from run summary and segment detail', async () => {
  mocks.getRun.mockResolvedValue({ data: { ok: true, run: { id: 'run-1', status: 'image_batch_running', current_stage: 'image_generation' } } })
  mocks.getRunTree.mockResolvedValue({ data: { ok: true, episodes: [{ scenes: [{ shots: [{ segments: [{ id: 'seg-1', segment_id: 'shot-1-seg-01', status: 'failed_retryable' }] }] }] }] } })
  mocks.getSegmentDetail.mockResolvedValue({ data: { ok: true, segment: { id: 'seg-1' }, latest_assets: {}, allowed_actions: ['retry'] } })
  mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })

  const wrapper = mount(VideoProductionMonitorPage, {
    global: { mocks: { $route: { params: { runId: 'run-1' } } } },
  })
  await flushPromises()

  expect(wrapper.text()).toContain('Run Health')
  expect(wrapper.text()).toContain('Exception Queue')
  expect(mocks.getSegmentDetail).toHaveBeenCalledWith('seg-1', { history_limit: 10 })
  expect(wrapper.find('[aria-live="polite"]').exists()).toBe(true)
  expect(wrapper.find('[data-test="mobile-action-bar"]').exists()).toBe(true)
})

it('keeps manual sync controls out of the primary happy path while provider work is running', async () => {
  mocks.getRun.mockResolvedValue({ data: { ok: true, run: { id: 'run-1', status: 'image_batch_running', current_stage: 'image_generation' } } })
  mocks.getRunTree.mockResolvedValue({ data: { ok: true, episodes: [] } })
  mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })

  const wrapper = mount(VideoProductionMonitorPage, {
    global: { mocks: { $route: { params: { runId: 'run-1' } } } },
  })
  await flushPromises()

  expect(wrapper.find('[data-test="primary-next-action"]').text()).not.toContain('Sync')
  expect(wrapper.find('[data-test="developer-sync-controls"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Add client functions**

Ensure `web/src/api/videoProduction.js` exports:

```javascript
export function getSegmentDetail(segmentId, params = {}) {
  return client.get(`/video-production/segments/${segmentId}/detail`, { params })
}

export function getSegmentRetryImpact(segmentId) {
  return client.get(`/video-production/segments/${segmentId}/retry-impact`)
}

export function getRunCosts(runId) {
  return client.get(`/video-production/runs/${runId}/costs`)
}
```

- [ ] **Step 3: Rebuild page state model**

In `VideoProductionMonitorPage.vue`, add refs:

```javascript
const segmentDetail = ref(null)
const segmentDetailLoading = ref(false)
const costs = ref(null)
const retryImpact = ref(null)
const retryDialogOpen = ref(false)
const mobileTreeOpen = ref(false)
```

Add selected-segment loader:

```javascript
async function selectSegment(segment) {
  selectedSegment.value = segment
  segmentDetailLoading.value = true
  try {
    const { data } = await getSegmentDetail(segment.id, { history_limit: 10 })
    segmentDetail.value = data
  } catch (e) {
    segmentDetail.value = { repair: normalizeError(e) }
  } finally {
    segmentDetailLoading.value = false
  }
}
```

Add normalized error helper:

```javascript
function normalizeError(e) {
  const detail = e.response?.data?.detail
  if (detail && typeof detail === 'object') return detail
  return {
    error_code: 'UNKNOWN',
    message: detail || e.message || 'Action failed',
    repair_action: 'Refresh',
    retryable: true,
    affected_ids: [],
  }
}
```

- [ ] **Step 4: Rebuild template around design contract**

Use these top-level areas:

```html
<section data-test="run-health-strip" aria-live="polite">...</section>
<section data-test="stage-timeline">...</section>
<section data-test="exception-queue">...</section>
<div data-test="control-room-grid">...</div>
<div data-test="mobile-action-bar">...</div>
```

Tree buttons must include:

```html
:aria-current="selectedSegment?.id === segment.id ? 'true' : undefined"
@keydown.enter.prevent="selectSegment(segment)"
@keydown.space.prevent="selectSegment(segment)"
```

The retry button opens impact first:

```javascript
async function previewRetryImpact() {
  if (!selectedSegment.value) return
  const { data } = await getSegmentRetryImpact(selectedSegment.value.id)
  retryImpact.value = data
  retryDialogOpen.value = true
}
```

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
cd web
npx vitest run src/__tests__/video-production-monitor-page.test.js src/__tests__/production-control-room-autopilot.test.js src/__tests__/production-control-room-empty-states.test.js src/__tests__/production-control-room-a11y.test.js src/__tests__/production-monitor-responsive.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/views/VideoProductionMonitorPage.vue web/src/api/videoProduction.js web/src/__tests__/video-production-monitor-page.test.js web/src/__tests__/production-control-room-autopilot.test.js web/src/__tests__/production-control-room-empty-states.test.js web/src/__tests__/production-control-room-a11y.test.js web/src/__tests__/production-monitor-responsive.test.js
git commit -m "feat: upgrade video production control room"
```

### Task 11: Mocked Episode E2E And Regression Gate

**Files:**
- Modify: `server/tests/test_video_production_full_mocked_e2e.py`
- Modify: `server/tests/test_series_style_lock_pipeline.py`
- Modify: `web/src/__tests__/review-bulk-actions.test.js`
- Modify: `web/src/__tests__/ai-video-review-page.test.js`

- [ ] **Step 1: Add mocked E2E assertions**

Extend `server/tests/test_video_production_full_mocked_e2e.py` so one test covers:

```python
POST /api/video-production/runs/start
POST /api/video-production/runs/{run_id}/sync-image-results
POST /api/video-production/reviews/bulk-action
POST /api/video-production/runs/{run_id}/start-videos
POST /api/video-production/runs/{run_id}/sync-video-results
POST /api/video-production/reviews/bulk-action
POST /api/video-production/runs/{run_id}/compose
POST /api/video-production/runs/{run_id}/sync-compose-results
```

Final assertions:

```python
assert episode.video_url
assert episode.status == "done"
assert run.production_link_status == "linked"
assert db.query(VideoProductionAsset).filter_by(is_latest=True).count() >= 1
assert db.query(ProductionAuditEvent).count() >= 5
```

- [ ] **Step 2: Run backend regression set**

Run:

```powershell
cd server
pytest tests/test_video_production_full_mocked_e2e.py tests/test_series_style_lock_pipeline.py tests/test_video_production_api.py tests/test_video_production_service.py tests/test_pixelle_stage_client.py -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend regression set**

Run:

```powershell
cd web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/video-production-monitor-page.test.js src/__tests__/ai-video-review-page.test.js src/__tests__/review-bulk-actions.test.js
```

Expected: PASS.

- [ ] **Step 4: Run full test suites when targeted tests pass**

Run:

```powershell
cd server
pytest
cd ..\web
npx vitest run
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/tests/test_video_production_full_mocked_e2e.py server/tests/test_series_style_lock_pipeline.py web/src/__tests__/review-bulk-actions.test.js web/src/__tests__/ai-video-review-page.test.js
git commit -m "test: cover linked production control plane e2e"
```

### Task 12: Final Documentation And Manual Smoke Checklist

**Files:**
- Modify: `docs/superpowers/specs/2026-05-26-video-production-control-plane-convergence-design.md`
- Create: `docs/superpowers/reports/2026-05-26-video-production-control-plane-stage1-verification.md`

- [ ] **Step 1: Create verification report**

Create `docs/superpowers/reports/2026-05-26-video-production-control-plane-stage1-verification.md`:

```markdown
# Video Production Control Plane Stage 1 Verification

## Automated Verification

- `cd server && pytest`
- `cd web && npx vitest run`

## Manual Local Smoke

1. Open a Series detail page.
2. Lock style.
3. Start episode production from one visible action.
4. Confirm navigation to `/video-production/{runId}`.
5. Confirm run health, stage timeline, exception queue, production tree, Segment detail, and action panel render.
6. Confirm a retryable failed Segment opens retry impact before mutation.
7. Confirm final compose writes `Episode.video_url`.

## Paid Provider Smoke

Paid provider smoke is manual. Use a short test episode and verify Ark Plan V3 endpoints remain `/api/plan/v3`.
```

- [ ] **Step 2: Update spec final status note**

Append to the spec under `GSTACK REVIEW REPORT`:

```markdown
### Stage 1 Implementation Plan

Implementation plan written:

`docs/superpowers/plans/2026-05-26-video-production-control-plane-stage1.md`

The implementation plan preserves Stage 1 scope and starts from the one user-facing start flow, named repairable errors, and production observability before frontend polish.
```

- [ ] **Step 3: Run final placeholder scan**

Run:

```powershell
$patterns = @(
  'T' + 'BD',
  'TO' + 'DO',
  'implement ' + 'later',
  'fill ' + 'in',
  'appropriate error ' + 'handling',
  'Write tests for ' + 'the above',
  'Similar ' + 'to'
)
foreach ($pattern in $patterns) {
  Select-String -Path docs/superpowers/plans/2026-05-26-video-production-control-plane-stage1.md -Pattern $pattern -SimpleMatch
}
```

Expected: no matches.

- [ ] **Step 4: Commit**

```powershell
git add docs/superpowers/plans/2026-05-26-video-production-control-plane-stage1.md docs/superpowers/specs/2026-05-26-video-production-control-plane-convergence-design.md docs/superpowers/reports/2026-05-26-video-production-control-plane-stage1-verification.md
git commit -m "docs: plan video production control plane stage 1"
```

## Final Verification Checklist

- [ ] Stage 1 starts from one user-facing production action.
- [ ] All blocking failures return named repairable errors.
- [ ] Linked runs store `production_plan_id`, `production_episode_id`, and `production_link_status`.
- [ ] Linked image/video/compose stages use `ProductionSegment`.
- [ ] Legacy unlinked runs remain compatible.
- [ ] Segment detail, retry impact, costs, pause, resume, and retry routes exist.
- [ ] Control room uses Segment detail instead of all-assets run payload.
- [ ] Mocked episode E2E reaches final write-back.
- [ ] Existing Pixelle stage client tests still pass.
- [ ] Existing review center tests still pass.

## Execution Handoff

Recommended execution mode: `superpowers:subagent-driven-development`.

Use one fresh worker per task, in numeric order. Review after each task before starting the next task because the plan crosses database migrations, backend service contracts, stage execution semantics, and frontend state. If execution must stay in this session, use `superpowers:executing-plans` and stop at each task commit checkpoint for verification.
