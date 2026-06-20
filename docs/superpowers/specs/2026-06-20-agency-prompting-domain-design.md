# Agency Prompting Domain Design

## Context

`server/app/services/agency_prompting.py` builds expert system prompts and user
payloads for the agency runtime. It is agency boundary logic and should live
with the rest of `agency_operations`.

## Decision

Move prompt construction to `app.domains.agency_operations.agency_prompting`.
Keep `app.services.agency_prompting` as a compatibility facade while dirty
agency runtime tests and service modules still import the legacy path.

## Scope

- Preserve `ExpertPrompt` and `build_expert_prompt`.
- Preserve current prompt rules for `creative_patches` and `scorecard`.
- Preserve multimodal `image_url` and `video_url` user content parts.
- Document the domain module and legacy facade.

## Non-Goals

- Do not migrate `agency_runtime.py` in this slice.
- Do not commit the larger `server/tests/test_agency_runtime.py` WIP in this
  slice.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_prompting_facade.py -q
```
