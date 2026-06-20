# Video Production Service Final Domain Implementation Plan

> **Auto-approved spec:** Per user instruction, all specs are approved by
> default. Execute without pausing for approval.

**Goal:** Remove the final business implementations from `server/app/services`
while preserving legacy import compatibility.

**Architecture:** `agency_operations.video_agency_team` owns agency team
definitions. `video_production.video_production_service` owns staged production
orchestration. `app.services.video_agency_team` and
`app.services.video_production_service` are module-alias facades.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove remaining implementation allowlist entries**

Set the non-facade, mixed-facade, and target-domain inventories to empty.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL while the two services are still implementations.

### Task 2: Move Agency Team

**Files:**
- Create: `server/app/domains/agency_operations/video_agency_team.py`
- Modify: `server/app/services/video_agency_team.py`
- Modify: domain callers of `app.services.video_agency_team`
- Modify: `server/app/domains/agency_operations/README.md`
- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Move the current implementation**

Move the working-tree implementation into
`app.domains.agency_operations.video_agency_team`.

- [ ] **Step 2: Point dependencies and domain callers at domain paths**

Use `app.domains.agency_operations.agency_manifest` inside the moved module and
update domain callers to import `video_agency_team` directly from
`app.domains.agency_operations`.

- [ ] **Step 3: Replace the legacy service with a facade**

Use the existing module-alias facade pattern so legacy tests and monkeypatches
continue to resolve to the same module object.

### Task 3: Move Production Service

**Files:**
- Create: `server/app/domains/video_production/video_production_service.py`
- Modify: `server/app/services/video_production_service.py`
- Modify: domain callers of `app.services.video_production_service`
- Modify: `server/app/domains/video_production/README.md`
- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Move the current implementation**

Move the working-tree implementation into
`app.domains.video_production.video_production_service`.

- [ ] **Step 2: Replace moved service dependencies with domain imports**

Use direct domain imports for audit gate, agency backtrack and creative patch
helpers, agency orchestrator, Pixelle stage client, production status/helpers,
runtime model config, provider capability, production observability, and run
types.

- [ ] **Step 3: Replace the legacy service with a facade**

Use the existing module-alias facade pattern to preserve old imports and
monkeypatch targets.

### Task 4: Verify and Commit

- [ ] **Step 1: Run inventory and focused regression tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py server/tests/test_domain_service_import_inventory.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_orchestrator.py server/tests/test_agency_console.py server/tests/test_series_style_lock_pipeline.py server/tests/test_video_production_service.py server/tests/test_video_production_linked_stage_execution.py server/tests/test_video_production_real_short_mocked_e2e.py server/tests/test_video_production_real_worker_step.py -q
```

- [ ] **Step 2: Commit target files only**

Commit the spec, plan, inventories, moved domain modules, facades, domain caller
imports, and README updates without staging unrelated files.
