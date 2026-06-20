# Video Production Service Final Domain Design

## Context

`server/app/services/video_agency_team.py` and
`server/app/services/video_production_service.py` are the remaining service-layer
business implementations. They keep the service implementation inventory from
reaching zero and force domain modules to import orchestration code through
`app.services`.

## Decision

Move `video_agency_team.py` to
`app.domains.agency_operations.video_agency_team` and move
`video_production_service.py` to
`app.domains.video_production.video_production_service`. Keep both legacy
`app.services.*` modules as compatibility facades that alias the domain modules.

The migration preserves the current working-tree behavior of both services,
including the story planning role in the agency team and the current production
stage, audit, creative-patch, backtrack, prompt-composition, and storyboard
image bridge behavior in video production.

## Scope

- Remove all remaining service implementation allowlist entries.
- Replace domain callers of `app.services.video_agency_team` and
  `app.services.video_production_service` with direct domain imports.
- Replace service-local dependencies inside the moved implementations with
  domain imports where the target domain already exists.
- Keep test monkeypatch compatibility for legacy service import paths through
  module alias facades.
- Register both moved modules in their domain READMEs.

## Non-Goals

- Do not change video production API routes, response shapes, statuses, or stage
  semantics.
- Do not remove legacy service import compatibility for tests and older callers.
- Do not clean unrelated dirty files or staged changes outside this migration.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py server/tests/test_domain_service_import_inventory.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_orchestrator.py server/tests/test_agency_console.py server/tests/test_series_style_lock_pipeline.py server/tests/test_video_production_service.py server/tests/test_video_production_linked_stage_execution.py server/tests/test_video_production_real_short_mocked_e2e.py server/tests/test_video_production_real_worker_step.py -q
```
