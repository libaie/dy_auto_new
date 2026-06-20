# Agency Runtime Domain Design

## Context

`server/app/services/agency_runtime.py` runs agency experts against
OpenAI-compatible chat-completion providers. It loads expert prompts, validates
model responses, redacts secrets, normalizes optional scorecards, and returns
`AgencyRuntimeResult`. This is agency operations behavior and should live with
the rest of the agency domain.

## Decision

Move the implementation to `app.domains.agency_operations.agency_runtime`. Keep
`app.services.agency_runtime` as a compatibility facade while orchestrator,
story generator, script pipeline, one-sentence video, and legacy tests still use
the old import path.

The new domain module should import agency helpers from
`app.domains.agency_operations` and runtime model config from
`app.domains.model_configuration`.

## Scope

- Preserve `AgencySkillRuntime`, `AgencyRuntimeError`,
  `AgencyRuntimeResult`, `_default_model_client`, and parsing/redaction helpers.
- Preserve support for structured multimodal user message content.
- Preserve optional `creative_patches` and normalized `scorecard` fields in
  `output_summary`.
- Remove `agency_runtime.py` from the service implementation inventory.
- Register the domain module and legacy facade in the agency operations README.

## Non-Goals

- Do not migrate `agency_orchestrator.py`, `one_sentence_video_service.py`, or
  script pipeline callers in this slice.
- Do not change provider compatibility, HTTP request payloads, timeout handling,
  or secret-redaction rules.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_runtime.py server/tests/test_agency_orchestrator.py -q
```
