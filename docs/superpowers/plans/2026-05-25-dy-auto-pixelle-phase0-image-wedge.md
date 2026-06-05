# dy_auto Pixelle Phase 0 Image Wedge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the safe first slice of dy_auto + Pixelle staged video production: Phase 0 trust/security/contracts plus the image generation, AI audit, human review, and single-image regeneration wedge.

**Architecture:** dy_auto remains the orchestration and truth layer: series, episode, storyboard, production runs, assets, review records, model config, review UI, and video library links. Pixelle-Video remains the execution layer and exposes explicit stage APIs that wrap its existing media services. The first implementation deliberately stops before image-to-video and final composition so the security, state-machine, review, and regeneration contracts are proven before the expensive stages.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic, httpx, pytest, Vue 3, Vue Router, Vitest, Pixelle-Video FastAPI task manager.

**Source Spec:** `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-25-dy-auto-pixelle-stage-gated-integration-design.md`

---

## Scope

This plan implements:

- Phase 0: trust, security, and contract gate.
- Phase 1: image-stage review wedge.
- Phase 2: single-image regeneration and latest-version gate.

This plan intentionally does not implement:

- Video segment stage.
- Final composition stage.
- Douyin publishing.
- Generic review center for non-video assets.
- Multi-user reviewer permissions.
- Real paid-provider E2E as a required automated test.

Those should be separate implementation plans after this wedge passes local mocked E2E.

## Repos

| Repo | Root | Role |
|---|---|---|
| dy_auto | `D:\devWorkspace\jsProjects\dy_auto` | Orchestration, DB truth, model config, audit gates, review UI. |
| Pixelle-Video | `D:\devWorkspace\Pixelle-Video` | Stage execution APIs and generated media serving. |

## File Map

### dy_auto Backend

| File | Action | Responsibility |
|---|---|---|
| `server/app/db_models.py` | Modify | Add `VideoProductionRun`, `VideoProductionAsset`, `VideoReviewRecord`. |
| `server/alembic/versions/9f1a2b3c4d5e_add_video_production_tables.py` | Create | Persist new production tables. |
| `server/tests/conftest.py` | Modify | Clean new tables in isolated tests. |
| `server/app/services/runtime_model_config.py` | Create | Resolve dy_auto `AIModel` rows into secret-safe runtime payloads. |
| `server/app/services/audit_gate.py` | Create | Convert audit responses/errors into gate statuses. |
| `server/app/services/pixelle_stage_client.py` | Create | Submit image stage requests to Pixelle and read stage task state. |
| `server/app/services/video_production_service.py` | Create | Own run creation, image submit, asset persistence, review, regeneration, and gate evaluation. |
| `server/app/routers/video_production.py` | Create | Thin API surface for production runs, review items, review actions, regeneration. |
| `server/app/routers/pipeline.py` | Modify | Preserve legacy start, add saved-storyboard compatibility, add run query routes. |
| `server/app/routers/audit.py` | Modify | Include gate status and never treat audit failures as approval. |
| `server/app/routers/pixelle.py` | Modify | Recursively redact all nested secrets. |
| `server/app/main.py` | Modify | Register `video_production.router`. |

### dy_auto Frontend

| File | Action | Responsibility |
|---|---|---|
| `web/src/api/videoProduction.js` | Create | Client functions for staged production and review center. |
| `web/src/views/AIVideoReviewPage.vue` | Create | Human review queue for image-stage exceptions. |
| `web/src/views/SeriesDetailPage.vue` | Modify | Start staged production and show image-review blocked link. |
| `web/src/views/PipelineMonitorPage.vue` | Modify | Show execution state and link to review center when blocked. |
| `web/src/router/index.js` | Modify | Add `/ai-video-review` route and admin guard. |
| `web/src/constants/navigation.js` | Modify | Add AI Video Review navigation item and route category. |

### Pixelle-Video

| File | Action | Responsibility |
|---|---|---|
| `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py` | Create | Stage request/response schemas. |
| `D:\devWorkspace\Pixelle-Video\api\routers\stages.py` | Create | `/api/stages/images/batch` and `/api/stages/tasks/{id}`. |
| `D:\devWorkspace\Pixelle-Video\api\routers\__init__.py` | Modify | Export `stages_router`. |
| `D:\devWorkspace\Pixelle-Video\api\app.py` | Modify | Include `stages_router`. |
| `D:\devWorkspace\Pixelle-Video\api\tasks\models.py` | Modify | Add `IMAGE_BATCH`, `VIDEO_BATCH`, `COMPOSE` task types. |
| `D:\devWorkspace\Pixelle-Video\api\middleware.py` | Modify | Require API key for `/api/stages/*` when runtime credentials are present. |
| `D:\devWorkspace\Pixelle-Video\api\routers\files.py` | Modify | Resolve paths before allowed-root checks. |

### Tests

| File | Action | Responsibility |
|---|---|---|
| `server/tests/test_video_production_models.py` | Create | Table/model invariants. |
| `server/tests/test_pipeline_saved_storyboard_compat.py` | Create | Current pipeline regression and run query routes. |
| `server/tests/test_pixelle_config_security.py` | Create | Recursive redaction. |
| `server/tests/test_audit_gate.py` | Create | Audit failure and low-confidence semantics. |
| `server/tests/test_runtime_model_config.py` | Create | Runtime config without leaked frontend secrets. |
| `server/tests/test_video_production_service.py` | Create | Image wedge state machine and latest-version invariant. |
| `server/tests/test_video_production_api.py` | Create | API endpoints and review flows. |
| `server/tests/test_video_production_mocked_e2e.py` | Create | Mocked local image-stage E2E. |
| `web/src/__tests__/api-clients.test.js` | Modify | Add video production API client tests. |
| `web/src/__tests__/ai-video-review-page.test.js` | Create | Review center states and actions. |
| `web/src/__tests__/series-detail-video-production.test.js` | Create | Series start path and blocked review link. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_api_auth.py` | Create | Stage API auth. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_images_api.py` | Create | Image stage API behavior. |
| `D:\devWorkspace\Pixelle-Video\tests\test_files_security.py` | Create | File path traversal regression. |

---

## Task 1: Add dy_auto Production Models

**Files:**
- Modify: `server/app/db_models.py`
- Create: `server/alembic/versions/9f1a2b3c4d5e_add_video_production_tables.py`
- Modify: `server/tests/conftest.py`
- Create: `server/tests/test_video_production_models.py`

- [ ] **Step 1: Write failing model tests**

Create `server/tests/test_video_production_models.py`:

```python
from app.db_models import (
    Episode,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)


def test_video_production_models_store_run_assets_and_reviews(db):
    series = Series(title="Stage Test", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()

    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_batch_running",
        current_stage="image_generation",
        storyboard_json={"frames": [{"frame_id": "frame-001"}]},
        model_trace_json={"image_generation": {"provider": "seedance"}},
    )
    db.add(run)
    db.flush()

    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/frame-001.png",
        version=1,
        status="review_pending",
        metadata_json={"width": 1080, "height": 1920},
    )
    db.add(asset)
    db.flush()

    review = VideoReviewRecord(
        asset_id=asset.id,
        run_id=run.id,
        review_type="ai",
        status="needs_human",
        score=0.42,
        issues_json=["identity mismatch"],
        model_trace_json={"provider": "audit-model"},
    )
    db.add(review)
    db.commit()

    saved = db.query(VideoProductionAsset).filter_by(frame_id="frame-001").one()
    assert saved.run_id == run.id
    assert saved.version == 1
    assert saved.status == "review_pending"
    assert db.query(VideoReviewRecord).filter_by(asset_id=saved.id).one().status == "needs_human"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_models.py -q
```

Expected: FAIL with `ImportError` or `cannot import name 'VideoProductionRun'`.

- [ ] **Step 3: Add SQLAlchemy models**

Append after `PipelineRun` in `server/app/db_models.py`:

```python
class VideoProductionRun(Base):
    """One staged automated production attempt for an episode."""
    __tablename__ = "video_production_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(40), nullable=False, default="draft")
    current_stage = Column(String(40), nullable=False, default="draft")
    pixelle_stage_task_id = Column(String(100), nullable=True)
    storyboard_json = Column(JSON, nullable=True, default=dict)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    edit_manifest_json = Column(JSON, nullable=True, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_production_runs_series_episode", "series_id", "episode_id"),
        Index("idx_video_production_runs_status", "status"),
    )


class VideoProductionAsset(Base):
    """Intermediate or final asset created by staged production."""
    __tablename__ = "video_production_assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    frame_id = Column(String(100), nullable=False)
    asset_type = Column(String(30), nullable=False)
    stage = Column(String(40), nullable=False)
    url = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(40), nullable=False, default="generated")
    pixelle_task_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_assets_run_stage", "run_id", "stage"),
        Index("idx_video_assets_run_frame", "run_id", "frame_id"),
        Index("idx_video_assets_status", "status"),
        UniqueConstraint("run_id", "frame_id", "asset_type", "version", name="uq_video_asset_version"),
    )


class VideoReviewRecord(Base):
    """AI or human review decision for a production asset."""
    __tablename__ = "video_review_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("video_production_assets.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    review_type = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False)
    score = Column(Float, nullable=True)
    criteria_json = Column(JSON, nullable=True, default=list)
    issues_json = Column(JSON, nullable=True, default=list)
    reviewer_user_id = Column(String(36), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_review_asset", "asset_id"),
        Index("idx_video_review_run", "run_id"),
        Index("idx_video_review_status", "status"),
    )
```

- [ ] **Step 4: Add Alembic migration**

Create `server/alembic/versions/9f1a2b3c4d5e_add_video_production_tables.py`:

```python
"""add_video_production_tables

Revision ID: 9f1a2b3c4d5e
Revises: 8e4f5d6a7b9c
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f1a2b3c4d5e"
down_revision: Union[str, Sequence[str], None] = "8e4f5d6a7b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_production_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_stage", sa.String(length=40), nullable=False),
        sa.Column("pixelle_stage_task_id", sa.String(length=100), nullable=True),
        sa.Column("storyboard_json", sa.JSON(), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("edit_manifest_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_video_production_runs_series_episode", "video_production_runs", ["series_id", "episode_id"])
    op.create_index("idx_video_production_runs_status", "video_production_runs", ["status"])

    op.create_table(
        "video_production_assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("frame_id", sa.String(length=100), nullable=False),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("pixelle_task_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_video_assets_run_stage", "video_production_assets", ["run_id", "stage"])
    op.create_index("idx_video_assets_run_frame", "video_production_assets", ["run_id", "frame_id"])
    op.create_index("idx_video_assets_status", "video_production_assets", ["status"])
    op.create_unique_constraint(
        "uq_video_asset_version",
        "video_production_assets",
        ["run_id", "frame_id", "asset_type", "version"],
    )

    op.create_table(
        "video_review_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("video_production_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("criteria_json", sa.JSON(), nullable=True),
        sa.Column("issues_json", sa.JSON(), nullable=True),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_video_review_asset", "video_review_records", ["asset_id"])
    op.create_index("idx_video_review_run", "video_review_records", ["run_id"])
    op.create_index("idx_video_review_status", "video_review_records", ["status"])


def downgrade() -> None:
    op.drop_index("idx_video_review_status", table_name="video_review_records")
    op.drop_index("idx_video_review_run", table_name="video_review_records")
    op.drop_index("idx_video_review_asset", table_name="video_review_records")
    op.drop_table("video_review_records")

    op.drop_constraint("uq_video_asset_version", "video_production_assets", type_="unique")
    op.drop_index("idx_video_assets_status", table_name="video_production_assets")
    op.drop_index("idx_video_assets_run_frame", table_name="video_production_assets")
    op.drop_index("idx_video_assets_run_stage", table_name="video_production_assets")
    op.drop_table("video_production_assets")

    op.drop_index("idx_video_production_runs_status", table_name="video_production_runs")
    op.drop_index("idx_video_production_runs_series_episode", table_name="video_production_runs")
    op.drop_table("video_production_runs")
```

- [ ] **Step 5: Update test cleanup imports and table order**

In `server/tests/conftest.py`, extend the import:

```python
from app.db_models import Base, Task, ChainInstance, DailyStats, Account, AccountGroup, AccountGroupMember, Channel, ChannelItem, Character, Scene, Series, Episode, PipelineRun, GeneratedVideo, AuditReport, ReferenceData, AIModel, User, VideoProductionRun, VideoProductionAsset, VideoReviewRecord, series_characters, series_scenes
```

Then update `_CLEANUP_TABLES` so review records are deleted before assets and runs:

```python
_CLEANUP_TABLES = [
    Task, DailyStats, AccountGroupMember, AccountGroup, ChainInstance,
    ChannelItem, Channel, ReferenceData, AIModel,
    VideoReviewRecord, VideoProductionAsset, VideoProductionRun,
    AuditReport, GeneratedVideo, PipelineRun, Episode,
]
```

- [ ] **Step 6: Run model tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_models.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/app/db_models.py server/alembic/versions/9f1a2b3c4d5e_add_video_production_tables.py server/tests/conftest.py server/tests/test_video_production_models.py
git commit -m "feat: add video production state models"
```

---

## Task 2: Fix Phase 0 Pipeline Compatibility and Run Query Routes

**Files:**
- Modify: `server/app/routers/pipeline.py`
- Create: `server/tests/test_pipeline_saved_storyboard_compat.py`

- [ ] **Step 1: Write failing compatibility tests**

Create `server/tests/test_pipeline_saved_storyboard_compat.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_models import Episode, PipelineRun, Series


client = TestClient(app)


def _series_with_storyboard(db):
    series = Series(
        title="Pipeline Compat",
        logline="Saved storyboard should start without director_plan.",
        genre="drama",
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "narration": "A clean opening.",
                "image_prompt": "A cinematic opening frame.",
                "duration": 5,
                "reference_urls": ["https://cdn.test/ref.png"],
            }]
        },
    )
    db.add(episode)
    db.commit()
    return series, episode


@pytest.mark.asyncio
async def test_pipeline_start_loads_saved_storyboard_when_director_plan_missing(db, monkeypatch):
    from app.routers import pipeline

    series, episode = _series_with_storyboard(db)
    captured = {}

    async def fake_submit_and_poll(payload, request_db):
        captured["payload"] = payload
        return {
            "task_id": "pixelle-task-1",
            "video_path": "output/final.mp4",
            "duration": 5,
        }

    monkeypatch.setattr(pipeline, "_submit_and_poll", fake_submit_and_poll)

    resp = client.post("/api/pipeline/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "director_plan": None,
    })

    assert resp.status_code == 200
    assert resp.json()["run_id"]
    assert captured["payload"]["frames"][0]["frame_id"] == "frame-001"
    assert captured["payload"]["frames"][0]["reference_urls"] == ["https://cdn.test/ref.png"]


def test_pipeline_run_lookup_routes_exist(db):
    series, episode = _series_with_storyboard(db)
    run = PipelineRun(
        series_id=series.id,
        episode_id=episode.id,
        mode="fully_automatic",
        status="running",
        current_layer=0,
        layers_json={"0": {"status": "queued"}},
    )
    db.add(run)
    db.commit()

    by_series = client.get(f"/api/pipeline/runs/{series.id}")
    by_pair = client.get(f"/api/pipeline/runs/{series.id}/{run.id}")
    by_id = client.get(f"/api/pipeline/runs/by-id/{run.id}")

    assert by_series.status_code == 200
    assert by_pair.status_code == 200
    assert by_id.status_code == 200
    assert by_id.json()["run"]["id"] == run.id
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pipeline_saved_storyboard_compat.py -q
```

Expected: FAIL because `director_plan is required` or run query routes are missing.

- [ ] **Step 3: Add helper functions to `pipeline.py`**

In `server/app/routers/pipeline.py`, change the import:

```python
from app.db_models import Episode, PipelineRun, GeneratedVideo
```

Add these helpers near `_build_storyboard_payload`:

```python
def _load_director_plan_from_episode(db: Session, series_id: str, episode_id: str | None) -> dict | None:
    if not episode_id:
        return None
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.series_id == series_id,
    ).first()
    if not episode:
        raise HTTPException(404, "Episode not found")
    storyboard = episode.storyboard_json or {}
    if not storyboard.get("frames"):
        raise HTTPException(400, "Episode storyboard_json is empty. Run /api/director/auto-plan first.")
    return storyboard


def _serialize_run(run: PipelineRun) -> dict:
    return {
        "id": run.id,
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "mode": run.mode,
        "model_ids": run.model_ids or {},
        "layers_json": run.layers_json or {},
        "current_layer": run.current_layer,
        "status": run.status,
        "error_log": run.error_log,
        "actual_cost_so_far": run.actual_cost_so_far,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
```

- [ ] **Step 4: Replace the director_plan guard in `pipeline_start`**

Replace:

```python
    if not body.director_plan:
        raise HTTPException(400, "director_plan is required")

    payload = _build_storyboard_payload(body.director_plan)
```

with:

```python
    director_plan = body.director_plan or _load_director_plan_from_episode(
        db,
        body.series_id,
        body.episode_id,
    )
    if not director_plan:
        raise HTTPException(400, "director_plan is required when episode_id is not provided")

    payload = _build_storyboard_payload(director_plan)
```

Then replace the two `body.director_plan.get(...)` calls in `GeneratedVideo(...)` with `director_plan.get(...)`.

- [ ] **Step 5: Add run query routes**

Append to `server/app/routers/pipeline.py`:

```python
@router.get("/runs/{series_id}")
async def list_pipeline_runs(
    series_id: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    runs = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id,
    ).order_by(PipelineRun.created_at.desc()).all()
    return {"ok": True, "runs": [_serialize_run(r) for r in runs]}


@router.get("/runs/by-id/{run_id}")
async def get_pipeline_run_by_id(
    run_id: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Pipeline run not found")
    return {"ok": True, "run": _serialize_run(run)}


@router.get("/runs/{series_id}/{run_id}")
async def get_pipeline_run(
    series_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id,
        PipelineRun.series_id == series_id,
    ).first()
    if not run:
        raise HTTPException(404, "Pipeline run not found")
    return {"ok": True, "run": _serialize_run(run)}
```

- [ ] **Step 6: Run compatibility tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pipeline_saved_storyboard_compat.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/app/routers/pipeline.py server/tests/test_pipeline_saved_storyboard_compat.py
git commit -m "fix: load saved storyboard for pipeline start"
```

---

## Task 3: Add Runtime Model Config Resolver

**Files:**
- Create: `server/app/services/runtime_model_config.py`
- Create: `server/tests/test_runtime_model_config.py`

- [ ] **Step 1: Write failing resolver tests**

Create `server/tests/test_runtime_model_config.py`:

```python
from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.runtime_model_config import resolve_runtime_model_config, redact_runtime_model_config


def test_resolve_runtime_model_config_decrypts_for_server_payload(db):
    model = AIModel(
        name="Seedance Image",
        model_type="image",
        provider="seedance",
        base_url="https://ark.test",
        api_key=encrypt("secret-key"),
        model_name="doubao-seedance-image",
        enabled=True,
        config_json={"scene_key": "image_generation", "config_version": 7},
    )
    db.add(model)
    db.commit()

    resolved = resolve_runtime_model_config(db, "image_generation")

    assert resolved["scene_key"] == "image_generation"
    assert resolved["provider"] == "seedance"
    assert resolved["model"] == "doubao-seedance-image"
    assert resolved["api_key"] == "secret-key"
    assert resolved["config_version"] == 7


def test_redact_runtime_model_config_removes_secret():
    payload = {
        "scene_key": "image_generation",
        "provider": "seedance",
        "model": "doubao-seedance-image",
        "api_key": "secret-key",
        "base_url": "https://ark.test",
        "config_version": 7,
    }

    redacted = redact_runtime_model_config(payload)

    assert redacted["provider"] == "seedance"
    assert redacted["model"] == "doubao-seedance-image"
    assert redacted["config_version"] == 7
    assert "api_key" not in redacted
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_runtime_model_config.py -q
```

Expected: FAIL because `runtime_model_config.py` does not exist.

- [ ] **Step 3: Create resolver**

Create `server/app/services/runtime_model_config.py`:

```python
"""Resolve dy_auto AIModel rows into runtime Pixelle stage payloads."""
from sqlalchemy.orm import Session

from app.db_models import AIModel
from app.services.crypto import decrypt


class RuntimeModelConfigError(ValueError):
    pass


def resolve_runtime_model_config(db: Session, scene_key: str, explicit_model_id: str | None = None) -> dict:
    query = db.query(AIModel).filter(AIModel.enabled == True)
    if explicit_model_id:
        query = query.filter(AIModel.id == explicit_model_id)
    else:
        query = query.filter(AIModel.config_json["scene_key"].as_string() == scene_key)
    model = query.order_by(AIModel.sort_order.asc(), AIModel.created_at.asc()).first()
    if not model:
        raise RuntimeModelConfigError(f"No enabled model configured for scene '{scene_key}'")

    api_key = ""
    if model.api_key:
        api_key = decrypt(model.api_key)

    config = model.config_json or {}
    return {
        "scene_key": scene_key,
        "model_id": model.id,
        "provider": model.provider,
        "model": model.model_name or "",
        "base_url": model.base_url or "",
        "api_key": api_key,
        "config": config,
        "config_version": config.get("config_version", 1),
    }


def redact_runtime_model_config(config: dict) -> dict:
    redacted = dict(config or {})
    redacted.pop("api_key", None)
    if isinstance(redacted.get("config"), dict):
        redacted["config"] = {
            key: value for key, value in redacted["config"].items()
            if "key" not in key.lower() and "secret" not in key.lower()
        }
    return redacted
```

- [ ] **Step 4: Run resolver tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_runtime_model_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/runtime_model_config.py server/tests/test_runtime_model_config.py
git commit -m "feat: resolve runtime model config for Pixelle stages"
```

---

## Task 4: Fix Audit Gate Semantics

**Files:**
- Create: `server/app/services/audit_gate.py`
- Modify: `server/app/routers/audit.py`
- Create: `server/tests/test_audit_gate.py`

- [ ] **Step 1: Write failing audit gate tests**

Create `server/tests/test_audit_gate.py`:

```python
from app.services.audit_gate import classify_audit_gate


def test_missing_audit_config_needs_human():
    result = classify_audit_gate({"score": 0.0, "pass_fail": False, "issues": ["missing api key"]})
    assert result["gate_status"] == "needs_human"
    assert result["pass_fail"] is False


def test_low_score_needs_human_by_default():
    result = classify_audit_gate({"score": 0.62, "pass_fail": True, "issues": []})
    assert result["gate_status"] == "needs_human"
    assert result["pass_fail"] is False


def test_high_score_approved():
    result = classify_audit_gate({"score": 0.93, "pass_fail": True, "issues": []})
    assert result["gate_status"] == "approved"
    assert result["pass_fail"] is True


def test_exception_result_needs_human():
    result = classify_audit_gate({"score": 0.0, "pass_fail": False, "issues": ["timeout"], "raw": ""}, error=True)
    assert result["gate_status"] == "needs_human"
    assert result["pass_fail"] is False
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_audit_gate.py -q
```

Expected: FAIL because `audit_gate.py` does not exist.

- [ ] **Step 3: Create audit gate classifier**

Create `server/app/services/audit_gate.py`:

```python
"""Classify audit responses into production gate decisions."""


def classify_audit_gate(result: dict, *, error: bool = False, approve_threshold: float = 0.85) -> dict:
    score = float((result or {}).get("score") or 0.0)
    issues = list((result or {}).get("issues") or [])
    raw_pass = bool((result or {}).get("pass_fail", False))

    if error:
        gate_status = "needs_human"
    elif issues and any("api key" in str(issue).lower() or "missing" in str(issue).lower() for issue in issues):
        gate_status = "needs_human"
    elif not raw_pass:
        gate_status = "needs_human"
    elif score < approve_threshold:
        gate_status = "needs_human"
    else:
        gate_status = "approved"

    return {
        **(result or {}),
        "score": score,
        "issues": issues,
        "gate_status": gate_status,
        "pass_fail": gate_status == "approved",
    }
```

- [ ] **Step 4: Update audit route to return gate_status**

In `server/app/routers/audit.py`, add:

```python
from app.services.audit_gate import classify_audit_gate
```

Replace the exception block in `audit_image`:

```python
    try:
        result = _do_audit(model_config, body.image_url, body.audit_criteria)
        result = classify_audit_gate(result)
    except Exception as e:
        logger.exception("Audit API call failed")
        result = classify_audit_gate(
            {"score": 0.0, "pass_fail": False, "issues": [str(e)], "raw": ""},
            error=True,
        )
```

Then include `gate_status` in the returned report:

```python
        "issues": report.issues_json,
        "auditor_model": report.auditor_model,
        "gate_status": result["gate_status"],
```

- [ ] **Step 5: Run audit tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_audit_gate.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/services/audit_gate.py server/app/routers/audit.py server/tests/test_audit_gate.py
git commit -m "fix: route uncertain audit results to human review"
```

---

## Task 5: Fix Pixelle Config Secret Redaction

**Files:**
- Modify: `server/app/routers/pixelle.py`
- Create: `server/tests/test_pixelle_config_security.py`

- [ ] **Step 1: Write failing redaction tests**

Create `server/tests/test_pixelle_config_security.py`:

```python
from app.routers.pixelle import _redact_secrets


def test_redact_secrets_recursively_redacts_nested_api_keys():
    config = {
        "llm": {"api_key": "llm-secret"},
        "ai_models": {
            "scenes": {
                "image_generation": {
                    "provider": "seedance",
                    "api_key": "image-secret",
                    "nested": {"api_secret": "nested-secret"},
                }
            }
        },
    }

    redacted = _redact_secrets(config)

    assert redacted["llm"]["api_key"] != "llm-secret"
    assert redacted["ai_models"]["scenes"]["image_generation"]["api_key"] != "image-secret"
    assert redacted["ai_models"]["scenes"]["image_generation"]["nested"]["api_secret"] != "nested-secret"
    assert config["ai_models"]["scenes"]["image_generation"]["api_key"] == "image-secret"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_config_security.py -q
```

Expected: FAIL because nested `ai_models` secrets are not redacted.

- [ ] **Step 3: Replace redaction implementation**

In `server/app/routers/pixelle.py`, replace `_redact_secrets` with:

```python
_SECRET_KEY_PARTS = ("api_key", "api_secret", "secret", "token", "authorization")


def _redact_secrets(config):
    """Return a deep copy with secret-looking values redacted for safe display."""
    if isinstance(config, list):
        return [_redact_secrets(item) for item in config]
    if isinstance(config, dict):
        safe = {}
        for key, value in config.items():
            if any(part in str(key).lower() for part in _SECRET_KEY_PARTS):
                safe[key] = _redact_api_key(str(value or ""))
            else:
                safe[key] = _redact_secrets(value)
        return safe
    return config
```

- [ ] **Step 4: Run redaction tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_config_security.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/app/routers/pixelle.py server/tests/test_pixelle_config_security.py
git commit -m "fix: recursively redact Pixelle config secrets"
```

---

## Task 6: Add Pixelle Stage API Auth, Schemas, and File Safety

**Files:**
- Modify: `D:\devWorkspace\Pixelle-Video\api\middleware.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\routers\files.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\tasks\models.py`
- Create: `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py`
- Create: `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\routers\__init__.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\app.py`
- Create: `D:\devWorkspace\Pixelle-Video\tests\test_stage_api_auth.py`
- Create: `D:\devWorkspace\Pixelle-Video\tests\test_files_security.py`
- Create: `D:\devWorkspace\Pixelle-Video\tests\test_stage_images_api.py`

- [ ] **Step 1: Add Pixelle auth and file security tests**

Create `D:\devWorkspace\Pixelle-Video\tests\test_stage_api_auth.py`:

```python
from fastapi.testclient import TestClient

from api.app import app


def test_stage_runtime_credentials_require_api_key(monkeypatch):
    monkeypatch.setattr("api.middleware.API_KEY", "stage-secret")
    client = TestClient(app)

    resp = client.post("/api/stages/images/batch", json={
        "external_run_id": "run-1",
        "episode_id": "episode-1",
        "frames": [],
        "model_config": {"api_key": "runtime-secret"},
    })

    assert resp.status_code == 401


def test_stage_runtime_credentials_accept_valid_api_key(monkeypatch):
    monkeypatch.setattr("api.middleware.API_KEY", "stage-secret")
    client = TestClient(app)

    resp = client.post(
        "/api/stages/images/batch",
        headers={"X-API-Key": "stage-secret"},
        json={
            "external_run_id": "run-1",
            "episode_id": "episode-1",
            "frames": [{
                "frame_id": "frame-001",
                "image_prompt": "test image",
                "reference_urls": [],
                "duration": 5,
            }],
            "model_config": {"provider": "mock", "api_key": "runtime-secret"},
        },
    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
```

Create `D:\devWorkspace\Pixelle-Video\tests\test_files_security.py`:

```python
from fastapi.testclient import TestClient

from api.app import app


def test_files_endpoint_rejects_parent_traversal():
    client = TestClient(app)

    resp = client.get("/api/files/../config.yaml")

    assert resp.status_code in (403, 404)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_files_security.py -q
```

Expected: FAIL because `/api/stages/images/batch` does not exist and file path checks are not resolved first.

- [ ] **Step 3: Add stage task types**

In `D:\devWorkspace\Pixelle-Video\api\tasks\models.py`, replace `TaskType` with:

```python
class TaskType(str, Enum):
    """Task type"""
    VIDEO_GENERATION = "video_generation"
    IMAGE_BATCH = "image_batch"
    VIDEO_BATCH = "video_batch"
    COMPOSE = "compose"
```

- [ ] **Step 4: Add stage schemas**

Create `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py`:

```python
from typing import Any

from pydantic import BaseModel, Field


class StageFrame(BaseModel):
    frame_id: str
    image_prompt: str
    reference_urls: list[str] = Field(default_factory=list)
    style_constraints: dict[str, Any] = Field(default_factory=dict)
    duration: float = 5.0


class StageAsset(BaseModel):
    frame_id: str
    asset_type: str
    url: str = ""
    local_path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImageBatchRequest(BaseModel):
    external_run_id: str
    episode_id: str
    frames: list[StageFrame]
    model_config: dict[str, Any] = Field(default_factory=dict)
    template_config: dict[str, Any] = Field(default_factory=dict)


class StageTaskResponse(BaseModel):
    ok: bool
    stage_task_id: str
    assets: list[StageAsset] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)


class StageTaskStatusResponse(BaseModel):
    ok: bool
    stage_task_id: str
    status: str
    progress: dict[str, Any] = Field(default_factory=dict)
    assets: list[StageAsset] = Field(default_factory=list)
    error: str | None = None
```

- [ ] **Step 5: Add stages router**

Create `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`:

```python
from fastapi import APIRouter, HTTPException

from api.dependencies import PixelleVideoDep
from api.schemas.stages import ImageBatchRequest, StageAsset, StageTaskResponse, StageTaskStatusResponse
from api.tasks import TaskType, task_manager


router = APIRouter(prefix="/stages", tags=["Stages"])


def _public_file_url(path: str) -> str:
    clean = str(path).replace("\\", "/")
    if clean.startswith("output/"):
        clean = clean[len("output/"):]
    return f"/api/files/{clean}"


async def _run_image_batch(request: ImageBatchRequest, pixelle_video: PixelleVideoDep, task_id: str) -> dict:
    assets = []
    total = max(len(request.frames), 1)
    for index, frame in enumerate(request.frames, start=1):
        task_manager.update_progress(task_id, index - 1, total, f"Generating {frame.frame_id}")
        if request.model_config.get("provider") == "mock":
            local_path = f"output/{task_id}/{frame.frame_id}.png"
            url = _public_file_url(local_path)
        else:
            media_result = await pixelle_video.media(
                prompt=frame.image_prompt,
                width=int(request.template_config.get("width", 1080)),
                height=int(request.template_config.get("height", 1920)),
                workflow=request.template_config.get("workflow"),
            )
            local_path = media_result.url
            url = media_result.url
        assets.append(StageAsset(
            frame_id=frame.frame_id,
            asset_type="image",
            url=url,
            local_path=local_path,
            metadata={"duration": frame.duration},
        ).model_dump())
        task_manager.update_progress(task_id, index, total, f"Generated {frame.frame_id}")
    return {"assets": assets}


@router.post("/images/batch", response_model=StageTaskResponse)
async def image_batch(request: ImageBatchRequest, pixelle_video: PixelleVideoDep):
    if not request.frames:
        raise HTTPException(status_code=400, detail="frames is required")
    task = task_manager.create_task(TaskType.IMAGE_BATCH, request.model_dump(exclude={"model_config"}))
    await task_manager.execute_task(task.task_id, _run_image_batch, request, pixelle_video, task.task_id)
    return StageTaskResponse(ok=True, stage_task_id=task.task_id, assets=[], logs=[])


@router.get("/tasks/{stage_task_id}", response_model=StageTaskStatusResponse)
async def stage_task_status(stage_task_id: str):
    task = task_manager.get_task(stage_task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Stage task {stage_task_id} not found")
    result = task.result or {}
    return StageTaskStatusResponse(
        ok=task.status.value != "failed",
        stage_task_id=task.task_id,
        status=task.status.value,
        progress=task.progress.model_dump() if task.progress else {},
        assets=result.get("assets", []),
        error=task.error,
    )
```

- [ ] **Step 6: Export and include stages router**

In `D:\devWorkspace\Pixelle-Video\api\routers\__init__.py`, add:

```python
from api.routers.stages import router as stages_router
```

and add `"stages_router"` to `__all__`.

In `D:\devWorkspace\Pixelle-Video\api\app.py`, update the router import list to include `stages_router`, then add:

```python
app.include_router(stages_router, prefix=api_config.api_prefix)
```

- [ ] **Step 7: Require API key for stage runtime credentials**

In `D:\devWorkspace\Pixelle-Video\api\middleware.py`, replace `dispatch` with:

```python
    async def dispatch(self, request: Request, call_next):
        is_public = request.url.path in PUBLIC_PATHS
        is_stage = request.url.path.startswith("/api/stages/")
        if is_public:
            return await call_next(request)

        if not API_KEY and not is_stage:
            return await call_next(request)

        key = request.headers.get("X-API-Key", "")
        if key != API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return await call_next(request)
```

- [ ] **Step 8: Resolve file paths before allow-list checks**

In `D:\devWorkspace\Pixelle-Video\api\routers\files.py`, replace:

```python
        abs_path = Path.cwd() / full_path
```

with:

```python
        root = Path.cwd().resolve()
        abs_path = (root / full_path).resolve()
```

Then replace:

```python
            rel_path = abs_path.relative_to(Path.cwd())
```

with:

```python
            rel_path = abs_path.relative_to(root)
```

- [ ] **Step 9: Run Pixelle tests**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_files_security.py tests/test_stage_images_api.py -q
```

Expected: PASS after `tests/test_stage_images_api.py` is added in Step 10.

- [ ] **Step 10: Add image stage behavior test**

Create `D:\devWorkspace\Pixelle-Video\tests\test_stage_images_api.py`:

```python
from fastapi.testclient import TestClient

from api.app import app


def test_image_stage_returns_stage_task(monkeypatch):
    monkeypatch.setattr("api.middleware.API_KEY", "stage-secret")
    client = TestClient(app)

    resp = client.post(
        "/api/stages/images/batch",
        headers={"X-API-Key": "stage-secret"},
        json={
            "external_run_id": "run-1",
            "episode_id": "episode-1",
            "frames": [{
                "frame_id": "frame-001",
                "image_prompt": "test image",
                "reference_urls": [],
                "duration": 5,
            }],
            "model_config": {"provider": "mock", "api_key": "runtime-secret"},
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["stage_task_id"]
```

- [ ] **Step 11: Commit Pixelle changes**

```powershell
cd D:\devWorkspace\Pixelle-Video
git add api/middleware.py api/routers/files.py api/tasks/models.py api/schemas/stages.py api/routers/stages.py api/routers/__init__.py api/app.py tests/test_stage_api_auth.py tests/test_files_security.py tests/test_stage_images_api.py
git commit -m "feat: add authenticated image stage API"
```

---

## Task 7: Add dy_auto Pixelle Stage Client

**Files:**
- Create: `server/app/services/pixelle_stage_client.py`
- Create: `server/tests/test_pixelle_stage_client.py`

- [ ] **Step 1: Write failing client tests**

Create `server/tests/test_pixelle_stage_client.py`:

```python
import pytest

from app.services.pixelle_stage_client import submit_image_batch, get_stage_task


@pytest.mark.asyncio
async def test_submit_image_batch_calls_pixelle_stage_api(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-1", "assets": []}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await submit_image_batch(
        db=None,
        run_id="run-1",
        episode_id="episode-1",
        frames=[{"frame_id": "frame-001", "image_prompt": "prompt", "reference_urls": [], "duration": 5}],
        model_config={"provider": "mock", "api_key": "secret"},
    )

    assert result["stage_task_id"] == "stage-1"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/stages/images/batch"
    assert calls[0][2]["external_run_id"] == "run-1"


@pytest.mark.asyncio
async def test_get_stage_task_calls_pixelle_status(monkeypatch):
    async def fake_request(method, path, db=None, **kwargs):
        return {"ok": True, "stage_task_id": "stage-1", "status": "completed", "assets": []}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await get_stage_task(None, "stage-1")

    assert result["status"] == "completed"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_stage_client.py -q
```

Expected: FAIL because `pixelle_stage_client.py` does not exist.

- [ ] **Step 3: Create client**

Create `server/app/services/pixelle_stage_client.py`:

```python
"""Client for Pixelle-Video stage APIs."""
from sqlalchemy.orm import Session

from app.services.pixelle_client import _pixelle_request


async def submit_image_batch(
    db: Session | None,
    run_id: str,
    episode_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "episode_id": episode_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    return await _pixelle_request("POST", "/api/stages/images/batch", db, json=payload)


async def get_stage_task(db: Session | None, stage_task_id: str) -> dict:
    return await _pixelle_request("GET", f"/api/stages/tasks/{stage_task_id}", db)
```

- [ ] **Step 4: Run client tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_stage_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/pixelle_stage_client.py server/tests/test_pixelle_stage_client.py
git commit -m "feat: add Pixelle stage client"
```

---

## Task 8: Add Video Production Service

**Files:**
- Create: `server/app/services/video_production_service.py`
- Create: `server/tests/test_video_production_service.py`

- [ ] **Step 1: Write failing service tests**

Create `server/tests/test_video_production_service.py`:

```python
import pytest

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import (
    approve_asset,
    create_run_from_episode,
    latest_approved_assets_by_frame,
    mark_image_stage_assets,
)


def _episode_with_storyboard(db):
    series = Series(title="Image Wedge", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "image_prompt": "Prompt",
                "reference_urls": ["https://cdn.test/ref.png"],
                "duration": 5,
            }]
        },
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_create_run_from_episode_copies_storyboard(db):
    series, episode = _episode_with_storyboard(db)

    run = create_run_from_episode(db, series.id, episode.id)

    assert run.status == "draft"
    assert run.current_stage == "storyboard_ready"
    assert run.storyboard_json["frames"][0]["frame_id"] == "frame-001"


def test_mark_image_stage_assets_creates_review_pending_assets(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)

    assets = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/image.png",
        "local_path": "output/image.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")

    assert assets[0].status == "review_pending"
    assert assets[0].version == 1
    assert db.query(VideoProductionRun).filter_by(id=run.id).one().status == "image_review_pending"


def test_latest_approved_assets_uses_latest_version(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)
    old_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        version=1,
        status="approved",
        url="old.png",
    )
    new_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        version=2,
        status="review_pending",
        url="new.png",
    )
    db.add_all([old_asset, new_asset])
    db.commit()

    approved = latest_approved_assets_by_frame(db, run.id)

    assert approved == {}


def test_approve_asset_records_human_review(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)
    asset = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/image.png",
        "local_path": "output/image.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")[0]

    approve_asset(db, asset.id, reviewer_user_id="user-1", comment="looks good")

    db.refresh(asset)
    assert asset.status == "approved"
    assert latest_approved_assets_by_frame(db, run.id)["frame-001"].id == asset.id
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_service.py -q
```

Expected: FAIL because `video_production_service.py` does not exist.

- [ ] **Step 3: Create service**

Create `server/app/services/video_production_service.py`:

```python
"""Staged video production orchestration owned by dy_auto."""
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import (
    Episode,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)


class VideoProductionError(ValueError):
    pass


def _frame_id(frame: dict, index: int) -> str:
    return str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}")


def create_run_from_episode(db: Session, series_id: str, episode_id: str) -> VideoProductionRun:
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
    db.commit()
    db.refresh(run)
    return run


def image_stage_frames(run: VideoProductionRun) -> list[dict]:
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


def mark_image_stage_submitted(db: Session, run: VideoProductionRun, stage_task_id: str, model_trace: dict) -> VideoProductionRun:
    run.status = "image_batch_running"
    run.current_stage = "image_generation"
    run.pixelle_stage_task_id = stage_task_id
    run.model_trace_json = model_trace
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run


def _next_asset_version(db: Session, run_id: str, frame_id: str, asset_type: str) -> int:
    latest = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.frame_id == frame_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.version.desc()).first()
    return (latest.version + 1) if latest else 1


def mark_image_stage_assets(db: Session, run: VideoProductionRun, assets: list[dict], pixelle_task_id: str) -> list[VideoProductionAsset]:
    saved = []
    for item in assets:
        frame_id = item["frame_id"]
        asset = VideoProductionAsset(
            run_id=run.id,
            episode_id=run.episode_id,
            frame_id=frame_id,
            asset_type="image",
            stage="image_generation",
            url=item.get("url", ""),
            local_path=item.get("local_path", ""),
            thumbnail_url=item.get("thumbnail_url", ""),
            version=_next_asset_version(db, run.id, frame_id, "image"),
            metadata_json=item.get("metadata", {}),
            status="review_pending",
            pixelle_task_id=pixelle_task_id,
        )
        db.add(asset)
        saved.append(asset)
    run.status = "image_review_pending"
    run.current_stage = "image_review"
    run.updated_at = bj_now()
    db.commit()
    for asset in saved:
        db.refresh(asset)
    return saved


def latest_assets_by_frame(db: Session, run_id: str, asset_type: str = "image") -> dict[str, VideoProductionAsset]:
    rows = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.frame_id.asc(), VideoProductionAsset.version.desc()).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.frame_id, row)
    return latest


def latest_approved_assets_by_frame(db: Session, run_id: str, asset_type: str = "image") -> dict[str, VideoProductionAsset]:
    latest = latest_assets_by_frame(db, run_id, asset_type)
    return {frame_id: asset for frame_id, asset in latest.items() if asset.status == "approved"}


def approve_asset(db: Session, asset_id: str, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")
    latest = latest_assets_by_frame(db, asset.run_id, asset.asset_type).get(asset.frame_id)
    if latest and latest.id != asset.id:
        raise VideoProductionError("A newer asset version exists. Reload before reviewing.")
    asset.status = "approved"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="approved",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
    ))
    db.commit()
    db.refresh(asset)
    return asset
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/video_production_service.py server/tests/test_video_production_service.py
git commit -m "feat: add image-stage production service"
```

---

## Task 9: Add dy_auto Video Production API

**Files:**
- Create: `server/app/routers/video_production.py`
- Modify: `server/app/main.py`
- Create: `server/tests/test_video_production_api.py`

- [ ] **Step 1: Write failing API tests**

Create `server/tests/test_video_production_api.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, Series
from app.main import app


client = TestClient(app)


def _episode(db):
    series = Series(title="Review API", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "duration": 5}]},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_create_video_production_run(db):
    series, episode = _episode(db)

    resp = client.post("/api/video-production/runs", json={
        "series_id": series.id,
        "episode_id": episode.id,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["run"]["episode_id"] == episode.id
    assert body["run"]["current_stage"] == "storyboard_ready"
```

- [ ] **Step 2: Run API test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_api.py -q
```

Expected: FAIL because `/api/video-production/runs` is not registered.

- [ ] **Step 3: Create router**

Create `server/app/routers/video_production.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import (
    VideoProductionError,
    approve_asset,
    create_run_from_episode,
    latest_assets_by_frame,
)

router = APIRouter(prefix="/api/video-production", tags=["video-production"])


class CreateRunRequest(BaseModel):
    series_id: str
    episode_id: str


class ReviewAssetRequest(BaseModel):
    action: str
    comment: str = ""


def _run_payload(run: VideoProductionRun) -> dict:
    return {
        "id": run.id,
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "pixelle_stage_task_id": run.pixelle_stage_task_id,
        "storyboard_json": run.storyboard_json or {},
        "model_trace_json": run.model_trace_json or {},
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def _asset_payload(asset: VideoProductionAsset) -> dict:
    return {
        "id": asset.id,
        "run_id": asset.run_id,
        "episode_id": asset.episode_id,
        "frame_id": asset.frame_id,
        "asset_type": asset.asset_type,
        "stage": asset.stage,
        "url": asset.url,
        "local_path": asset.local_path,
        "thumbnail_url": asset.thumbnail_url,
        "duration_seconds": asset.duration_seconds,
        "version": asset.version,
        "metadata_json": asset.metadata_json or {},
        "status": asset.status,
        "pixelle_task_id": asset.pixelle_task_id,
    }


@router.post("/runs")
def create_run(
    body: CreateRunRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = create_run_from_episode(db, body.series_id, body.episode_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    assets = db.query(VideoProductionAsset).filter(VideoProductionAsset.run_id == run.id).all()
    return {"ok": True, "run": _run_payload(run), "assets": [_asset_payload(a) for a in assets]}


@router.get("/review-items")
def review_items(
    run_id: str | None = None,
    status: str = "review_pending",
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    query = db.query(VideoProductionAsset).filter(VideoProductionAsset.status == status)
    if run_id:
        query = query.filter(VideoProductionAsset.run_id == run_id)
    items = query.order_by(VideoProductionAsset.created_at.desc()).limit(100).all()
    return {"ok": True, "items": [_asset_payload(item) for item in items]}


@router.post("/assets/{asset_id}/review")
def review_asset(
    asset_id: str,
    body: ReviewAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    reviewer_id = user[0] if isinstance(user, tuple) else None
    if body.action != "approve":
        raise HTTPException(400, "Only approve is implemented in the image wedge")
    try:
        asset = approve_asset(db, asset_id, reviewer_user_id=reviewer_id, comment=body.comment)
    except VideoProductionError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
```

- [ ] **Step 4: Register router**

In `server/app/main.py`, update the router import line to include `video_production`:

```python
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content, account_groups, chains, settings, channels, prompt_templates, data, videos, pixelle, ai_config, characters, scenes, series, pipeline, audit, director, reference_data, dm_sequences, video_production
```

Add after `app.include_router(director.router)`:

```python
app.include_router(video_production.router)
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/routers/video_production.py server/app/main.py server/tests/test_video_production_api.py
git commit -m "feat: expose video production run API"
```

---

## Task 10: Add Image Stage Submit and Poll Flow

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/routers/video_production.py`
- Create: `server/tests/test_video_production_mocked_e2e.py`

- [ ] **Step 1: Write mocked image-stage E2E test**

Create `server/tests/test_video_production_mocked_e2e.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import AIModel, Episode, Series
from app.main import app


client = TestClient(app)


def test_mocked_image_stage_to_human_approval(db, monkeypatch):
    series = Series(title="Mocked E2E", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "duration": 5}]},
    )
    model = AIModel(
        name="Mock Image",
        model_type="image",
        provider="mock",
        model_name="mock-image",
        enabled=True,
        config_json={"scene_key": "image_generation"},
    )
    db.add_all([episode, model])
    db.commit()

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        return {"ok": True, "stage_task_id": "stage-1", "assets": []}

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "stage_task_id": stage_task_id,
            "status": "completed",
            "assets": [{
                "frame_id": "frame-001",
                "asset_type": "image",
                "url": "https://cdn.test/frame-001.png",
                "local_path": "output/frame-001.png",
                "metadata": {},
            }],
        }

    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)

    run_resp = client.post("/api/video-production/runs", json={"series_id": series.id, "episode_id": episode.id})
    run_id = run_resp.json()["run"]["id"]

    submit_resp = client.post(f"/api/video-production/runs/{run_id}/start-images")
    assert submit_resp.status_code == 200

    sync_resp = client.post(f"/api/video-production/runs/{run_id}/sync-image-results")
    assert sync_resp.status_code == 200
    items = client.get(f"/api/video-production/review-items?run_id={run_id}").json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "review_pending"

    approve_resp = client.post(f"/api/video-production/assets/{items[0]['id']}/review", json={"action": "approve"})
    assert approve_resp.status_code == 200
```

- [ ] **Step 2: Run E2E test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_mocked_e2e.py -q
```

Expected: FAIL because image-stage routes are not implemented.

- [ ] **Step 3: Add image submit and sync functions**

At the top of `server/app/services/video_production_service.py`, add:

```python
from app.services.pixelle_stage_client import get_stage_task, submit_image_batch
from app.services.runtime_model_config import redact_runtime_model_config, resolve_runtime_model_config
```

Append:

```python
async def start_image_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    frames = image_stage_frames(run)
    if not frames:
        raise VideoProductionError("Run has no storyboard frames")
    model_config = resolve_runtime_model_config(db, "image_generation")
    response = await submit_image_batch(
        db=db,
        run_id=run.id,
        episode_id=run.episode_id,
        frames=frames,
        model_config=model_config,
    )
    return mark_image_stage_submitted(
        db,
        run,
        response["stage_task_id"],
        {"image_generation": redact_runtime_model_config(model_config)},
    )


async def sync_image_stage_results(db: Session, run_id: str) -> list[VideoProductionAsset]:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Image stage is not complete: {status.get('status')}")
    return mark_image_stage_assets(db, run, status.get("assets", []), pixelle_task_id=run.pixelle_stage_task_id)
```

- [ ] **Step 4: Add image-stage routes**

In `server/app/routers/video_production.py`, update imports:

```python
from app.services.video_production_service import (
    VideoProductionError,
    approve_asset,
    create_run_from_episode,
    latest_assets_by_frame,
    start_image_stage,
    sync_image_stage_results,
)
```

Append:

```python
@router.post("/runs/{run_id}/start-images")
async def start_images(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = await start_image_stage(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.post("/runs/{run_id}/sync-image-results")
async def sync_images(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        assets = await sync_image_stage_results(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "assets": [_asset_payload(asset) for asset in assets]}
```

- [ ] **Step 5: Run mocked E2E**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_mocked_e2e.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/services/video_production_service.py server/app/routers/video_production.py server/tests/test_video_production_mocked_e2e.py
git commit -m "feat: run mocked image-stage production flow"
```

---

## Task 11: Add Single-Image Regeneration

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/routers/video_production.py`
- Modify: `server/tests/test_video_production_service.py`
- Modify: `server/tests/test_video_production_api.py`

- [ ] **Step 1: Add failing regeneration service test**

Append to `server/tests/test_video_production_service.py`:

```python
def test_regeneration_marks_old_asset_and_creates_next_version(db):
    from app.services.video_production_service import create_regenerated_image_asset

    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)
    asset = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/v1.png",
        "local_path": "output/v1.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")[0]

    new_asset = create_regenerated_image_asset(db, asset.id, {
        "url": "https://cdn.test/v2.png",
        "local_path": "output/v2.png",
        "metadata": {},
    })

    db.refresh(asset)
    assert asset.status == "regenerating"
    assert new_asset.version == 2
    assert new_asset.status == "review_pending"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_service.py::test_regeneration_marks_old_asset_and_creates_next_version -q
```

Expected: FAIL because `create_regenerated_image_asset` does not exist.

- [ ] **Step 3: Add regeneration service helper**

Append to `server/app/services/video_production_service.py`:

```python
def create_regenerated_image_asset(db: Session, asset_id: str, generated: dict) -> VideoProductionAsset:
    old = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not old:
        raise VideoProductionError("Asset not found")
    old.status = "regenerating"
    new_asset = VideoProductionAsset(
        run_id=old.run_id,
        episode_id=old.episode_id,
        frame_id=old.frame_id,
        asset_type="image",
        stage="image_generation",
        url=generated.get("url", ""),
        local_path=generated.get("local_path", ""),
        thumbnail_url=generated.get("thumbnail_url", ""),
        version=_next_asset_version(db, old.run_id, old.frame_id, "image"),
        metadata_json=generated.get("metadata", {}),
        status="review_pending",
        pixelle_task_id=generated.get("pixelle_task_id"),
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    return new_asset
```

- [ ] **Step 4: Add route for local/manual regeneration result**

For this wedge, make regeneration store a new review-pending version from a generated payload. Later video/provider work can call Pixelle for the actual new image.

In `server/app/routers/video_production.py`, add:

```python
class RegenerateAssetRequest(BaseModel):
    url: str
    local_path: str = ""
    thumbnail_url: str = ""
    metadata: dict = {}
    pixelle_task_id: str | None = None
```

Update imports to include:

```python
    create_regenerated_image_asset,
```

Append:

```python
@router.post("/assets/{asset_id}/regenerate")
def regenerate_asset(
    asset_id: str,
    body: RegenerateAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = create_regenerated_image_asset(db, asset_id, body.model_dump())
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
```

- [ ] **Step 5: Run regeneration tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_service.py tests/test_video_production_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/services/video_production_service.py server/app/routers/video_production.py server/tests/test_video_production_service.py server/tests/test_video_production_api.py
git commit -m "feat: preserve versions during image regeneration"
```

---

## Task 12: Add Frontend API Client and Review Center

**Files:**
- Create: `web/src/api/videoProduction.js`
- Create: `web/src/views/AIVideoReviewPage.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/constants/navigation.js`
- Modify: `web/src/__tests__/api-clients.test.js`
- Create: `web/src/__tests__/ai-video-review-page.test.js`

- [ ] **Step 1: Add API client tests**

Append to `web/src/__tests__/api-clients.test.js`:

```javascript
  describe('video production API', () => {
    it('createVideoProductionRun calls POST /video-production/runs', async () => {
      const { createVideoProductionRun } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createVideoProductionRun('sid', 'eid')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs', {
        series_id: 'sid',
        episode_id: 'eid',
      })
    })

    it('listReviewItems calls GET with filters', async () => {
      const { listReviewItems } = await import('../api/videoProduction.js')
      mockGet.mockResolvedValue({ data: { ok: true, items: [] } })
      await listReviewItems({ run_id: 'rid', status: 'review_pending' })
      expect(mockGet).toHaveBeenCalledWith('/video-production/review-items', {
        params: { run_id: 'rid', status: 'review_pending' },
      })
    })

    it('reviewAsset calls POST asset review endpoint', async () => {
      const { reviewAsset } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await reviewAsset('aid', 'approve', 'ok')
      expect(mockPost).toHaveBeenCalledWith('/video-production/assets/aid/review', {
        action: 'approve',
        comment: 'ok',
      })
    })
  })
```

- [ ] **Step 2: Run frontend API tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm test -- --run src/__tests__/api-clients.test.js
```

Expected: FAIL because `videoProduction.js` does not exist. If this project does not define `npm test`, run `npx vitest run src/__tests__/api-clients.test.js`.

- [ ] **Step 3: Create API client**

Create `web/src/api/videoProduction.js`:

```javascript
import client from './client.js'

export function createVideoProductionRun(seriesId, episodeId) {
  return client.post('/video-production/runs', {
    series_id: seriesId,
    episode_id: episodeId,
  })
}

export function getVideoProductionRun(runId) {
  return client.get(`/video-production/runs/${runId}`)
}

export function startImageStage(runId) {
  return client.post(`/video-production/runs/${runId}/start-images`)
}

export function syncImageStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-image-results`)
}

export function listReviewItems(params = {}) {
  return client.get('/video-production/review-items', { params })
}

export function reviewAsset(assetId, action, comment = '') {
  return client.post(`/video-production/assets/${assetId}/review`, { action, comment })
}

export function regenerateAsset(assetId, payload) {
  return client.post(`/video-production/assets/${assetId}/regenerate`, payload)
}
```

- [ ] **Step 4: Add review center page**

Create `web/src/views/AIVideoReviewPage.vue`:

```vue
<template>
  <div class="p-6">
    <div class="flex justify-between items-start mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">AI Video Review</h1>
        <p class="text-slate-500 text-sm mt-1">Human decisions for staged video production assets.</p>
      </div>
      <button @click="load" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
        Refresh
      </button>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">Loading review queue...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <div v-else class="grid grid-cols-[320px_1fr] gap-4">
      <aside class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.55);">
        <div class="px-4 py-3 border-b border-gray-700/50 text-sm text-slate-300">
          Pending review: {{ items.length }}
        </div>
        <button
          v-for="item in items"
          :key="item.id"
          @click="selected = item"
          class="w-full text-left px-4 py-3 border-b border-gray-800/60 hover:bg-slate-800/60"
          :class="selected?.id === item.id ? 'bg-slate-800/80' : ''"
        >
          <div class="text-sm text-slate-100">{{ item.frame_id }}</div>
          <div class="text-xs text-slate-500">v{{ item.version }} · {{ item.status }} · {{ item.stage }}</div>
        </button>
        <div v-if="!items.length" class="px-4 py-10 text-center text-sm text-slate-500">
          No assets need human review.
        </div>
      </aside>

      <section class="rounded-xl border border-gray-700/50 p-5 min-h-[520px]" style="background: rgba(15, 23, 42, 0.55);">
        <template v-if="selected">
          <div class="flex justify-between gap-4 mb-4">
            <div>
              <h2 class="text-lg font-semibold text-slate-100">{{ selected.frame_id }}</h2>
              <p class="text-xs text-slate-500">Asset {{ selected.id }}</p>
            </div>
            <span class="px-2 py-1 rounded text-xs bg-amber-900/40 text-amber-300 h-fit">{{ selected.status }}</span>
          </div>

          <div class="aspect-video rounded-lg border border-gray-700/50 bg-slate-950/80 mb-4 overflow-hidden flex items-center justify-center">
            <img v-if="selected.url" :src="selected.url" :alt="selected.frame_id" class="max-h-full max-w-full object-contain" />
            <span v-else class="text-sm text-slate-500">No preview URL</span>
          </div>

          <dl class="grid grid-cols-2 gap-3 text-sm mb-5">
            <div>
              <dt class="text-slate-500">Run</dt>
              <dd class="text-slate-200 font-mono">{{ selected.run_id }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">Version</dt>
              <dd class="text-slate-200">v{{ selected.version }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">Local path</dt>
              <dd class="text-slate-200 break-all">{{ selected.local_path || 'Not provided' }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">Pixelle task</dt>
              <dd class="text-slate-200 break-all">{{ selected.pixelle_task_id || 'Not provided' }}</dd>
            </div>
          </dl>

          <div class="flex gap-2">
            <button @click="approve" :disabled="acting" class="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">
              Approve latest
            </button>
          </div>
        </template>
        <div v-else class="text-slate-500 text-center py-24">
          Select an asset to review.
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { listReviewItems, reviewAsset } from '../api/videoProduction.js'

const route = useRoute()
const items = ref([])
const selected = ref(null)
const loading = ref(true)
const acting = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await listReviewItems({
      run_id: route.query.run_id || undefined,
      status: route.query.status || 'review_pending',
    })
    items.value = data.ok ? data.items || [] : []
    selected.value = items.value.find(item => item.id === route.query.asset_id) || items.value[0] || null
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load review queue'
  } finally {
    loading.value = false
  }
}

async function approve() {
  if (!selected.value) return
  acting.value = true
  try {
    await reviewAsset(selected.value.id, 'approve', 'Approved from review center')
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to approve asset'
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>
```

- [ ] **Step 5: Register route and navigation**

In `web/src/router/index.js`, add this child route near `pipeline/:runId`:

```javascript
      {
        path: 'ai-video-review',
        name: 'AIVideoReview',
        component: () => import('../views/AIVideoReviewPage.vue'),
      },
```

Add `'/ai-video-review'` to `ADMIN_ONLY_PATHS`.

In `web/src/constants/navigation.js`, add this item inside the `ai-video` category:

```javascript
      { name: 'AI 瑙嗛瀹℃煡', path: '/ai-video-review', icon: 'M9 12l2 2 4-4m5 2a9 9 0 11-18 0 9 9 0 0118 0z' },
```

Add route category:

```javascript
  '/ai-video-review': 'ai-video',
```

- [ ] **Step 6: Run frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/api/videoProduction.js web/src/views/AIVideoReviewPage.vue web/src/router/index.js web/src/constants/navigation.js web/src/__tests__/api-clients.test.js
git commit -m "feat: add AI video review center"
```

---

## Task 13: Wire Series and Pipeline Pages to the Wedge

**Files:**
- Modify: `web/src/views/SeriesDetailPage.vue`
- Modify: `web/src/views/PipelineMonitorPage.vue`
- Create: `web/src/__tests__/series-detail-video-production.test.js`

- [ ] **Step 1: Add failing series detail launch test**

Create `web/src/__tests__/series-detail-video-production.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SeriesDetailPage from '../views/SeriesDetailPage.vue'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  autoPlanEpisode: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  createVideoProductionRun: vi.fn(() => Promise.resolve({ data: { ok: true, run: { id: 'run-1' } } })),
  startImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'sid' } }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('../api/series.js', () => ({
  getSeries: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      series: {
        id: 'sid',
        title: 'City Healer',
        logline: 'One sentence story',
        total_episodes: 1,
        genre: 'drama',
        mode: 'fully_automatic',
        target_duration: 60,
      },
      episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
    },
  })),
  getStyleLock: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      locked: true,
      version: 1,
      missing_assets: [],
      reference_status: {
        characters: { ready: 1, total: 1 },
        scenes: { ready: 1, total: 1 },
      },
      agency_team_status: { enabled: true, core_role_count: 5, support_role_count: 4 },
    },
  })),
  lockSeriesStyle: vi.fn(),
  autoGenerateAssets: vi.fn(),
}))

vi.mock('../api/director.js', () => ({
  autoPlanEpisode: mocks.autoPlanEpisode,
}))

vi.mock('../api/pipeline.js', () => ({
  listRuns: vi.fn(() => Promise.resolve({ data: { ok: true, runs: [] } })),
  startPipeline: vi.fn(),
}))

vi.mock('../api/videoProduction.js', () => ({
  createVideoProductionRun: mocks.createVideoProductionRun,
  startImageStage: mocks.startImageStage,
}))

describe('SeriesDetailPage video production launch', () => {
  beforeEach(() => {
    mocks.push.mockClear()
    mocks.autoPlanEpisode.mockClear()
    mocks.createVideoProductionRun.mockClear()
    mocks.startImageStage.mockClear()
  })

  it('creates a staged run after auto-plan and opens the review center', async () => {
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.findAll('button').find(btn => btn.text().includes('鍚姩'))
    expect(button).toBeTruthy()
    await button.trigger('click')
    await flushPromises()

    expect(mocks.autoPlanEpisode).toHaveBeenCalledWith('sid', 'ep1', 60)
    expect(mocks.createVideoProductionRun).toHaveBeenCalledWith('sid', 'ep1')
    expect(mocks.startImageStage).toHaveBeenCalledWith('run-1')
    expect(mocks.push).toHaveBeenCalledWith('/ai-video-review?run_id=run-1')
  })
})
```

- [ ] **Step 2: Run series detail test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/series-detail-video-production.test.js
```

Expected: FAIL because `SeriesDetailPage.vue` still uses `startPipeline`.

- [ ] **Step 3: Add series detail start behavior**

In `web/src/views/SeriesDetailPage.vue`, add import:

```javascript
import { createVideoProductionRun, startImageStage } from '../api/videoProduction.js'
```

In `startPipelineRun`, replace:

```javascript
    const { data } = await startPipeline(route.params.id, ep.id, series.value.mode)
    if (data?.run_id) router.push(`/pipeline/${data.run_id}`)
```

with:

```javascript
    const { data } = await createVideoProductionRun(route.params.id, ep.id)
    if (!data?.run?.id) throw new Error('Production run was not created')
    await startImageStage(data.run.id)
    router.push(`/ai-video-review?run_id=${data.run.id}`)
```

Keep the old `startPipeline` import in place only if another function still uses it. If no function uses it after this edit, remove `startPipeline` from the import.

- [ ] **Step 4: Add pipeline review handoff**

In `web/src/views/PipelineMonitorPage.vue`, add this button near the agency console button:

```vue
          <button v-if="run.status === 'image_review_pending' || run.status === 'image_human_review_required'"
                  @click="$router.push(`/ai-video-review?run_id=${run.id}`)"
                  class="bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            Review required
          </button>
```

- [ ] **Step 5: Run focused frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/views/SeriesDetailPage.vue web/src/views/PipelineMonitorPage.vue web/src/__tests__/series-detail-video-production.test.js
git commit -m "feat: launch image-stage production from series detail"
```

---

## Task 14: Run Full Verification

**Files:**
- No new files. This task verifies the integrated wedge.

- [ ] **Step 1: Run dy_auto backend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_models.py tests/test_pipeline_saved_storyboard_compat.py tests/test_pixelle_config_security.py tests/test_audit_gate.py tests/test_runtime_model_config.py tests/test_pixelle_stage_client.py tests/test_video_production_service.py tests/test_video_production_api.py tests/test_video_production_mocked_e2e.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 2: Run dy_auto frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js
```

Expected: PASS.

- [ ] **Step 3: Run Pixelle tests**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_files_security.py -q
```

Expected: PASS.

- [ ] **Step 4: Run static diff checks**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git diff --check
cd D:\devWorkspace\Pixelle-Video
git diff --check
```

Expected: no whitespace errors. CRLF warnings are acceptable on this Windows workspace.

- [ ] **Step 5: Manual smoke**

Run dy_auto and Pixelle locally with mock image model configured. In the browser:

```text
Series detail -> Lock style if needed -> Start next episode -> lands on /ai-video-review?run_id=...
```

Expected:

- A production run is created.
- Image stage starts.
- Review center loads.
- A review-pending image asset appears after sync.
- Approving the latest asset succeeds.

- [ ] **Step 6: Final commit**

If all verification passes:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short
git add server/app/db_models.py server/alembic/versions/9f1a2b3c4d5e_add_video_production_tables.py server/app/services/runtime_model_config.py server/app/services/audit_gate.py server/app/services/pixelle_stage_client.py server/app/services/video_production_service.py server/app/routers/video_production.py server/app/routers/pipeline.py server/app/routers/audit.py server/app/routers/pixelle.py server/app/main.py server/tests/conftest.py server/tests/test_video_production_models.py server/tests/test_pipeline_saved_storyboard_compat.py server/tests/test_pixelle_config_security.py server/tests/test_audit_gate.py server/tests/test_runtime_model_config.py server/tests/test_pixelle_stage_client.py server/tests/test_video_production_service.py server/tests/test_video_production_api.py server/tests/test_video_production_mocked_e2e.py web/src/api/videoProduction.js web/src/views/AIVideoReviewPage.vue web/src/views/SeriesDetailPage.vue web/src/views/PipelineMonitorPage.vue web/src/router/index.js web/src/constants/navigation.js web/src/__tests__/api-clients.test.js
git commit -m "feat: add Pixelle image-stage production wedge"
```

Commit Pixelle separately:

```powershell
cd D:\devWorkspace\Pixelle-Video
git status --short
git add api/middleware.py api/routers/files.py api/tasks/models.py api/schemas/stages.py api/routers/stages.py api/routers/__init__.py api/app.py tests/test_stage_api_auth.py tests/test_files_security.py tests/test_stage_images_api.py
git commit -m "feat: add authenticated image stage API"
```

---

## Self-Review

Spec coverage:

- Phase 0 trust/security/contracts: covered by Tasks 1-7 and 14.
- Saved storyboard pipeline compatibility: covered by Task 2.
- Secret redaction: covered by Task 5.
- Pixelle stage auth and file safety: covered by Task 6.
- Runtime model config delivery: covered by Tasks 3 and 7.
- Image-stage submit and asset persistence: covered by Tasks 8-10.
- Human review center: covered by Tasks 9, 12, and 13.
- Single-image regeneration/latest-version invariant: covered by Task 11.
- Video segment and compose stages: intentionally deferred to later plans.

Placeholder scan:

- No unresolved placeholder markers.
- No undefined route names.
- No test step says only "write tests"; every test task includes concrete test code.

Type consistency:

- Run model name: `VideoProductionRun`.
- Asset model name: `VideoProductionAsset`.
- Review model name: `VideoReviewRecord`.
- Runtime config resolver: `resolve_runtime_model_config`.
- Pixelle stage client: `submit_image_batch`, `get_stage_task`.
- dy_auto API prefix: `/api/video-production`.
- Pixelle stage prefix: `/api/stages`.
