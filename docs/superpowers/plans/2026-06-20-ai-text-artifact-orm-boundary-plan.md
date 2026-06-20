# AI Text Artifact ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move AI text artifact ORM class bodies out of `app.db_models`.

**Architecture:** Add `AITextArtifact` and `AITextArtifactConsumer` to `app.db.models.ai_text_artifacts`, keep legacy re-exports in `app.db_models`, and update the owner domain service/router to import the domain model path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest AI text artifact domain boundary tests.

---

### Task 1: AI Text Artifact ORM Boundary

**Files:**
- Create: `server/tests/test_ai_text_artifact_orm_boundary.py`
- Create: `server/app/db/models/ai_text_artifacts.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/db/models/ai_video_series.py`
- Modify: `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py`
- Modify: `server/app/domains/ai_text_artifacts/ai_text_artifacts_router.py`
- Modify: `server/app/domains/ai_text_artifacts/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.ai_text_artifacts.AITextArtifact` and
`AITextArtifactConsumer` to exist and match the legacy `app.db_models`
exports.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError` for the missing model module.

- [x] **Step 3: Move the class bodies**

Create `server/app/db/models/ai_text_artifacts.py`, import both classes in
`server/app/db_models.py`, and remove the old class bodies.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.ai_text_artifacts` in the AI text artifact service/router
and update the domain README.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_orm_boundary.py server/tests/test_ai_text_artifacts_domain_boundary.py server/tests/test_ai_text_artifact_service_domain_facade.py server/tests/test_ai_video_series_orm_boundary.py -q
```
