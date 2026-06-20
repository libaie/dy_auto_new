# Pixelle Execution Service Domain Design

## Context

`server/app/services/pixelle_execution_service.py` builds Pixelle video stage
frame payloads. The current staged behavior adds `input_image_url` to that
payload. This helper is Pixelle payload mapping, not video production
orchestration, so it fits `app.domains.pixelle_integration`.

## Decision

Move `build_video_stage_frame` and its private payload helpers to
`app.domains.pixelle_integration.pixelle_execution_service`. Keep
`app.services.pixelle_execution_service` as a compatibility facade.

## Scope

- Preserve current payload behavior, including `input_image_url`.
- Import production status constants from
  `app.domains.video_production.production_status`.
- Document the domain module and legacy facade in the Pixelle README.
- Add a focused facade and behavior test.

## Non-Goals

- Do not move video production orchestration.
- Do not change Pixelle stage submission clients.
- Do not update existing continuity tests in this slice.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_execution_service_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_production_segment_continuity.py -q
```
