# AI Video Series Story Generator Expert Domain Design

## Context

`server/app/services/story_generator_expert.py` contains the story planning expert runtime used by multi-episode AI video series generation. The series planning service has already moved into `app.domains.ai_video_series`, but it still imports `generate_story_plan_with_expert` from the old service layer. That leaves core AI video series business behavior split across two ownership boundaries.

## Decision

Move the full implementation to `app.domains.ai_video_series.story_generator_expert` and keep `app.services.story_generator_expert` as a compatibility facade that aliases the domain module through `sys.modules`.

This keeps behavior unchanged while making the domain package own the story generator expert. Existing imports, tests, and monkeypatches that still use `app.services.story_generator_expert` continue to resolve to the same module object as the domain import.

## Scope

In scope:

- Create `server/app/domains/ai_video_series/story_generator_expert.py` with the existing implementation.
- Replace `server/app/services/story_generator_expert.py` with a thin compatibility facade.
- Update `server/app/domains/ai_video_series/series_planning_service.py` to import `generate_story_plan_with_expert` from `app.domains.ai_video_series.story_generator_expert`.
- Register the facade in `server/app/domains/ai_video_series/README.md`.
- Add focused boundary tests that prove the old and new import paths share the same module object and public runtime objects.

Out of scope:

- No behavior changes to `generate_story_plan_with_expert`.
- No model-provider changes.
- No changes to the story generator manifest, prompt content, persistence schema, API paths, or frontend.
- No cleanup of historical docs that reference the original service path.

## Architecture

The domain module owns:

- `StoryGeneratorResult`
- `StoryModelClientResponse`
- `StoryModelClient`
- `STORY_PLAN_OUTPUT_SCHEMA`
- `generate_story_plan_with_expert`
- the private prompt, parsing, provider-call, and persistence helper functions used by that runtime

The legacy module owns no business logic. It imports the domain module, replaces its own entry in `sys.modules`, and updates globals for compatibility with direct attribute access.

## Data Flow

`series_planning_service.generate_series_story_plan()` calls the domain `generate_story_plan_with_expert()`. The expert runtime still builds context from the `Series`, `Episode`, character IDs, scene IDs, and approved artifacts; calls the configured model client; parses and validates JSON; finalizes agency invocation/audit state; and returns `StoryGeneratorResult`.

## Error Handling

Error behavior is unchanged. HTTP, timeout, invalid JSON, and unexpected runtime errors still map to the existing `AgencyRuntimeError` codes and still finalize the agency invocation as failed.

## Testing

Add `server/tests/test_ai_video_series_story_generator_expert_facade.py` to verify:

- this spec and its implementation plan mention `app.domains.ai_video_series.story_generator_expert`, `app.services.story_generator_expert`, `generate_story_plan_with_expert`, and `StoryGeneratorResult`;
- the domain service file exists;
- the old service file is a thin facade and contains no copied expert runtime implementation;
- old and new imports are the same module object and expose the same key public objects;
- `series_planning_service.py` imports the domain path instead of the legacy service path;
- the AI video series README records the facade and cleanup gate.

Run the new boundary test together with existing story planning coverage:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_story_generator_expert_facade.py server/tests/test_series_planning_service.py server/tests/test_ai_video_series_domain_boundary.py -q
```
