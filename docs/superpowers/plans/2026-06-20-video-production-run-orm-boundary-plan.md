# VideoProductionRun ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `VideoProductionRun` into the video production ORM module without breaking legacy imports.

**Architecture:** The canonical SQLAlchemy class lives in `app.db.models.video_production`. `app.db_models` remains a compatibility barrel that imports and re-exports the class. Owner-domain services import the class from the canonical module.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Boundary Test

**Files:**
- Modify: `server/tests/test_video_production_orm_boundary.py`

- [ ] **Step 1: Add `VideoProductionRun` to the boundary assertions**

```python
from app.db_models import VideoProductionRun as LegacyVideoProductionRun
from app.db.models.video_production import VideoProductionRun

assert VideoProductionRun is LegacyVideoProductionRun
assert VideoProductionRun.metadata is Base.metadata
assert VideoProductionRun.__module__ == "app.db.models.video_production"
assert "video_production_runs" in Base.metadata.tables
```

- [ ] **Step 2: Run the boundary test and verify it fails before migration**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py -q`

Expected: FAIL because `VideoProductionRun` is not exported from `app.db.models.video_production` yet.

### Task 2: ORM Class Move

**Files:**
- Modify: `server/app/db/models/video_production.py`
- Modify: `server/app/db_models.py`

- [ ] **Step 1: Move the existing class body**

Move this class unchanged from `server/app/db_models.py` to `server/app/db/models/video_production.py`:

```python
class VideoProductionRun(Base):
    """One staged automated production attempt for an episode."""
    __tablename__ = "video_production_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(40), nullable=False, default="draft")
    current_stage = Column(String(40), nullable=False, default="draft")
    run_type = Column(String(40), nullable=False, default="legacy_episode_run")
    pixelle_stage_task_id = Column(String(100), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_link_status = Column(String(30), nullable=False, default="legacy_unlinked")
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
        Index("idx_video_production_runs_type", "run_type"),
        Index("idx_video_production_runs_production_links", "production_plan_id", "production_episode_id"),
        Index("idx_video_production_runs_link_status", "production_link_status"),
    )
```

- [ ] **Step 2: Re-export from the legacy barrel**

Add `VideoProductionRun` to the existing `from app.db.models.video_production import (...)` import list in `server/app/db_models.py`.

### Task 3: Owner-Domain Imports

**Files:**
- Modify video production domain files that currently import `VideoProductionRun` from `app.db_models`.

- [ ] **Step 1: Import `VideoProductionRun` from the canonical module in owner code**

For each file under `server/app/domains/video_production`, remove `VideoProductionRun` from `app.db_models` imports and add it to the `app.db.models.video_production` import.

- [ ] **Step 2: Verify no owner-domain residual imports remain**

Run: `rg -n "from app\.db_models import .*VideoProductionRun|from app\.db_models import VideoProductionRun\b" server/app/domains/video_production -g "*.py"`

Expected: no output.

### Task 4: Verification

**Files:**
- Test only.

- [ ] **Step 1: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py server/tests/test_video_production_run_type.py server/tests/test_video_production_service.py server/tests/test_video_production_real_worker_step.py server/tests/test_production_gate_evaluator.py -q`

Expected: all selected tests pass.

- [ ] **Step 2: Check diff whitespace**

Run: `git diff --check -- server/app/db_models.py server/app/db/models/video_production.py server/app/domains/video_production server/tests/test_video_production_orm_boundary.py docs/superpowers/specs/2026-06-20-video-production-run-orm-boundary-design.md docs/superpowers/plans/2026-06-20-video-production-run-orm-boundary-plan.md`

Expected: no output and exit code 0.

### Task 5: Commit

**Files:**
- Stage only files changed in this plan.

- [ ] **Step 1: Commit the migration**

Run:

```powershell
git add docs/superpowers/specs/2026-06-20-video-production-run-orm-boundary-design.md docs/superpowers/plans/2026-06-20-video-production-run-orm-boundary-plan.md server/app/db_models.py server/app/db/models/video_production.py server/app/domains/video_production/mock_scale_scheduler_service.py server/app/domains/video_production/one_sentence_video_service.py server/app/domains/video_production/production_cost_summary_service.py server/app/domains/video_production/production_gate_evaluator.py server/app/domains/video_production/production_review_service.py server/app/domains/video_production/production_retry_service.py server/app/domains/video_production/production_run_service.py server/app/domains/video_production/production_worker_service.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/video_production_service.py server/app/domains/video_production/video_production_state.py server/tests/test_video_production_orm_boundary.py
git commit --only -m "refactor: move video production run model into db domain" -- docs/superpowers/specs/2026-06-20-video-production-run-orm-boundary-design.md docs/superpowers/plans/2026-06-20-video-production-run-orm-boundary-plan.md server/app/db_models.py server/app/db/models/video_production.py server/app/domains/video_production/mock_scale_scheduler_service.py server/app/domains/video_production/one_sentence_video_service.py server/app/domains/video_production/production_cost_summary_service.py server/app/domains/video_production/production_gate_evaluator.py server/app/domains/video_production/production_review_service.py server/app/domains/video_production/production_retry_service.py server/app/domains/video_production/production_run_service.py server/app/domains/video_production/production_worker_service.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/video_production_service.py server/app/domains/video_production/video_production_state.py server/tests/test_video_production_orm_boundary.py
```
