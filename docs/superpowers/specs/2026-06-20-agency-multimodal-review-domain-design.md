# Agency Multimodal Review Domain Design

## Context

`server/app/services/agency_multimodal_review.py` builds asset review context
and dispatches image/video multimodal agency reviews. It is agency review
workflow logic and is called by the agency router.

## Decision

Move the module to `app.domains.agency_operations.agency_multimodal_review`.
Keep `app.services.agency_multimodal_review` as a compatibility facade so
existing tests and monkeypatch paths keep working while related agency services
are still dirty.

## Scope

- Preserve `build_multimodal_asset_context` and `run_multimodal_asset_review`.
- Update the agency router to import the domain helper directly.
- Keep legacy module alias compatibility.
- Document the module and facade in the agency README.

## Non-Goals

- Do not migrate `agency_orchestrator.py` in this slice.
- Do not change model config resolution or review behavior.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_multimodal_review_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_multimodal_review.py -q
```
