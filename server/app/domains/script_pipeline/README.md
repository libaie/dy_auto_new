# Script Pipeline Domain

This domain owns the legacy script-to-video pipeline HTTP routes and script
generation pipeline runtime.

## Owned Routes

- `/api/pipeline/*`

## Not Owned

- Database session helpers stay in `app.database`.
- Role dependencies stay in `app.deps`.
- Series authoring, AI text artifact, director, and video production routes stay
  in their own routers or domains.

## Current Modules

- `pipeline_router.py` owns `PipelineStartRequest`, `/api/pipeline/*` route
  handlers, `_submit_and_poll`, `_run_all_layers`, run serialization, agency
  trace status helpers, and route-local Pixelle pipeline orchestration helpers.
- `script_pipeline_service.py` owns `DynamicPromptBuilder`,
  `ScriptGenerationPipeline`, `PipelineManager`, script generation retries,
  structured script persistence, episode snapshots, and AI text artifact
  publication.
- `storyboard_timing.py` owns `annotate_storyboard_with_timing`, shot duration
  normalization, timed storyboard line rendering, and detailed image/video
  prompt timing text.
- `app.db.models.script_pipeline` owns `PipelineRun`, `EpisodeScript`,
  `ScriptDramaticBeat`, `ScriptSceneOutline`, and `ScriptVisualShot` ORM class
  bodies.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Keep the script pipeline service runtime independent from `pipeline_router`.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
