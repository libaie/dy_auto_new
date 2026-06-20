# Agency Repair Executor Domain Design

## Context

`server/app/services/agency_repair_executor.py` executes agency auto-repair
production jobs. It updates repair audit events, blocks paid reference repairs,
and sends segment-level failures back to image generation after prompt
micro-tuning. That is agency operations behavior, not generic service-layer
infrastructure.

## Decision

Move the implementation to
`app.domains.agency_operations.agency_repair_executor`. Keep
`app.services.agency_repair_executor` as a compatibility facade while
`production_worker_service.py` and legacy tests still import the old path.

The new domain module should import already-migrated video production helpers
from `app.domains.video_production`, including queueing, action results, and
status constants.

## Scope

- Preserve `execute_repair_job` and `is_agency_repair_stage` behavior.
- Preserve segment prompt micro-tuning, downstream image generation enqueueing,
  run-stage rollback, and manual-reference blocking.
- Remove `agency_repair_executor.py` from the service implementation inventory.
- Register the domain module and legacy facade in the agency operations README.

## Non-Goals

- Do not migrate `production_worker_service.py` in this slice.
- Do not change repair stages, audit payloads, cost gates, or job retry policy.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_repair_executor.py server/tests/test_agency_repair_worker.py -q
```
