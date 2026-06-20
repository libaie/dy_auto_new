# AI Text Artifact Ledger Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the backend foundation for versioned, editable, approvable, and consumable AI text artifacts.

**Architecture:** Add `AITextArtifact` and `AITextArtifactConsumer` SQLAlchemy models, then expose a small service that creates versions, creates human edits as child versions, approves one active version per target/type, and binds exact artifact versions to production consumers. This first slice does not add UI or public APIs.

**Tech Stack:** SQLAlchemy, pytest, Alembic.

---

## File Map

- Modify `server/app/db_models.py`
  - Add `AITextArtifact`.
  - Add `AITextArtifactConsumer`.
- Create `server/app/services/ai_text_artifact_service.py`
  - Own version creation, edit, approve, lineage, and consumer binding.
- Modify `server/tests/conftest.py`
  - Include new tables in cleanup imports.
- Create `server/tests/test_ai_text_artifact_service.py`
  - Service tests for versioning, edit lineage, approval superseding, and consumer binding.
- Create `server/alembic/versions/4e5f60718293_add_ai_text_artifacts.py`
  - Add the two new tables and indexes.

## Task 1: Service Contract Tests

- [ ] **Step 1: Write failing tests**

Test these behaviors:

```python
artifact = service.create_artifact(...)
edited = service.edit_artifact(artifact.id, content_text="manual edit", actor_user_id="u1")
approved = service.approve_artifact(edited.id, actor_user_id="u1")
service.bind_consumer(approved.id, consumer_type="video_run", consumer_id="run-1")
```

Expected assertions:

- first artifact version is 1
- edit creates version 2 with `source_type="human_edit"` and parent id
- approving version 2 supersedes version 1
- only version 2 remains `approved`
- consumer row binds exact artifact id

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_service.py -q
```

Expected: FAIL because the service/model does not exist.

## Task 2: Model and Service Implementation

- [ ] **Step 1: Add models**

Add `AITextArtifact` and `AITextArtifactConsumer` near the existing agency/production trace models.

- [ ] **Step 2: Add service**

Implement explicit functions:

- `create_artifact`
- `edit_artifact`
- `approve_artifact`
- `bind_consumer`
- `list_versions`

- [ ] **Step 3: Verify GREEN**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_service.py -q
```

Expected: PASS.

## Task 3: Migration

- [ ] **Step 1: Add Alembic revision**

Create the two tables with indexes matching the model.

- [ ] **Step 2: Run targeted tests again**

Run service tests plus the placeholder foundation tests.

## Self-Review

Covered:

- versioned text artifacts
- manual edit child version
- approval and supersede semantics
- exact consumer binding

Not covered yet:

- public artifact API
- migration from existing snapshots
- artifact workbench UI
- production start gate requiring approved artifacts
- regenerate through a real model provider
