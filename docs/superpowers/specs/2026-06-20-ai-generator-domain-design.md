# AI Generator Domain Design

## Context

`server/app/services/ai_generator.py` provides the shared `AiGeneratorService`
used for template generation, custom LLM calls, streaming responses, and app
shutdown cleanup. It is a model configuration and LLM access helper, so it
belongs with model configuration instead of the generic services folder.

## Decision

Move the implementation to `app.domains.model_configuration.ai_generator`.
Keep `app.services.ai_generator` as a compatibility facade while app startup,
domain callers, and legacy tests still import or monkeypatch the old path.

The new domain module should import sensitive-word content checks from
`app.domains.content_collection.content_service`.

## Scope

- Preserve `AiGeneratorService`, `SYSTEM_PROMPT`, and the shared
  `ai_generator` instance.
- Preserve custom, streaming, Anthropic, and OpenAI-compatible request paths.
- Preserve the current `request_timeout_seconds` option for `generate_custom`.
- Remove `ai_generator.py` from the service implementation inventory.
- Register the domain module and legacy facade in the model configuration
  README.

## Non-Goals

- Do not migrate all domain callers from `app.services.ai_generator` in this
  slice.
- Do not change model selection, prompt text, sensitive-word filtering, retry
  counts, or HTTP payload shapes.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_ai_generator.py -q
```
