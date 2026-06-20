# Agency Orchestrator Domain Design

## Context

`server/app/services/agency_orchestrator.py` owns staged expert review
orchestration: `STAGE_DAG`, `AgencyOrchestrator`, invocation persistence,
runtime execution, stage status aggregation, and optional debate audit merging.
This is agency operations domain behavior.

## Decision

Move the implementation to `app.domains.agency_operations.agency_orchestrator`.
Keep `app.services.agency_orchestrator` as a compatibility facade while dirty
service modules and legacy tests still import or monkeypatch the old path.

Domain callers should use the new domain import directly. The migrated
orchestrator should import manifest, persistence, runtime, and debate helpers
from `app.domains.agency_operations`.

## Scope

- Preserve `STAGE_DAG`, `AgencyOrchestrator`, `_hash_context`, debate audit
  merging, story-planning review, and `enable_debate` behavior.
- Move domain callers from `app.services.agency_orchestrator` to
  `app.domains.agency_operations.agency_orchestrator`.
- Remove `agency_orchestrator.py` from the service implementation inventory.
- Remove no-longer-needed agency orchestrator entries from the domain service
  import inventory.
- Register the domain module and legacy facade in the agency operations README.

## Non-Goals

- Do not migrate dirty service modules such as `one_sentence_video_service.py`
  or `video_production_service.py` in this slice.
- Do not change stage DAG semantics, runtime invocation behavior, or debate
  audit payloads.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_orchestrator.py server/tests/test_agency_console.py server/tests/test_agency_multimodal_review.py server/tests/test_script_pipeline.py -q
```
