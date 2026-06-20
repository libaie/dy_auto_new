# VideoReviewRecord ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `VideoReviewRecord` into the video production ORM module without breaking legacy imports.

**Architecture:** The canonical review-record ORM class lives beside `VideoProductionAsset` in `app.db.models.video_production`. `app.db_models` remains the compatibility barrel. Owner-domain review and routing code imports the canonical class.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Boundary Test

**Files:**
- Modify: `server/tests/test_video_production_orm_boundary.py`

- [ ] **Step 1: Add `VideoReviewRecord` to boundary assertions**

```python
from app.db_models import VideoReviewRecord as LegacyVideoReviewRecord
from app.db.models.video_production import VideoReviewRecord

assert VideoReviewRecord is LegacyVideoReviewRecord
assert VideoReviewRecord.metadata is Base.metadata
assert VideoReviewRecord.__module__ == "app.db.models.video_production"
assert "video_review_records" in Base.metadata.tables
```

- [ ] **Step 2: Verify red**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py -q`

Expected: FAIL because `VideoReviewRecord` is not exported from `app.db.models.video_production` yet.

### Task 2: ORM Class Move

**Files:**
- Modify: `server/app/db/models/video_production.py`
- Modify: `server/app/db_models.py`

- [ ] **Step 1: Move the class body unchanged**

Move `class VideoReviewRecord(Base)` from `server/app/db_models.py` to `server/app/db/models/video_production.py` after `VideoProductionAsset`.

- [ ] **Step 2: Re-export from compatibility barrel**

Add `VideoReviewRecord` to the existing `from app.db.models.video_production import (...)` import list in `server/app/db_models.py`.

### Task 3: Owner-Domain Imports

**Files:**
- Modify: `server/app/domains/video_production/production_review_service.py`
- Modify: `server/app/domains/video_production/production_segment_detail_service.py`
- Modify: `server/app/domains/video_production/review_asset_edit_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/video_production_service.py`

- [ ] **Step 1: Move owner imports to the canonical module**

Remove `VideoReviewRecord` from `app.db_models` imports in each listed file and import it from `app.db.models.video_production`.

- [ ] **Step 2: Verify no owner-domain residual imports remain**

Run: `rg -n "from app\.db_models import .*VideoReviewRecord|from app\.db_models import VideoReviewRecord\b" server/app/domains/video_production -g "*.py"`

Expected: no output.

### Task 4: Verification

**Files:**
- Test only.

- [ ] **Step 1: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py server/tests/test_video_production_service.py server/tests/test_production_bulk_review.py server/tests/test_review_asset_edit_service.py server/tests/test_video_production_api.py server/tests/test_video_production_ai_audit_gate.py -q`

Expected: all selected tests pass.

- [ ] **Step 2: Check placeholders and whitespace**

Run: `rg -n "T[B]D|T[O]DO|implement [l]ater|fill in [d]etails|Similar to T[a]sk|Write tests for the [a]bove|appropriate error [h]andling|handle edge [c]ases" docs/superpowers/specs/2026-06-20-video-review-record-orm-boundary-design.md docs/superpowers/plans/2026-06-20-video-review-record-orm-boundary-plan.md server/tests/test_video_production_orm_boundary.py`

Expected: no output.

Run: `git diff --check -- server/app/db_models.py server/app/db/models/video_production.py server/app/domains/video_production server/tests/test_video_production_orm_boundary.py docs/superpowers/specs/2026-06-20-video-review-record-orm-boundary-design.md docs/superpowers/plans/2026-06-20-video-review-record-orm-boundary-plan.md`

Expected: no output and exit code 0.

### Task 5: Commit

**Files:**
- Stage and commit only files changed in this plan.

- [ ] **Step 1: Commit the migration**

Run:

```powershell
git add docs/superpowers/specs/2026-06-20-video-review-record-orm-boundary-design.md docs/superpowers/plans/2026-06-20-video-review-record-orm-boundary-plan.md server/app/db_models.py server/app/db/models/video_production.py server/app/domains/video_production/production_review_service.py server/app/domains/video_production/production_segment_detail_service.py server/app/domains/video_production/review_asset_edit_service.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/video_production_service.py server/tests/test_video_production_orm_boundary.py
git commit --only -m "refactor: move video review record model into db domain" -- docs/superpowers/specs/2026-06-20-video-review-record-orm-boundary-design.md docs/superpowers/plans/2026-06-20-video-review-record-orm-boundary-plan.md server/app/db_models.py server/app/db/models/video_production.py server/app/domains/video_production/production_review_service.py server/app/domains/video_production/production_segment_detail_service.py server/app/domains/video_production/review_asset_edit_service.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/video_production_service.py server/tests/test_video_production_orm_boundary.py
```
