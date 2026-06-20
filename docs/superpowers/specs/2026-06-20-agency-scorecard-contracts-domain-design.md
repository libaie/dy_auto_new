# Agency Scorecard Contracts Domain Design

## Context

`server/app/services/agency_scorecard_contracts.py` owns agency scorecard
normalization and blocking verdict helpers. This is agency contract logic, not
generic service infrastructure, so it belongs under `agency_operations`.

## Decision

Move scorecard contracts to
`app.domains.agency_operations.agency_scorecard_contracts`. Keep
`app.services.agency_scorecard_contracts` as a compatibility facade because
dirty agency service modules still import the legacy path.

## Scope

- Preserve `normalize_scorecard` and `scorecard_blocks_stage` behavior.
- Add a domain module and a legacy alias facade.
- Document the module and facade in the agency operations README.
- Add a focused boundary test.

## Non-Goals

- Do not migrate `agency_runtime.py` or `agency_debate_audit.py` in this slice.
- Do not redesign scorecard schema or verdict rules.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_scorecard_contracts_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_scorecard_contracts.py -q
```
