# Series-Scale Long Video Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a series-scale AI video production control plane that turns a locked series style and episode plan into inspectable, retryable, review-gated multi-shot video production.

**Architecture:** dy_auto is the orchestration and truth layer for plans, Segment queues, review gates, cost events, provenance, and video library records. Pixelle-Video remains the execution layer for image generation, image-to-video generation, last-frame continuation, and composition. Phase 1 proves the architecture on stable 3-8 minute episodes before scaling to 240+ minute collections.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, pytest, Vue 3, Vue Router, Vitest, Axios, Pixelle-Video FastAPI stage APIs, Volcengine Ark Plan V3 Seedream/Seedance models.

---

## Source Documents

- Reviewed design spec: `docs/superpowers/specs/2026-05-25-series-scale-long-video-production-design.md`
- Engineering test plan artifact: `C:\Users\HNXE\.gstack\projects\dy_auto\HNXE-feature-video-review-fixes-eng-review-test-plan-20260525-222431.md`
- Design wireframe artifact: `C:\Users\HNXE\.gstack\projects\dy_auto\designs\2026-05-25-series-production-control-room-wireframe.html`

## Scope

This is one master plan with phased, independently testable workstreams. The first usable milestone is a reliable 3-8 minute episode with persisted Segment rows, local retry, review gates, cost controls, and a tree-based production monitor. Long collections are built on the same tables and APIs after the episode wedge works.

## Success Criteria

- A locked series can create a persisted production plan with Episode, Scene, Shot, Segment, Job, Cost, and Collection rows.
- `Episode.storyboard_json` and `VideoProductionRun.storyboard_json` remain compatibility snapshots, not production truth.
- Every Segment has typed reference roles, continuity mode, retry version, provider task id, latest asset status, and review state.
- Queue jobs are idempotent, leased, retryable, resumable, and visible in the frontend.
- Continuous action segments use previous end frames; scene changes and montage segments do not accidentally force previous frames.
- Frontend shows a production tree, selected Segment preview, review/action panel, cost summary, failure reason, retry impact, and collection progress.
- Mocked backend E2E produces a multi-episode run, retries one Segment locally, approves reviews, composes episodes, and builds a collection.

## File Map

### dy_auto Backend

| File | Action | Responsibility |
|---|---|---|
| `server/app/db_models.py` | Modify | Add production plan, version, episode, scene, shot, segment, job, cost event, collection models; link assets/reviews to production targets. |
| `server/alembic/versions/c3d4e5f6a8b9_add_series_production_tables.py` | Create | Add production tables and indexes. |
| `server/app/services/production_status.py` | Create | Central status/stage/continuity constants. |
| `server/app/services/production_plan_service.py` | Create | Materialize plans from locked series and episode storyboard snapshots. |
| `server/app/services/production_queue_service.py` | Create | Enqueue, claim, lease, retry, pause, resume, and idempotency. |
| `server/app/services/production_segment_service.py` | Create | Segment state transitions, retry versioning, downstream impact. |
| `server/app/services/production_cost_service.py` | Create | Estimate/actual cost events and budget pause. |
| `server/app/services/pixelle_execution_service.py` | Create | Map Segment rows to Pixelle/Seedance stage payloads and normalize responses. |
| `server/app/services/production_review_service.py` | Create | AI/human review, bulk review, latest-version enforcement, gate recomputation. |
| `server/app/services/production_tree_service.py` | Create | Paginated production tree, node detail, latest review/cost summaries. |
| `server/app/services/production_collection_service.py` | Create | Build collections from approved episode videos and persist final collection assets. |
| `server/app/routers/director.py` | Modify | Add series/episode production planning endpoints while keeping `/api/director/auto-plan`. |
| `server/app/routers/video_production.py` | Modify | Add run tree, job, retry, bulk review, cost, pause/resume, and collection endpoints. |
| `server/app/services/pixelle_stage_client.py` | Modify | Pass typed reference roles, continuity mode, previous end frame, and model config snapshots. |
| `server/tests/*.py` | Create/Modify | Add unit, API, and mocked E2E coverage listed per task. |

### Pixelle-Video

| File | Action | Responsibility |
|---|---|---|
| `D:\devWorkspace\Pixelle-Video\api\schemas\video.py` | Modify | Add typed reference roles and continuity mode to stage frame schemas. |
| `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py` | Modify | Preserve per-segment provider metadata and last frame in responses. |
| `D:\devWorkspace\Pixelle-Video\api\routers\stages.py` | Modify | Apply mode-aware previous-end-frame handling. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_videos_api.py` | Modify/Create | Verify continuity modes and typed reference payload behavior. |

### dy_auto Frontend

| File | Action | Responsibility |
|---|---|---|
| `web/src/api/videoProduction.js` | Modify | Add tree, node detail, jobs, retry, bulk review, costs, collection APIs. |
| `web/src/views/VideoProductionMonitorPage.vue` | Replace/Refactor | Turn current stage strip into three-pane production control room. |
| `web/src/views/AIVideoReviewPage.vue` | Modify | Add bulk review, contextual review mode, latest-version conflict display. |
| `web/src/views/SeriesDetailPage.vue` | Modify | Add production plan/run entry and links to control room/collection builder. |
| `web/src/views/CollectionBuilderPage.vue` | Create | Show approved episodes, collection compose progress, final collection video. |
| `web/src/router/index.js` | Modify | Add collection builder route and admin path guard entry. |
| `web/src/__tests__/*.test.js` | Create/Modify | Add frontend tests listed per task. |

## Implementation Order

1. Data model and migration.
2. Status constants, queue, cost, and segment state services.
3. Plan materialization from locked style and storyboard.
4. Pixelle/Seedance continuity contract.
5. Worker/execution pipeline and review gates.
6. Backend APIs and tree query service.
7. Frontend API client and production control room.
8. Review center bulk actions and collection builder.
9. Mocked E2E, regression tests, and documentation sync.

## Task 1: Add Production Data Model and Migration

**Files:**

- Modify: `server/app/db_models.py`
- Create: `server/alembic/versions/c3d4e5f6a8b9_add_series_production_tables.py`
- Create: `server/tests/test_series_production_models.py`

- [ ] **Step 1: Write failing model smoke test**

Create `server/tests/test_series_production_models.py`:

```python
from app.db_models import (
    Episode,
    ProductionCostEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoCollection,
    VideoProductionAsset,
)


def test_series_production_model_graph_can_persist(db):
    series = Series(title="Long Show", logline="A test show", genre="drama", target_duration=300)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()

    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        target_total_duration_seconds=300,
        budget_limit=100.0,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()
    version = ProductionPlanVersion(
        plan_id=plan.id,
        version=1,
        style_lock_json={"locked": True, "version": 1},
        model_config_snapshot_json={"image_generation": {"model": "doubao-seedream-5.0-lite"}},
        prompt_policy_json={"continuity": "typed_reference_roles"},
    )
    db.add(version)
    prod_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=180,
    )
    db.add(prod_episode)
    db.flush()
    scene = ProductionScene(
        episode_plan_id=prod_episode.id,
        scene_id="scene-a",
        order_index=1,
        status="ready",
        location_summary="Night street",
    )
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-a",
        order_index=1,
        status="ready",
        character_ids=["char-a"],
        action="turns around",
        emotion="tense",
        shot_type="medium",
        duration_seconds=8,
    )
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-a",
        order_index=1,
        status="planned",
        duration_seconds=5,
        continuity_mode="continuous_action",
        version=1,
        reference_roles_json=[{"role": "character_anchor", "url": "https://cdn.test/char.png", "priority": 1}],
    )
    db.add(segment)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="segment",
        target_id=segment.id,
        stage="image_generation",
        status="queued",
        idempotency_key=f"{segment.id}:image_generation:v1",
    )
    db.add(job)
    asset = VideoProductionAsset(
        run_id="compat-run",
        episode_id=episode.id,
        frame_id="seg-a",
        asset_type="image",
        stage="image_generation",
        version=1,
        status="review_pending",
        production_segment_id=segment.id,
    )
    db.add(asset)
    cost = ProductionCostEvent(
        plan_id=plan.id,
        episode_plan_id=prod_episode.id,
        segment_id=segment.id,
        stage="image_generation",
        provider="seedance",
        model_name="doubao-seedream-5.0-lite",
        estimated_cost=0.2,
        actual_cost=0.0,
        currency="CNY",
        units_json={"images": 1},
    )
    db.add(cost)
    collection = VideoCollection(
        series_id=series.id,
        status="draft",
        included_episode_ids=[episode.id],
        duration_seconds=0,
    )
    db.add(collection)
    db.commit()

    assert db.query(ProductionPlan).filter_by(series_id=series.id).count() == 1
    assert db.query(ProductionSegment).filter_by(segment_id="seg-a").one().version == 1
    assert db.query(ProductionJob).filter_by(idempotency_key=f"{segment.id}:image_generation:v1").one().status == "queued"
    assert db.query(VideoProductionAsset).filter_by(production_segment_id=segment.id).one().frame_id == "seg-a"
    assert db.query(VideoCollection).filter_by(series_id=series.id).one().included_episode_ids == [episode.id]
```

- [ ] **Step 2: Run the model test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_series_production_models.py -q
```

Expected: FAIL with `ImportError` or missing class errors for `ProductionPlan`.

- [ ] **Step 3: Add ORM models**

Modify `server/app/db_models.py` after `VideoReviewRecord` or near existing video production models. Add these classes with the fields used by the test:

```python
class ProductionPlan(Base):
    __tablename__ = "production_plans"
    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="draft")
    target_total_duration_seconds = Column(Integer, nullable=False, default=0)
    budget_limit = Column(Float, nullable=True)
    current_cost = Column(Float, nullable=False, default=0.0)
    active_version = Column(Integer, nullable=False, default=1)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    __table_args__ = (
        Index("idx_production_plans_series_status", "series_id", "status"),
        Index("idx_production_plans_status_updated", "status", "updated_at"),
    )


class ProductionPlanVersion(Base):
    __tablename__ = "production_plan_versions"
    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    style_lock_json = Column(JSON, nullable=False, default=dict)
    model_config_snapshot_json = Column(JSON, nullable=False, default=dict)
    prompt_policy_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_production_plan_version"),
    )
```

Add the remaining classes with the exact column names from the test:

```python
class ProductionEpisode(Base):
    __tablename__ = "production_episodes"
    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    status = Column(String(40), nullable=False, default="planned")
    target_duration_seconds = Column(Integer, nullable=False, default=0)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    __table_args__ = (
        UniqueConstraint("plan_id", "episode_id", name="uq_production_episode_plan_episode"),
        Index("idx_production_episodes_plan_status", "plan_id", "status"),
        Index("idx_production_episodes_order", "plan_id", "order_index"),
    )


class ProductionScene(Base):
    __tablename__ = "production_scenes"
    id = Column(String(36), primary_key=True, default=_uuid)
    episode_plan_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="CASCADE"), nullable=False)
    scene_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False)
    status = Column(String(40), nullable=False, default="planned")
    location_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    __table_args__ = (
        Index("idx_production_scenes_episode_order", "episode_plan_id", "order_index"),
    )


class ProductionShot(Base):
    __tablename__ = "production_shots"
    id = Column(String(36), primary_key=True, default=_uuid)
    scene_plan_id = Column(String(36), ForeignKey("production_scenes.id", ondelete="CASCADE"), nullable=False)
    shot_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False)
    status = Column(String(40), nullable=False, default="planned")
    character_ids = Column(JSON, nullable=False, default=list)
    action = Column(Text, nullable=False, default="")
    emotion = Column(String(100), nullable=True)
    shot_type = Column(String(50), nullable=False, default="medium")
    duration_seconds = Column(Float, nullable=False, default=5.0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    __table_args__ = (
        Index("idx_production_shots_scene_order", "scene_plan_id", "order_index"),
    )


class ProductionSegment(Base):
    __tablename__ = "production_segments"
    id = Column(String(36), primary_key=True, default=_uuid)
    shot_plan_id = Column(String(36), ForeignKey("production_shots.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False)
    status = Column(String(40), nullable=False, default="planned")
    duration_seconds = Column(Float, nullable=False, default=5.0)
    continuity_mode = Column(String(40), nullable=False, default="narrative_cut")
    previous_segment_id = Column(String(36), ForeignKey("production_segments.id"), nullable=True)
    previous_end_frame_url = Column(Text, nullable=True)
    expected_end_state = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    retry_count = Column(Integer, nullable=False, default=0)
    reference_roles_json = Column(JSON, nullable=False, default=list)
    image_prompt = Column(Text, nullable=False, default="")
    video_prompt = Column(Text, nullable=False, default="")
    narration = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    __table_args__ = (
        UniqueConstraint("shot_plan_id", "segment_id", "version", name="uq_production_segment_version"),
        Index("idx_production_segments_shot_order", "shot_plan_id", "order_index"),
        Index("idx_production_segments_status_updated", "status", "updated_at"),
    )
```

Also add `ProductionJob`, `ProductionCostEvent`, `VideoCollection`, and nullable linkage columns on `VideoProductionAsset`:

```python
class ProductionJob(Base):
    __tablename__ = "production_jobs"
    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(36), nullable=False)
    stage = Column(String(40), nullable=False)
    status = Column(String(40), nullable=False, default="queued")
    idempotency_key = Column(String(200), nullable=False)
    provider_task_id = Column(String(120), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    retry_after = Column(DateTime, nullable=True)
    lease_id = Column(String(80), nullable=True)
    leased_until = Column(DateTime, nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    scheduled_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    retryable = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_production_jobs_idempotency"),
        Index("idx_production_jobs_claim", "status", "scheduled_at", "priority"),
        Index("idx_production_jobs_plan_status", "plan_id", "status"),
        Index("idx_production_jobs_target_stage", "target_type", "target_id", "stage"),
        Index("idx_production_jobs_lease", "lease_id", "leased_until"),
    )


class ProductionCostEvent(Base):
    __tablename__ = "production_cost_events"
    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    episode_plan_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    provider = Column(String(50), nullable=False)
    model_name = Column(String(120), nullable=False)
    model_config_id = Column(String(36), nullable=True)
    config_version = Column(Integer, nullable=False, default=1)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=False, default=dict)
    provider_task_id = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    __table_args__ = (
        Index("idx_production_cost_plan_stage", "plan_id", "stage"),
        Index("idx_production_cost_segment", "segment_id"),
    )


class VideoCollection(Base):
    __tablename__ = "video_collections"
    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(40), nullable=False, default="draft")
    included_episode_ids = Column(JSON, nullable=False, default=list)
    video_url = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    __table_args__ = (
        Index("idx_video_collections_series_status", "series_id", "status"),
    )
```

Add these columns to `VideoProductionAsset`:

```python
production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
target_type = Column(String(30), nullable=True)
target_id = Column(String(36), nullable=True)
provider_task_id = Column(String(120), nullable=True)
prompt_hash = Column(String(64), nullable=True)
```

- [ ] **Step 4: Create Alembic migration**

Create `server/alembic/versions/c3d4e5f6a8b9_add_series_production_tables.py` with matching `op.create_table`, `op.create_index`, and `op.add_column` operations. Use `down_revision = "b2c3d4e5f6a7"` unless a newer migration exists when implementation begins.

- [ ] **Step 5: Run model tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_series_production_models.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit data model baseline**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/db_models.py server/alembic/versions/c3d4e5f6a8b9_add_series_production_tables.py server/tests/test_series_production_models.py
git commit -m "feat: add series production data model"
```

## Task 2: Centralize Production Status and Queue Semantics

**Files:**

- Create: `server/app/services/production_status.py`
- Create: `server/app/services/production_queue_service.py`
- Create: `server/tests/test_production_queue_service.py`

- [ ] **Step 1: Write queue service tests**

Create `server/tests/test_production_queue_service.py`:

```python
from datetime import timedelta

from app.config import bj_now
from app.db_models import ProductionJob, ProductionPlan, Series
from app.services.production_queue_service import (
    claim_next_job,
    enqueue_job,
    fail_job,
    pause_plan_jobs,
    release_expired_leases,
)


def _plan(db):
    series = Series(title="Queue Show", logline="Queue test", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", target_total_duration_seconds=60)
    db.add(plan)
    db.commit()
    return plan


def test_enqueue_job_is_idempotent(db):
    plan = _plan(db)
    first = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    second = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    assert first.id == second.id
    assert db.query(ProductionJob).count() == 1


def test_claim_next_job_sets_lease(db):
    plan = _plan(db)
    enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    job = claim_next_job(db, lease_id="worker-a", lease_seconds=30)

    assert job is not None
    assert job.status == "leased"
    assert job.lease_id == "worker-a"
    assert job.leased_until is not None


def test_release_expired_leases_returns_job_to_queue(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = "leased"
    job.lease_id = "worker-a"
    job.leased_until = bj_now() - timedelta(seconds=5)
    db.commit()

    released = release_expired_leases(db)

    assert released == 1
    db.refresh(job)
    assert job.status == "queued"
    assert job.lease_id is None


def test_fail_job_retryable_moves_to_retry_wait(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    fail_job(db, job.id, "RATE_LIMIT", "provider rate limited", retryable=True, retry_after_seconds=60)

    db.refresh(job)
    assert job.status == "retry_wait"
    assert job.retry_after is not None
    assert job.attempt_count == 1


def test_pause_plan_jobs_blocks_queued_work(db):
    plan = _plan(db)
    enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    paused = pause_plan_jobs(db, plan.id, reason="budget_exceeded")

    assert paused == 1
    assert db.query(ProductionJob).one().status == "blocked"
```

- [ ] **Step 2: Run the queue tests and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_queue_service.py -q
```

Expected: FAIL because `production_queue_service.py` does not exist.

- [ ] **Step 3: Add status constants**

Create `server/app/services/production_status.py`:

```python
PLAN_DRAFT = "draft"
PLAN_READY = "ready"
PLAN_RUNNING = "running"
PLAN_PAUSED = "paused"
PLAN_BLOCKED = "blocked"
PLAN_COMPLETED = "completed"
PLAN_FAILED = "failed"
PLAN_CANCELLED = "cancelled"

JOB_QUEUED = "queued"
JOB_LEASED = "leased"
JOB_RUNNING = "running"
JOB_RETRY_WAIT = "retry_wait"
JOB_BLOCKED = "blocked"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

SEGMENT_PLANNED = "planned"
SEGMENT_IMAGE_QUEUED = "image_queued"
SEGMENT_IMAGE_RUNNING = "image_running"
SEGMENT_IMAGE_REVIEW_PENDING = "image_review_pending"
SEGMENT_IMAGE_APPROVED = "image_approved"
SEGMENT_VIDEO_QUEUED = "video_queued"
SEGMENT_VIDEO_RUNNING = "video_running"
SEGMENT_VIDEO_REVIEW_PENDING = "video_review_pending"
SEGMENT_VIDEO_APPROVED = "video_approved"
SEGMENT_COMPLETED = "completed"
SEGMENT_FAILED = "failed"
SEGMENT_RETRY_QUEUED = "retry_queued"
SEGMENT_SUPERSEDED = "superseded"

STAGE_IMAGE_GENERATION = "image_generation"
STAGE_IMAGE_AUDIT = "image_audit"
STAGE_VIDEO_GENERATION = "video_generation"
STAGE_VIDEO_AUDIT = "video_audit"
STAGE_EPISODE_COMPOSE = "episode_compose"
STAGE_COLLECTION_COMPOSE = "collection_compose"

CONTINUITY_CONTINUOUS_ACTION = "continuous_action"
CONTINUITY_NARRATIVE_CUT = "narrative_cut"
CONTINUITY_SCENE_CHANGE = "scene_change"
CONTINUITY_MONTAGE = "montage"

REFERENCE_CHARACTER_ANCHOR = "character_anchor"
REFERENCE_STYLE_ANCHOR = "style_anchor"
REFERENCE_SCENE_REFERENCE = "scene_reference"
REFERENCE_FIRST_FRAME = "first_frame"
REFERENCE_PREVIOUS_END_FRAME = "previous_end_frame"
```

- [ ] **Step 4: Add queue service implementation**

Create `server/app/services/production_queue_service.py`:

```python
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProductionJob
from app.services.production_status import JOB_BLOCKED, JOB_LEASED, JOB_QUEUED, JOB_RETRY_WAIT


def enqueue_job(
    db: Session,
    plan_id: str,
    target_type: str,
    target_id: str,
    stage: str,
    idempotency_key: str,
    priority: int = 100,
    max_attempts: int = 3,
) -> ProductionJob:
    existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
    if existing:
        return existing
    job = ProductionJob(
        plan_id=plan_id,
        target_type=target_type,
        target_id=target_id,
        stage=stage,
        status=JOB_QUEUED,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next_job(db: Session, lease_id: str, lease_seconds: int = 300) -> ProductionJob | None:
    now = bj_now()
    job = (
        db.query(ProductionJob)
        .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
        .filter((ProductionJob.retry_after.is_(None)) | (ProductionJob.retry_after <= now))
        .filter(ProductionJob.scheduled_at <= now)
        .order_by(ProductionJob.priority.asc(), ProductionJob.scheduled_at.asc(), ProductionJob.created_at.asc())
        .first()
    )
    if not job:
        return None
    updated = (
        db.query(ProductionJob)
        .filter(ProductionJob.id == job.id, ProductionJob.status == job.status)
        .update({
            "status": JOB_LEASED,
            "lease_id": lease_id,
            "leased_until": now + timedelta(seconds=lease_seconds),
            "updated_at": now,
        })
    )
    db.commit()
    if not updated:
        return None
    db.refresh(job)
    return job


def release_expired_leases(db: Session) -> int:
    now = bj_now()
    count = (
        db.query(ProductionJob)
        .filter(ProductionJob.status == JOB_LEASED, ProductionJob.leased_until < now)
        .update({"status": JOB_QUEUED, "lease_id": None, "leased_until": None, "updated_at": now})
    )
    db.commit()
    return count


def fail_job(db: Session, job_id: str, error_code: str, error_message: str, retryable: bool, retry_after_seconds: int = 60) -> ProductionJob:
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise ValueError("Production job not found")
    job.attempt_count += 1
    job.error_code = error_code
    job.error_message = error_message
    job.retryable = retryable
    if retryable and job.attempt_count < job.max_attempts:
        job.status = JOB_RETRY_WAIT
        job.retry_after = bj_now() + timedelta(seconds=retry_after_seconds)
    else:
        job.status = "failed"
        job.retry_after = None
    job.lease_id = None
    job.leased_until = None
    job.updated_at = bj_now()
    db.commit()
    db.refresh(job)
    return job


def pause_plan_jobs(db: Session, plan_id: str, reason: str) -> int:
    count = (
        db.query(ProductionJob)
        .filter(ProductionJob.plan_id == plan_id, ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
        .update({"status": JOB_BLOCKED, "error_code": reason, "updated_at": bj_now()})
    )
    db.commit()
    return count
```

- [ ] **Step 5: Run queue tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_queue_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit queue baseline**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/production_status.py server/app/services/production_queue_service.py server/tests/test_production_queue_service.py
git commit -m "feat: add durable production queue service"
```

## Task 3: Materialize Production Plans From Locked Series Style

**Files:**

- Create: `server/app/services/production_plan_service.py`
- Modify: `server/app/routers/director.py`
- Create: `server/tests/test_production_plan_service.py`
- Modify: `server/tests/test_series_style_lock_pipeline.py`

- [ ] **Step 1: Write plan materialization tests**

Create `server/tests/test_production_plan_service.py`:

```python
from app.db_models import Episode, ProductionEpisode, ProductionPlan, ProductionScene, ProductionSegment, ProductionShot, Series
from app.services.production_plan_service import create_episode_production_plan


def _locked_series(db):
    series = Series(
        title="Plan Show",
        logline="Test",
        genre="drama",
        story_bible_json={"style_lock": {"locked": True, "version": 1, "style_anchors": ["https://cdn.test/style.png"]}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [
                {
                    "frame_id": "frame-001",
                    "scene_id": "scene-a",
                    "character_ids": ["char-a"],
                    "image_prompt": "Hero stands in a blue-lit street",
                    "video_prompt": "Hero turns and walks forward",
                    "narration": "The city is quiet.",
                    "duration": 12,
                    "reference_urls": ["https://cdn.test/char.png"],
                    "continuity_notes": "continue the same action",
                    "audio_mode": "narration",
                }
            ]
        },
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_create_episode_production_plan_splits_long_frame_into_segments(db):
    series, episode = _locked_series(db)

    plan = create_episode_production_plan(db, series.id, episode.id, target_duration_seconds=12, budget_limit=20.0)

    assert db.query(ProductionPlan).filter_by(id=plan.id).one().status == "ready"
    assert db.query(ProductionEpisode).count() == 1
    assert db.query(ProductionScene).count() == 1
    assert db.query(ProductionShot).count() == 1
    segments = db.query(ProductionSegment).order_by(ProductionSegment.order_index).all()
    assert len(segments) == 2
    assert [segment.duration_seconds for segment in segments] == [6.0, 6.0]
    assert segments[0].continuity_mode == "continuous_action"
    assert segments[1].previous_segment_id == segments[0].id
    assert segments[0].reference_roles_json[0]["role"] == "character_anchor"


def test_create_episode_production_plan_requires_locked_style(db):
    series, episode = _locked_series(db)
    series.story_bible_json = {"style_lock": {"locked": False}}
    db.commit()

    try:
        create_episode_production_plan(db, series.id, episode.id, target_duration_seconds=12, budget_limit=20.0)
    except ValueError as exc:
        assert "style must be locked" in str(exc)
    else:
        raise AssertionError("Expected locked style validation error")
```

- [ ] **Step 2: Run the plan service tests and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_plan_service.py -q
```

Expected: FAIL because `production_plan_service.py` does not exist.

- [ ] **Step 3: Implement plan service**

Create `server/app/services/production_plan_service.py`:

```python
from math import ceil

from sqlalchemy.orm import Session

from app.db_models import Episode, ProductionEpisode, ProductionPlan, ProductionPlanVersion, ProductionScene, ProductionSegment, ProductionShot, Series
from app.services.production_status import CONTINUITY_CONTINUOUS_ACTION, REFERENCE_CHARACTER_ANCHOR, REFERENCE_STYLE_ANCHOR


def _style_lock(series: Series) -> dict:
    return (series.story_bible_json or {}).get("style_lock") or {}


def _segment_durations(duration: float, max_seconds: float = 8.0) -> list[float]:
    duration = float(duration or 5)
    count = max(1, ceil(duration / max_seconds))
    each = round(duration / count, 2)
    values = [each for _ in range(count)]
    values[-1] = round(duration - sum(values[:-1]), 2)
    return values


def _reference_roles(frame: dict, style_lock: dict) -> list[dict]:
    roles = []
    for index, url in enumerate(frame.get("reference_urls") or [], start=1):
        roles.append({"role": REFERENCE_CHARACTER_ANCHOR, "url": url, "priority": index})
    for index, url in enumerate(style_lock.get("style_anchors") or [], start=1):
        roles.append({"role": REFERENCE_STYLE_ANCHOR, "url": url, "priority": 100 + index})
    return roles


def create_episode_production_plan(
    db: Session,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
) -> ProductionPlan:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("Series not found")
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise ValueError("Episode not found")
    style_lock = _style_lock(series)
    if not style_lock.get("locked"):
        raise ValueError("Series style must be locked before production planning")

    frames = (episode.storyboard_json or {}).get("frames") or []
    if not frames:
        raise ValueError("Episode storyboard_json is empty")

    plan = ProductionPlan(
        series_id=series_id,
        status="ready",
        target_total_duration_seconds=int(target_duration_seconds or sum(float(frame.get("duration") or 5) for frame in frames)),
        budget_limit=budget_limit,
        current_cost=0.0,
        active_version=int(style_lock.get("version") or 1),
    )
    db.add(plan)
    db.flush()
    db.add(ProductionPlanVersion(
        plan_id=plan.id,
        version=plan.active_version,
        style_lock_json=style_lock,
        model_config_snapshot_json={},
        prompt_policy_json={"segment_max_seconds": 8, "reference_roles": True},
    ))
    prod_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=episode.episode_number,
        status="ready",
        target_duration_seconds=plan.target_total_duration_seconds,
    )
    db.add(prod_episode)
    db.flush()

    scene_by_id: dict[str, ProductionScene] = {}
    for frame_index, frame in enumerate(frames, start=1):
        scene_key = str(frame.get("scene_id") or "scene-default")
        if scene_key not in scene_by_id:
            scene = ProductionScene(
                episode_plan_id=prod_episode.id,
                scene_id=scene_key,
                order_index=len(scene_by_id) + 1,
                status="ready",
                location_summary=str(frame.get("scene_summary") or scene_key),
            )
            db.add(scene)
            db.flush()
            scene_by_id[scene_key] = scene
        shot = ProductionShot(
            scene_plan_id=scene_by_id[scene_key].id,
            shot_id=str(frame.get("frame_id") or f"shot-{frame_index:03d}"),
            order_index=frame_index,
            status="ready",
            character_ids=frame.get("character_ids") or [],
            action=str(frame.get("action") or frame.get("video_prompt") or ""),
            emotion=str(frame.get("emotion") or ""),
            shot_type=str(frame.get("shot_type") or "medium"),
            duration_seconds=float(frame.get("duration") or 5),
        )
        db.add(shot)
        db.flush()
        previous_segment = None
        chunks = _segment_durations(float(frame.get("duration") or 5))
        for segment_index, chunk_duration in enumerate(chunks, start=1):
            segment = ProductionSegment(
                shot_plan_id=shot.id,
                segment_id=f"{shot.shot_id}-seg-{segment_index:02d}",
                order_index=segment_index,
                status="planned",
                duration_seconds=chunk_duration,
                continuity_mode=CONTINUITY_CONTINUOUS_ACTION if len(chunks) > 1 else str(frame.get("continuity_mode") or "narrative_cut"),
                previous_segment_id=previous_segment.id if previous_segment else None,
                expected_end_state=str(frame.get("expected_end_state") or ""),
                version=1,
                reference_roles_json=_reference_roles(frame, style_lock),
                image_prompt=str(frame.get("image_prompt") or ""),
                video_prompt=str(frame.get("video_prompt") or ""),
                narration=frame.get("narration"),
            )
            db.add(segment)
            db.flush()
            previous_segment = segment
    db.commit()
    db.refresh(plan)
    return plan
```

- [ ] **Step 4: Add director endpoint**

Modify `server/app/routers/director.py`:

```python
class EpisodeProductionPlanRequest(BaseModel):
    series_id: str
    episode_id: str
    target_duration: int | None = None
    budget_limit: float | None = None


@router.post("/episode-production-plan")
def create_episode_production_plan_endpoint(body: EpisodeProductionPlanRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_plan_service import create_episode_production_plan

    try:
        plan = create_episode_production_plan(
            db,
            body.series_id,
            body.episode_id,
            target_duration_seconds=body.target_duration,
            budget_limit=body.budget_limit,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "plan": {"id": plan.id, "series_id": plan.series_id, "status": plan.status}}
```

- [ ] **Step 5: Run plan service tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_plan_service.py tests/test_series_style_lock_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit production plan service**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/production_plan_service.py server/app/routers/director.py server/tests/test_production_plan_service.py server/tests/test_series_style_lock_pipeline.py
git commit -m "feat: materialize episode production plans"
```

## Task 4: Add Segment Continuity and Pixelle Contract Mapping

**Files:**

- Modify: `server/app/services/pixelle_stage_client.py`
- Create: `server/app/services/pixelle_execution_service.py`
- Create: `server/tests/test_production_segment_continuity.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\schemas\video.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`
- Modify/Create: `D:\devWorkspace\Pixelle-Video\tests\test_stage_videos_api.py`

- [ ] **Step 1: Write dy_auto continuity mapping tests**

Create `server/tests/test_production_segment_continuity.py`:

```python
from app.services.pixelle_execution_service import build_video_stage_frame


def test_continuous_action_uses_previous_end_frame():
    frame = build_video_stage_frame({
        "segment_id": "seg-2",
        "duration_seconds": 5,
        "continuity_mode": "continuous_action",
        "previous_end_frame_url": "https://cdn.test/end.png",
        "reference_roles_json": [{"role": "character_anchor", "url": "https://cdn.test/char.png", "priority": 1}],
        "video_prompt": "continue walking",
    }, approved_image_url="https://cdn.test/start.png")

    assert frame["previous_end_frame_url"] == "https://cdn.test/end.png"
    assert any(item["role"] == "previous_end_frame" for item in frame["reference_roles"])


def test_scene_change_does_not_force_previous_end_frame():
    frame = build_video_stage_frame({
        "segment_id": "seg-3",
        "duration_seconds": 5,
        "continuity_mode": "scene_change",
        "previous_end_frame_url": "https://cdn.test/end.png",
        "reference_roles_json": [{"role": "style_anchor", "url": "https://cdn.test/style.png", "priority": 100}],
        "video_prompt": "new location",
    }, approved_image_url="https://cdn.test/start.png")

    assert frame["previous_end_frame_url"] == ""
    assert all(item["role"] != "previous_end_frame" for item in frame["reference_roles"])
```

- [ ] **Step 2: Run continuity tests and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_segment_continuity.py -q
```

Expected: FAIL because `pixelle_execution_service.py` does not exist.

- [ ] **Step 3: Add dy_auto Pixelle execution mapper**

Create `server/app/services/pixelle_execution_service.py`:

```python
from app.services.production_status import (
    CONTINUITY_CONTINUOUS_ACTION,
    CONTINUITY_NARRATIVE_CUT,
    REFERENCE_PREVIOUS_END_FRAME,
)


def build_video_stage_frame(segment: dict, approved_image_url: str) -> dict:
    continuity_mode = segment.get("continuity_mode") or CONTINUITY_NARRATIVE_CUT
    reference_roles = list(segment.get("reference_roles_json") or [])
    previous_end_frame_url = ""
    if continuity_mode == CONTINUITY_CONTINUOUS_ACTION and segment.get("previous_end_frame_url"):
        previous_end_frame_url = str(segment["previous_end_frame_url"])
        reference_roles.append({
            "role": REFERENCE_PREVIOUS_END_FRAME,
            "url": previous_end_frame_url,
            "priority": 10,
        })
    return {
        "frame_id": str(segment.get("segment_id")),
        "production_segment_id": str(segment.get("id") or segment.get("segment_id")),
        "continuity_mode": continuity_mode,
        "approved_image_url": approved_image_url,
        "previous_end_frame_url": previous_end_frame_url,
        "reference_roles": reference_roles,
        "reference_urls": [item["url"] for item in sorted(reference_roles, key=lambda item: item.get("priority", 100))],
        "duration": float(segment.get("duration_seconds") or 5),
        "video_prompt": str(segment.get("video_prompt") or ""),
        "audio_mode": str(segment.get("audio_mode") or "narration"),
        "return_last_frame": True,
    }
```

- [ ] **Step 4: Extend Pixelle schemas**

In `D:\devWorkspace\Pixelle-Video\api\schemas\video.py`, add:

```python
class ReferenceRole(BaseModel):
    role: str
    url: str
    character_id: str | None = None
    scene_id: str | None = None
    priority: int = 100
```

Add these fields to the video frame schema used by `/api/stages/videos/batch`:

```python
production_segment_id: str | None = None
continuity_mode: str = "narrative_cut"
previous_end_frame_url: str = ""
reference_roles: list[ReferenceRole] = Field(default_factory=list)
return_last_frame: bool = True
```

- [ ] **Step 5: Fix Pixelle previous-frame behavior**

Modify `D:\devWorkspace\Pixelle-Video\api\routers\stages.py` in `_run_video_batch`. Replace the blind append of `previous_end_frame_url` with:

```python
reference_urls = list(frame.reference_urls or [])
if frame.continuity_mode == "continuous_action":
    continuity_url = frame.previous_end_frame_url or previous_end_frame_url
    if continuity_url and continuity_url not in reference_urls:
        reference_urls.append(continuity_url)
elif frame.continuity_mode == "narrative_cut":
    continuity_url = frame.previous_end_frame_url or previous_end_frame_url
    if continuity_url and continuity_url not in reference_urls:
        reference_urls.append(continuity_url)
elif frame.continuity_mode in {"scene_change", "montage"}:
    reference_urls = [
        item.url for item in sorted(frame.reference_roles or [], key=lambda item: item.priority)
        if item.role in {"character_anchor", "style_anchor", "scene_reference"}
    ] or reference_urls
```

Keep writing `metadata["last_frame_url"]` from Seedance results.

- [ ] **Step 6: Run continuity contract tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_segment_continuity.py -q
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_videos_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit continuity contract**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/pixelle_execution_service.py server/app/services/pixelle_stage_client.py server/tests/test_production_segment_continuity.py
git commit -m "feat: add typed segment continuity mapping"

cd D:\devWorkspace\Pixelle-Video
git add api/schemas/video.py api/routers/stages.py tests/test_stage_videos_api.py
git commit -m "feat: honor typed video continuity modes"
```

## Task 5: Add Cost Events and Budget Pause

**Files:**

- Create: `server/app/services/production_cost_service.py`
- Create: `server/tests/test_production_cost_service.py`
- Modify: `server/app/services/production_queue_service.py`

- [ ] **Step 1: Write cost service tests**

Create `server/tests/test_production_cost_service.py`:

```python
from app.db_models import ProductionCostEvent, ProductionPlan, Series
from app.services.production_cost_service import assert_budget_available, record_cost_event


def _plan(db, budget=1.0):
    series = Series(title="Cost Show", logline="Cost test", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", target_total_duration_seconds=60, budget_limit=budget, current_cost=0.0)
    db.add(plan)
    db.commit()
    return plan


def test_record_cost_event_updates_plan_total(db):
    plan = _plan(db)

    event = record_cost_event(
        db,
        plan_id=plan.id,
        stage="image_generation",
        provider="seedance",
        model_name="doubao-seedream-5.0-lite",
        estimated_cost=0.2,
        actual_cost=0.3,
        currency="CNY",
        units_json={"images": 1},
    )

    db.refresh(plan)
    assert event.actual_cost == 0.3
    assert plan.current_cost == 0.3
    assert db.query(ProductionCostEvent).count() == 1


def test_assert_budget_available_blocks_overspend(db):
    plan = _plan(db, budget=0.1)

    try:
        assert_budget_available(db, plan.id, estimated_cost=0.2)
    except ValueError as exc:
        assert "budget exceeded" in str(exc)
    else:
        raise AssertionError("Expected budget exceeded")
```

- [ ] **Step 2: Run cost tests and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_cost_service.py -q
```

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement cost service**

Create `server/app/services/production_cost_service.py`:

```python
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProductionCostEvent, ProductionPlan


def assert_budget_available(db: Session, plan_id: str, estimated_cost: float) -> None:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")
    if plan.budget_limit is not None and (float(plan.current_cost or 0) + float(estimated_cost or 0)) > plan.budget_limit:
        raise ValueError("budget exceeded")


def record_cost_event(
    db: Session,
    plan_id: str,
    stage: str,
    provider: str,
    model_name: str,
    estimated_cost: float,
    actual_cost: float,
    currency: str,
    units_json: dict,
    episode_plan_id: str | None = None,
    segment_id: str | None = None,
    model_config_id: str | None = None,
    config_version: int = 1,
    provider_task_id: str | None = None,
) -> ProductionCostEvent:
    event = ProductionCostEvent(
        plan_id=plan_id,
        episode_plan_id=episode_plan_id,
        segment_id=segment_id,
        stage=stage,
        provider=provider,
        model_name=model_name,
        model_config_id=model_config_id,
        config_version=config_version,
        estimated_cost=float(estimated_cost or 0),
        actual_cost=float(actual_cost or 0),
        currency=currency,
        units_json=units_json or {},
        provider_task_id=provider_task_id,
    )
    db.add(event)
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if plan:
        plan.current_cost = float(plan.current_cost or 0) + event.actual_cost
        plan.updated_at = bj_now()
    db.commit()
    db.refresh(event)
    return event
```

- [ ] **Step 4: Run cost tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_cost_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit cost service**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/production_cost_service.py server/tests/test_production_cost_service.py
git commit -m "feat: add production cost ledger"
```

## Task 6: Add Segment Retry and Review Gate Services

**Files:**

- Create: `server/app/services/production_segment_service.py`
- Create: `server/app/services/production_review_service.py`
- Create: `server/tests/test_production_bulk_review.py`
- Modify: `server/app/services/video_production_state.py`

- [ ] **Step 1: Write review and retry tests**

Create `server/tests/test_production_bulk_review.py`:

```python
from app.db_models import Episode, ProductionSegment, ProductionShot, VideoProductionAsset, Series
from app.services.production_review_service import apply_bulk_review_action
from app.services.production_segment_service import retry_segment


def test_bulk_review_approves_latest_only(db):
    series = Series(title="Review Show", logline="Review", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    old = VideoProductionAsset(run_id="run-a", episode_id=episode.id, frame_id="seg-1", asset_type="image", stage="image_generation", version=1, status="review_pending")
    new = VideoProductionAsset(run_id="run-a", episode_id=episode.id, frame_id="seg-1", asset_type="image", stage="image_generation", version=2, status="review_pending")
    db.add_all([old, new])
    db.commit()

    result = apply_bulk_review_action(db, [old.id, new.id], action="approve", reviewer_user_id="user-a", comment="bulk approve")

    db.refresh(old)
    db.refresh(new)
    assert old.status == "review_pending"
    assert new.status == "approved"
    assert result["approved"] == 1
    assert result["skipped_stale"] == 1


def test_retry_segment_creates_new_version_and_marks_old_superseded(db):
    shot = ProductionShot(scene_plan_id="scene-plan", shot_id="shot-a", order_index=1, status="ready", character_ids=[], action="move", duration_seconds=5)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(shot_plan_id=shot.id, segment_id="seg-a", order_index=1, status="failed", duration_seconds=5, continuity_mode="continuous_action", version=1)
    db.add(segment)
    db.commit()

    new_segment = retry_segment(db, segment.id)

    db.refresh(segment)
    assert segment.status == "superseded"
    assert new_segment.version == 2
    assert new_segment.retry_count == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_bulk_review.py -q
```

Expected: FAIL because services do not exist.

- [ ] **Step 3: Implement segment retry service**

Create `server/app/services/production_segment_service.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionSegment
from app.services.production_status import SEGMENT_RETRY_QUEUED, SEGMENT_SUPERSEDED


def retry_segment(db: Session, segment_id: str) -> ProductionSegment:
    old = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not old:
        raise ValueError("Production segment not found")
    old.status = SEGMENT_SUPERSEDED
    new_segment = ProductionSegment(
        shot_plan_id=old.shot_plan_id,
        segment_id=old.segment_id,
        order_index=old.order_index,
        status=SEGMENT_RETRY_QUEUED,
        duration_seconds=old.duration_seconds,
        continuity_mode=old.continuity_mode,
        previous_segment_id=old.previous_segment_id,
        previous_end_frame_url=old.previous_end_frame_url,
        expected_end_state=old.expected_end_state,
        version=old.version + 1,
        retry_count=old.retry_count + 1,
        reference_roles_json=old.reference_roles_json or [],
        image_prompt=old.image_prompt,
        video_prompt=old.video_prompt,
        narration=old.narration,
    )
    db.add(new_segment)
    db.commit()
    db.refresh(new_segment)
    return new_segment
```

- [ ] **Step 4: Implement review service**

Create `server/app/services/production_review_service.py`:

```python
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import VideoProductionAsset, VideoReviewRecord


def _latest_asset(db: Session, asset: VideoProductionAsset) -> VideoProductionAsset:
    return (
        db.query(VideoProductionAsset)
        .filter(
            VideoProductionAsset.run_id == asset.run_id,
            VideoProductionAsset.frame_id == asset.frame_id,
            VideoProductionAsset.asset_type == asset.asset_type,
        )
        .order_by(VideoProductionAsset.version.desc())
        .first()
    )


def apply_bulk_review_action(db: Session, asset_ids: list[str], action: str, reviewer_user_id: str | None, comment: str = "") -> dict:
    approved = rejected = skipped_stale = 0
    for asset_id in asset_ids:
        asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
        if not asset:
            continue
        latest = _latest_asset(db, asset)
        if latest and latest.id != asset.id:
            skipped_stale += 1
            continue
        if action == "approve":
            asset.status = "approved"
            approved += 1
            review_status = "approved"
        elif action == "reject":
            asset.status = "rejected"
            rejected += 1
            review_status = "rejected"
        else:
            raise ValueError(f"Unsupported review action: {action}")
        db.add(VideoReviewRecord(
            asset_id=asset.id,
            run_id=asset.run_id,
            review_type="human",
            status=review_status,
            score=1.0 if review_status == "approved" else 0.0,
            issues_json=[] if review_status == "approved" else [comment or "Rejected by reviewer"],
            reviewer_user_id=reviewer_user_id,
            comment=comment,
        ))
        asset.updated_at = bj_now()
    db.commit()
    return {"approved": approved, "rejected": rejected, "skipped_stale": skipped_stale}
```

- [ ] **Step 5: Run review tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_bulk_review.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit review and retry services**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/production_segment_service.py server/app/services/production_review_service.py server/tests/test_production_bulk_review.py
git commit -m "feat: add production review and segment retry services"
```

## Task 7: Add Production Tree, Costs, Retry, and Bulk Review APIs

**Files:**

- Create: `server/app/services/production_tree_service.py`
- Modify: `server/app/routers/video_production.py`
- Create: `server/tests/test_video_production_tree_api.py`
- Modify: `server/tests/test_video_production_api.py`

- [ ] **Step 1: Write API tests**

Create `server/tests/test_video_production_tree_api.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, ProductionEpisode, ProductionPlan, ProductionScene, ProductionSegment, ProductionShot, Series
from app.main import app

client = TestClient(app)


def _tree_fixture(db):
    series = Series(title="Tree Show", logline="Tree", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", target_total_duration_seconds=60)
    db.add(plan)
    db.flush()
    pe = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="running", target_duration_seconds=60)
    db.add(pe)
    db.flush()
    scene = ProductionScene(episode_plan_id=pe.id, scene_id="scene-a", order_index=1, status="running")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-a", order_index=1, status="running", character_ids=["char-a"], action="move", duration_seconds=5)
    db.add(shot)
    db.flush()
    db.add(ProductionSegment(shot_plan_id=shot.id, segment_id="seg-a", order_index=1, status="video_review_pending", duration_seconds=5, continuity_mode="continuous_action"))
    db.commit()
    return plan


def test_run_tree_returns_paginated_hierarchy(db, admin_headers):
    plan = _tree_fixture(db)

    resp = client.get(f"/api/video-production/runs/{plan.id}/tree?page=1&page_size=50", headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["plan"]["id"] == plan.id
    assert body["page"] == 1
    assert body["total_segments"] == 1
    assert body["episodes"][0]["scenes"][0]["shots"][0]["segments"][0]["segment_id"] == "seg-a"
```

- [ ] **Step 2: Run API test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_tree_api.py -q
```

Expected: FAIL with 404 for `/api/video-production/runs/{plan_id}/tree`.

- [ ] **Step 3: Implement tree service**

Create `server/app/services/production_tree_service.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionEpisode, ProductionPlan, ProductionScene, ProductionSegment, ProductionShot


def get_run_tree(db: Session, plan_id: str, page: int = 1, page_size: int = 50, status: str | None = None) -> dict:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")
    segment_query = db.query(ProductionSegment)
    if status:
        segment_query = segment_query.filter(ProductionSegment.status == status)
    total_segments = segment_query.count()

    episodes_payload = []
    episodes = db.query(ProductionEpisode).filter(ProductionEpisode.plan_id == plan_id).order_by(ProductionEpisode.order_index).all()
    for episode in episodes:
        scenes_payload = []
        scenes = db.query(ProductionScene).filter(ProductionScene.episode_plan_id == episode.id).order_by(ProductionScene.order_index).all()
        for scene in scenes:
            shots_payload = []
            shots = db.query(ProductionShot).filter(ProductionShot.scene_plan_id == scene.id).order_by(ProductionShot.order_index).all()
            for shot in shots:
                segments = (
                    db.query(ProductionSegment)
                    .filter(ProductionSegment.shot_plan_id == shot.id)
                    .order_by(ProductionSegment.order_index)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )
                shots_payload.append({
                    "id": shot.id,
                    "shot_id": shot.shot_id,
                    "status": shot.status,
                    "segments": [{
                        "id": segment.id,
                        "segment_id": segment.segment_id,
                        "status": segment.status,
                        "duration_seconds": segment.duration_seconds,
                        "continuity_mode": segment.continuity_mode,
                        "version": segment.version,
                    } for segment in segments],
                })
            scenes_payload.append({"id": scene.id, "scene_id": scene.scene_id, "status": scene.status, "shots": shots_payload})
        episodes_payload.append({"id": episode.id, "episode_id": episode.episode_id, "status": episode.status, "scenes": scenes_payload})
    return {
        "plan": {"id": plan.id, "series_id": plan.series_id, "status": plan.status, "current_cost": plan.current_cost, "budget_limit": plan.budget_limit},
        "episodes": episodes_payload,
        "page": page,
        "page_size": page_size,
        "total_segments": total_segments,
    }
```

- [ ] **Step 4: Add routes**

Modify `server/app/routers/video_production.py`:

```python
from app.services.production_review_service import apply_bulk_review_action
from app.services.production_segment_service import retry_segment
from app.services.production_tree_service import get_run_tree


class BulkReviewRequest(BaseModel):
    asset_ids: list[str]
    action: str
    comment: str = ""


@router.get("/runs/{run_id}/tree")
def run_tree(run_id: str, page: int = 1, page_size: int = 50, status: str | None = None, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    try:
        payload = get_run_tree(db, run_id, page=page, page_size=min(page_size, 100), status=status)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {"ok": True, **payload}


@router.post("/segments/{segment_id}/retry")
def retry_production_segment(segment_id: str, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    try:
        segment = retry_segment(db, segment_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "segment": {"id": segment.id, "segment_id": segment.segment_id, "version": segment.version, "status": segment.status}}


@router.post("/reviews/bulk-action")
def bulk_review(body: BulkReviewRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    reviewer_id = user[0] if isinstance(user, tuple) else None
    try:
        result = apply_bulk_review_action(db, body.asset_ids, body.action, reviewer_id, body.comment)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "result": result}
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_tree_api.py tests/test_video_production_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit API layer**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/production_tree_service.py server/app/routers/video_production.py server/tests/test_video_production_tree_api.py server/tests/test_video_production_api.py
git commit -m "feat: add production tree and review APIs"
```

## Task 8: Add Collection Builder Backend

**Files:**

- Create: `server/app/services/production_collection_service.py`
- Modify: `server/app/routers/video_production.py`
- Create: `server/tests/test_collection_builder.py`

- [ ] **Step 1: Write collection tests**

Create `server/tests/test_collection_builder.py`:

```python
from app.db_models import Episode, GeneratedVideo, Series
from app.services.production_collection_service import create_collection_from_approved_episodes


def test_collection_includes_only_done_episodes(db):
    series = Series(title="Collection Show", logline="Collection", genre="drama")
    db.add(series)
    db.flush()
    done = Episode(series_id=series.id, episode_number=1, status="done", video_url="ep1.mp4", duration_seconds=60)
    pending = Episode(series_id=series.id, episode_number=2, status="pending", video_url=None)
    db.add_all([done, pending])
    db.commit()

    collection = create_collection_from_approved_episodes(db, series.id)

    assert collection.included_episode_ids == [done.id]
    assert collection.status == "draft"
    assert collection.duration_seconds == 60
```

- [ ] **Step 2: Run collection test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_collection_builder.py -q
```

Expected: FAIL because collection service does not exist.

- [ ] **Step 3: Implement collection service**

Create `server/app/services/production_collection_service.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import Episode, Series, VideoCollection


def create_collection_from_approved_episodes(db: Session, series_id: str) -> VideoCollection:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("Series not found")
    episodes = (
        db.query(Episode)
        .filter(Episode.series_id == series_id, Episode.status == "done", Episode.video_url.isnot(None))
        .order_by(Episode.episode_number)
        .all()
    )
    collection = VideoCollection(
        series_id=series_id,
        status="draft",
        included_episode_ids=[episode.id for episode in episodes],
        duration_seconds=sum(float(episode.duration_seconds or 0) for episode in episodes),
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection
```

- [ ] **Step 4: Add collection route**

Modify `server/app/routers/video_production.py`:

```python
class CreateCollectionRequest(BaseModel):
    series_id: str


@router.post("/collections")
def create_collection(body: CreateCollectionRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    from app.services.production_collection_service import create_collection_from_approved_episodes

    try:
        collection = create_collection_from_approved_episodes(db, body.series_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "ok": True,
        "collection": {
            "id": collection.id,
            "series_id": collection.series_id,
            "status": collection.status,
            "included_episode_ids": collection.included_episode_ids,
            "duration_seconds": collection.duration_seconds,
            "video_url": collection.video_url,
        },
    }
```

- [ ] **Step 5: Run collection tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_collection_builder.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit collection backend**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/production_collection_service.py server/app/routers/video_production.py server/tests/test_collection_builder.py
git commit -m "feat: add video collection builder backend"
```

## Task 9: Add Frontend API Client Coverage

**Files:**

- Modify: `web/src/api/videoProduction.js`
- Modify: `web/src/__tests__/api-clients.test.js`

- [ ] **Step 1: Add failing API client tests**

Append to `web/src/__tests__/api-clients.test.js`:

```javascript
it('video production tree helpers call production endpoints', async () => {
  const {
    getProductionTree,
    retryProductionSegment,
    bulkReviewProductionAssets,
    createVideoCollection,
  } = await import('../api/videoProduction.js')

  await getProductionTree('plan-1', { page: 2, status: 'failed' })
  expect(mockGet).toHaveBeenCalledWith('/video-production/runs/plan-1/tree', { params: { page: 2, status: 'failed' } })

  await retryProductionSegment('seg-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/segments/seg-1/retry')

  await bulkReviewProductionAssets({ asset_ids: ['a1'], action: 'approve', comment: 'ok' })
  expect(mockPost).toHaveBeenCalledWith('/video-production/reviews/bulk-action', { asset_ids: ['a1'], action: 'approve', comment: 'ok' })

  await createVideoCollection('series-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/collections', { series_id: 'series-1' })
})
```

- [ ] **Step 2: Run frontend client test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js
```

Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Add client helpers**

Modify `web/src/api/videoProduction.js`:

```javascript
export function getProductionTree(runId, params = {}) {
  return client.get(`/video-production/runs/${runId}/tree`, { params })
}

export function retryProductionSegment(segmentId) {
  return client.post(`/video-production/segments/${segmentId}/retry`)
}

export function bulkReviewProductionAssets(payload) {
  return client.post('/video-production/reviews/bulk-action', payload)
}

export function createVideoCollection(seriesId) {
  return client.post('/video-production/collections', { series_id: seriesId })
}
```

- [ ] **Step 4: Run frontend client test**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit frontend API client**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/api/videoProduction.js web/src/__tests__/api-clients.test.js
git commit -m "feat: add production control API client helpers"
```

## Task 10: Refactor Production Monitor Into Three-Pane Control Room

**Files:**

- Modify: `web/src/views/VideoProductionMonitorPage.vue`
- Create: `web/src/__tests__/production-tree-page.test.js`
- Create: `web/src/__tests__/production-monitor-responsive.test.js`

- [ ] **Step 1: Write production tree UI test**

Create `web/src/__tests__/production-tree-page.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { runId: 'plan-1' } },
  getProductionTree: vi.fn(),
  retryProductionSegment: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('../api/videoProduction.js', () => ({
  getProductionTree: mocks.getProductionTree,
  retryProductionSegment: mocks.retryProductionSegment,
}))

describe('VideoProductionMonitorPage production tree', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getProductionTree.mockResolvedValue({
      data: {
        ok: true,
        plan: { id: 'plan-1', status: 'running', current_cost: 4.2, budget_limit: 10 },
        page: 1,
        page_size: 50,
        total_segments: 1,
        episodes: [{
          id: 'pe-1',
          status: 'running',
          scenes: [{
            id: 'scene-1',
            scene_id: 'scene-a',
            status: 'running',
            shots: [{
              id: 'shot-1',
              shot_id: 'shot-a',
              status: 'running',
              segments: [{ id: 'seg-1', segment_id: 'seg-a', status: 'failed', continuity_mode: 'continuous_action', duration_seconds: 5, version: 1 }],
            }],
          }],
        }],
      },
    })
  })

  it('renders tree, selected segment preview, and retry action', async () => {
    const Page = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(Page)
    await flushPromises()

    expect(wrapper.text()).toContain('Production Run')
    expect(wrapper.text()).toContain('seg-a')
    expect(wrapper.text()).toContain('continuous_action')
    expect(wrapper.text()).toContain('Retry Segment')

    await wrapper.find('button[data-test="retry-segment"]').trigger('click')
    await flushPromises()
    expect(mocks.retryProductionSegment).toHaveBeenCalledWith('seg-1')
  })
})
```

- [ ] **Step 2: Run UI test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/production-tree-page.test.js
```

Expected: FAIL because current page uses old run/assets payload.

- [ ] **Step 3: Refactor monitor page**

Modify `web/src/views/VideoProductionMonitorPage.vue` to:

- load `getProductionTree(runId, { page, status })`
- render header with plan status, cost, total segment count
- render left production tree
- set `selectedSegment` to first segment by default
- render center preview with continuity mode, duration, version
- render right action panel with retry button and impact text

Use this data shape in script:

```javascript
const tree = ref(null)
const selectedSegment = ref(null)
const page = ref(1)
const statusFilter = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getProductionTree(runId, {
      page: page.value,
      status: statusFilter.value || undefined,
    })
    tree.value = data
    selectedSegment.value = firstSegment(data.episodes || [])
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load production tree'
  } finally {
    loading.value = false
  }
}

function firstSegment(episodes) {
  for (const episode of episodes) for (const scene of episode.scenes || []) for (const shot of scene.shots || []) {
    if ((shot.segments || []).length) return shot.segments[0]
  }
  return null
}

async function retrySelectedSegment() {
  if (!selectedSegment.value) return
  acting.value = true
  try {
    await retryProductionSegment(selectedSegment.value.id)
    await load()
  } finally {
    acting.value = false
  }
}
```

Ensure the retry button has `data-test="retry-segment"`.

- [ ] **Step 4: Run production monitor tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/production-tree-page.test.js src/__tests__/video-production-monitor-page.test.js
```

Expected: PASS. Update the old `video-production-monitor-page.test.js` assertions if they still expect only the legacy asset table.

- [ ] **Step 5: Commit production monitor UI**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/views/VideoProductionMonitorPage.vue web/src/__tests__/production-tree-page.test.js web/src/__tests__/production-monitor-responsive.test.js web/src/__tests__/video-production-monitor-page.test.js
git commit -m "feat: add production tree control room UI"
```

## Task 11: Add Bulk Review UX

**Files:**

- Modify: `web/src/views/AIVideoReviewPage.vue`
- Create: `web/src/__tests__/review-bulk-actions.test.js`

- [ ] **Step 1: Write bulk review UI test**

Create `web/src/__tests__/review-bulk-actions.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { query: { run_id: 'run-1' } },
  listReviewItems: vi.fn(),
  bulkReviewProductionAssets: vi.fn(() => Promise.resolve({ data: { ok: true, result: { approved: 2, skipped_stale: 0 } } })),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('../api/videoProduction.js', () => ({
  listReviewItems: mocks.listReviewItems,
  bulkReviewProductionAssets: mocks.bulkReviewProductionAssets,
  getVideoProductionRun: vi.fn(() => Promise.resolve({ data: { ok: true, run: { status: 'image_review_pending' } } })),
  reviewAsset: vi.fn(),
  startAssetRegeneration: vi.fn(),
  syncAssetRegeneration: vi.fn(),
  syncImageStage: vi.fn(),
}))

describe('AIVideoReviewPage bulk actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [
          { id: 'a1', frame_id: 'seg-1', version: 1, status: 'review_pending', stage: 'image_generation', asset_type: 'image', url: 'a.png' },
          { id: 'a2', frame_id: 'seg-2', version: 1, status: 'review_pending', stage: 'image_generation', asset_type: 'image', url: 'b.png' },
        ],
      },
    })
  })

  it('bulk approves selected assets after impact confirmation', async () => {
    const Page = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(Page)
    await flushPromises()

    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    await wrapper.find('button[data-test="bulk-approve"]').trigger('click')
    await flushPromises()

    expect(mocks.bulkReviewProductionAssets).toHaveBeenCalledWith({
      asset_ids: ['a1', 'a2'],
      action: 'approve',
      comment: 'Bulk approved from review center',
    })
  })
})
```

- [ ] **Step 2: Run bulk review test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/review-bulk-actions.test.js
```

Expected: FAIL because the view does not expose bulk selection/action controls.

- [ ] **Step 3: Add bulk selection controls**

Modify `web/src/views/AIVideoReviewPage.vue`:

- add `selectedIds = ref([])`
- add checkboxes for each review item
- add `Bulk approve` button with `data-test="bulk-approve"`
- call `bulkReviewProductionAssets({ asset_ids: selectedIds.value, action: 'approve', comment: 'Bulk approved from review center' })`
- reload the queue after success
- show skipped stale count if returned

- [ ] **Step 4: Run review tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/review-bulk-actions.test.js src/__tests__/ai-video-review-page.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit bulk review UX**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/views/AIVideoReviewPage.vue web/src/__tests__/review-bulk-actions.test.js web/src/__tests__/ai-video-review-page.test.js
git commit -m "feat: add bulk review controls"
```

## Task 12: Add Collection Builder Page

**Files:**

- Create: `web/src/views/CollectionBuilderPage.vue`
- Modify: `web/src/router/index.js`
- Create: `web/src/__tests__/collection-builder.test.js`
- Modify: `web/src/api/videoProduction.js`

- [ ] **Step 1: Write collection builder frontend test**

Create `web/src/__tests__/collection-builder.test.js`:

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { seriesId: 'series-1' } },
  createVideoCollection: vi.fn(() => Promise.resolve({ data: { ok: true, collection: { id: 'col-1', status: 'draft', included_episode_ids: ['ep-1'], duration_seconds: 60 } } })),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('../api/videoProduction.js', () => ({ createVideoCollection: mocks.createVideoCollection }))

describe('CollectionBuilderPage', () => {
  it('creates a collection from approved episodes', async () => {
    const Page = (await import('../views/CollectionBuilderPage.vue')).default
    const wrapper = mount(Page)

    await wrapper.find('button[data-test="create-collection"]').trigger('click')
    await flushPromises()

    expect(mocks.createVideoCollection).toHaveBeenCalledWith('series-1')
    expect(wrapper.text()).toContain('col-1')
    expect(wrapper.text()).toContain('60')
  })
})
```

- [ ] **Step 2: Run collection frontend test and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/collection-builder.test.js
```

Expected: FAIL because the page does not exist.

- [ ] **Step 3: Implement page and route**

Create `web/src/views/CollectionBuilderPage.vue`:

```vue
<template>
  <div class="p-6">
    <div class="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">Collection Builder</h1>
        <p class="text-slate-500 text-sm mt-1">Package approved episodes without blocking episode delivery.</p>
      </div>
      <button data-test="create-collection" @click="create" :disabled="acting" class="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">
        Create Collection
      </button>
    </div>

    <div v-if="error" class="text-red-400 py-6">{{ error }}</div>
    <div v-if="collection" class="rounded-lg border border-gray-700/50 p-4 bg-slate-900/50">
      <div class="text-slate-100 font-medium">Collection {{ collection.id }}</div>
      <div class="text-sm text-slate-400 mt-2">Status: {{ collection.status }}</div>
      <div class="text-sm text-slate-400 mt-1">Included episodes: {{ collection.included_episode_ids?.length || 0 }}</div>
      <div class="text-sm text-slate-400 mt-1">Duration: {{ collection.duration_seconds }}s</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { createVideoCollection } from '../api/videoProduction.js'

const route = useRoute()
const collection = ref(null)
const acting = ref(false)
const error = ref('')

async function create() {
  acting.value = true
  error.value = ''
  try {
    const { data } = await createVideoCollection(route.params.seriesId)
    collection.value = data.collection
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to create collection'
  } finally {
    acting.value = false
  }
}
</script>
```

Add route in `web/src/router/index.js`:

```javascript
{
  path: 'series/:seriesId/collection-builder',
  name: 'CollectionBuilder',
  component: () => import('../views/CollectionBuilderPage.vue'),
},
```

Add `'/collection-builder'` guard coverage by adding `'/series'` already covers this route through prefix.

- [ ] **Step 4: Run collection frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/collection-builder.test.js src/__tests__/navigation.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit collection frontend**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/views/CollectionBuilderPage.vue web/src/router/index.js web/src/__tests__/collection-builder.test.js
git commit -m "feat: add collection builder page"
```

## Task 13: Add Mocked Long-Video E2E

**Files:**

- Create: `server/tests/test_long_video_mocked_e2e.py`
- Modify: `server/tests/test_video_production_full_mocked_e2e.py`

- [ ] **Step 1: Write mocked multi-episode E2E**

Create `server/tests/test_long_video_mocked_e2e.py`:

```python
from app.db_models import Episode, GeneratedVideo, ProductionPlan, ProductionSegment, Series
from app.services.production_collection_service import create_collection_from_approved_episodes
from app.services.production_plan_service import create_episode_production_plan


def test_multi_episode_plan_retry_and_collection_mocked_e2e(db):
    series = Series(
        title="Mock Long Show",
        logline="Long form test",
        genre="drama",
        story_bible_json={"style_lock": {"locked": True, "version": 1, "style_anchors": ["https://cdn.test/style.png"]}},
    )
    db.add(series)
    db.flush()
    for episode_number in range(1, 4):
        db.add(Episode(
            series_id=series.id,
            episode_number=episode_number,
            title=f"Episode {episode_number}",
            storyboard_json={"frames": [{
                "frame_id": f"ep{episode_number}-frame-1",
                "scene_id": "scene-a",
                "character_ids": ["char-a"],
                "image_prompt": "consistent character",
                "video_prompt": "walk through scene",
                "duration": 12,
                "reference_urls": ["https://cdn.test/char.png"],
            }]},
        ))
    db.commit()

    episodes = db.query(Episode).order_by(Episode.episode_number).all()
    plans = [create_episode_production_plan(db, series.id, episode.id, target_duration_seconds=12, budget_limit=10.0) for episode in episodes]

    assert db.query(ProductionPlan).count() == 3
    assert db.query(ProductionSegment).count() == 6

    for episode in episodes:
        episode.status = "done"
        episode.video_url = f"episode-{episode.episode_number}.mp4"
        episode.duration_seconds = 12
        db.add(GeneratedVideo(keyword=series.title, title=episode.title, video_path=episode.video_url, duration=12, status="completed", pixelle_task_id=episode.id))
    db.commit()

    collection = create_collection_from_approved_episodes(db, series.id)

    assert len(collection.included_episode_ids) == 3
    assert collection.duration_seconds == 36
```

- [ ] **Step 2: Run E2E and verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_long_video_mocked_e2e.py -q
```

Expected: PASS if Tasks 1-8 are complete. Any failure identifies a missing integration from those tasks.

- [ ] **Step 3: Run full backend video production suite**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_series_production_models.py tests/test_production_plan_service.py tests/test_production_queue_service.py tests/test_production_segment_continuity.py tests/test_production_cost_service.py tests/test_production_bulk_review.py tests/test_video_production_tree_api.py tests/test_collection_builder.py tests/test_long_video_mocked_e2e.py tests/test_video_production_full_mocked_e2e.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit E2E coverage**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/tests/test_long_video_mocked_e2e.py server/tests/test_video_production_full_mocked_e2e.py
git commit -m "test: add mocked long video production e2e"
```

## Task 14: Final Verification and Documentation Sync

**Files:**

- Modify: `docs/superpowers/specs/2026-05-25-series-scale-long-video-production-design.md`
- Modify: `CLAUDE.md` only if commands or architecture guidance changed during implementation.

- [ ] **Step 1: Run backend targeted suite**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_series_style_lock_pipeline.py tests/test_series_production_models.py tests/test_production_plan_service.py tests/test_production_queue_service.py tests/test_production_segment_continuity.py tests/test_production_cost_service.py tests/test_production_bulk_review.py tests/test_video_production_tree_api.py tests/test_collection_builder.py tests/test_long_video_mocked_e2e.py tests/test_video_production_full_mocked_e2e.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend targeted suite**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/production-tree-page.test.js src/__tests__/review-bulk-actions.test.js src/__tests__/collection-builder.test.js src/__tests__/video-production-monitor-page.test.js src/__tests__/ai-video-review-page.test.js
```

Expected: PASS.

- [ ] **Step 3: Run Pixelle continuity suite**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_videos_api.py -q
```

Expected: PASS.

- [ ] **Step 4: Run static checks for the touched plan and code**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git diff --check
$patterns = @('T'+'BD', '待'+'定', '以后'+'再说', 'fill in'+' details', 'add'+' appropriate')
rg -n ($patterns -join '|') server/app server/tests web/src docs/superpowers/plans/2026-05-25-series-scale-long-video-production.md
```

Expected: `git diff --check` returns exit code 0. `rg` should return no matches in newly created implementation code and this plan.

- [ ] **Step 5: Commit final verification/doc sync**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add docs/superpowers/specs/2026-05-25-series-scale-long-video-production-design.md docs/superpowers/plans/2026-05-25-series-scale-long-video-production.md CLAUDE.md
git commit -m "docs: add series-scale production implementation plan"
```

## Parallel Execution Guidance

- Lane A: Task 1 first. No other task should start before the model baseline exists.
- Lane B: Tasks 2, 5, and 6 can run after Task 1, but coordinate service file names to avoid conflicts.
- Lane C: Task 4 can run after Task 1 and can be done in parallel with Lane B if one worker owns Pixelle files and one owns dy_auto services.
- Lane D: Tasks 7 and 8 depend on service contracts from Lanes B/C.
- Lane E: Tasks 9-12 depend on API contracts from Task 7.
- Lane F: Task 13 and Task 14 are final integration passes.

## Regression Guardrails

- Do not break existing `/api/director/auto-plan`.
- Do not remove current `VideoProductionRun` image/video/compose flow; keep it compatible while new `production_*` rows become the source of truth.
- Do not send API keys to frontend payloads or Pixelle task logs.
- Do not pass previous end frames for `scene_change` and `montage` segments.
- Do not return all assets for a long run in a single monitor endpoint.
- Do not let collection compose failure hide or invalidate completed Episode videos.

## Deferred Work

- Visual timeline editor.
- Douyin publishing.
- Multi-user approval roles.
- Full Celery/RQ distributed deployment. Phase 1 keeps a DB-backed worker abstraction that can migrate later.
- Rights management for generated assets.

## Self-Review Checklist

- Spec coverage: Data model, style lock inheritance, Segment queue, typed references, continuity modes, review gates, cost controls, frontend control room, collection builder, and tests are each mapped to tasks above.
- Placeholder scan: No unresolved placeholder wording is intentionally left in this document.
- Type consistency: `ProductionPlan`, `ProductionSegment`, `ProductionJob`, `ProductionCostEvent`, `VideoCollection`, and route helper names are used consistently across tasks.
- Execution readiness: Every task includes files, failing test, implementation direction, verification command, and commit command.
