# Agency Backtrack Policy Domain Design

## Context

`server/app/services/agency_backtrack_policy.py` counts repeated review
failures and enqueues upstream auto-repair jobs. That is agency repair policy
logic, so it belongs in `agency_operations`.

## Decision

Move backtrack policy to `app.domains.agency_operations.agency_backtrack_policy`.
Keep `app.services.agency_backtrack_policy` as a compatibility facade while
dirty video production service code still imports the legacy path.

## Scope

- Preserve `trigger_backtrack_if_needed` behavior.
- Preserve current production queue handoff through the existing queue helper.
- Add a domain module, legacy facade, README registration, and focused facade
  test.

## Non-Goals

- Do not migrate `video_production_service.py` in this slice.
- Do not change backtrack thresholds, job stages, or audit payloads.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_backtrack_policy_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_backtrack_policy.py -q
```
