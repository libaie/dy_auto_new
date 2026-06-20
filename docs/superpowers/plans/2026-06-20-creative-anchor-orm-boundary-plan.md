# Creative Anchor ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move creative anchor ORM class bodies out of `app.db_models`.

**Architecture:** Add `CharacterAnchor` and `SceneAnchor` to `app.db.models.creative_library`, keep legacy re-exports in `app.db_models`, and update the creative anchor service to import the domain model path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest creative-library anchor tests.

---

### Task 1: Creative Anchor ORM Boundary

**Files:**
- Create: `server/tests/test_creative_library_anchor_orm_boundary.py`
- Modify: `server/app/db/models/creative_library.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/creative_library/anchor_service.py`
- Modify: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.creative_library.CharacterAnchor` and `SceneAnchor` to
exist and match the legacy `app.db_models` exports.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_anchor_orm_boundary.py -q
```

Expected: FAIL with `ImportError` for the missing anchor ORM exports.

- [x] **Step 3: Move the class bodies**

Add the anchor ORM classes to `server/app/db/models/creative_library.py`,
import them in `server/app/db_models.py`, and remove the old class bodies.

- [x] **Step 4: Update production imports and docs**

Use `app.db.models.creative_library.CharacterAnchor` and `SceneAnchor` in
`anchor_service.py`, and record the boundary in the creative-library README.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_anchor_orm_boundary.py server/tests/test_asset_anchor_models.py server/tests/test_anchor_service.py server/tests/test_reference_asset_service.py -q
```
