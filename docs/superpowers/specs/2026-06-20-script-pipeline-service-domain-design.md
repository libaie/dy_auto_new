# Script Pipeline Service Domain Design

Status: auto-approved.

## Context

`app.domains.script_pipeline` already owns the `/api/pipeline/*` router, but the script generation pipeline runtime still lives in `app.services.script_pipeline`. The runtime owns prompt building, staged model execution, retries, persistence snapshots, and AI text artifact writes, so it belongs with the script pipeline domain rather than the flat service folder.

## Decision

Move the runtime implementation to `app.domains.script_pipeline.script_pipeline_service` and keep `app.services.script_pipeline` as a thin `sys.modules` compatibility facade.

This preserves existing imports and monkeypatches while making the domain package own both the HTTP router and its core generation runtime. The router remains in `pipeline_router.py`; the service remains router-free.

## Scope

In scope:

- Create `server/app/domains/script_pipeline/script_pipeline_service.py` with the current runtime implementation.
- Replace `server/app/services/script_pipeline.py` with a compatibility facade.
- Update `server/app/domains/script_pipeline/README.md` so it records service ownership, facade mapping, and cleanup gates.
- Update the existing script pipeline domain boundary test so it verifies the legacy service file remains router-free as a facade.
- Add focused tests proving old and new service imports are the same module object.

Out of scope:

- No behavior changes to `DynamicPromptBuilder`, `ScriptGenerationPipeline`, `PipelineManager`, prompt templates, retry rules, snapshot persistence, or AI text artifact writes.
- No changes to `/api/pipeline/*` routes.
- No changes to `production_run_service.py`; it can continue using the legacy facade until that file is clean enough to migrate.

## Architecture

The domain service owns:

- `DynamicPromptBuilder`
- `ScriptGenerationPipeline`
- `PipelineManager`
- `ScriptGenerationError`
- prompt payload helpers, stage ordering, runtime config resolution, persistence snapshots, and artifact publication

The legacy service module imports the domain service module, replaces itself in `sys.modules`, and updates globals so old imports and monkeypatches keep targeting the same module object.

The domain router remains separate in `app.domains.script_pipeline.pipeline_router` and must not be imported by the service runtime.

## Data Flow

Callers instantiate `PipelineManager` from either import path. The same domain module builds prompts from templates, runs the staged generation pipeline, persists structured script rows, writes episode snapshots, and publishes approved AI text artifacts through `AITextArtifactService`.

## Error Handling

Error behavior is unchanged. Stage failures still use `ScriptGenerationError`, retry and human-intervention behavior remain the same, and persisted run state is unchanged.

## Testing

Add `server/tests/test_script_pipeline_service_domain_facade.py` to verify:

- this spec and plan mention `app.domains.script_pipeline.script_pipeline_service`, `app.services.script_pipeline`, `DynamicPromptBuilder`, `ScriptGenerationPipeline`, and `PipelineManager`;
- the domain service file exists;
- the legacy service file is a thin facade with no copied runtime implementation;
- old and new imports resolve to the same module object and expose identical key public classes;
- the README records service ownership, facade mapping, and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_service_domain_facade.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_script_prompt_builder.py server/tests/test_script_pipeline.py -q
```
