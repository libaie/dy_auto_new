# Agency Creative Patch Contracts Domain Design

## Context

`server/app/services/agency_creative_patch_contracts.py` owns creative patch
types, target contracts, Pydantic validation, and `normalize_patch_payload`.
This is agency contract logic and belongs with the agency operations domain.

## Decision

Move the contracts to
`app.domains.agency_operations.agency_creative_patch_contracts`. Keep
`app.services.agency_creative_patch_contracts` as a compatibility facade while
dirty creative patch service code still imports the legacy path.

## Scope

- Preserve `CreativePatchProposal`, enum contracts, and
  `normalize_patch_payload`.
- Preserve the current guard that rejects patches whose `after` payload has no
  executable allowed field.
- Document the new domain module and legacy facade.
- Add a focused facade boundary test.

## Non-Goals

- Do not migrate `agency_creative_patch_service.py` in this slice.
- Do not redesign creative patch workflow or approval state.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_creative_patch_contracts_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_creative_patch_contracts.py -q
```
