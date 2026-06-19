# AI Video Series Planning Service Domain Design

Status: auto-approved.

## Goal

Move `app.services.series_planning_service` into the `ai_video_series` domain as
the first Phase 2 service-layer migration. This reduces the flat
`app/services` surface while preserving legacy imports and monkeypatch behavior.

## Domain Boundary

The new domain-owned implementation is:

- `app.domains.ai_video_series.series_planning_service`
- `series_planning_service.py`

It owns the current series planning public API:

- `EpisodePlaceholderResult`
- `ContinuityArtifactResult`
- `SeriesStoryPlanResult`
- `ensure_episode_placeholders`
- `ensure_series_continuity_artifacts`
- `generate_series_story_plan`
- `is_series_completed`
- `next_episode_number`

It also owns current helper seams used by tests and monkeypatches, including
`generate_story_plan_with_expert` and episode outline normalization helpers.

## Compatibility

Keep `app.services.series_planning_service` as a thin `sys.modules` facade to
`app.domains.ai_video_series.series_planning_service`. The legacy import and
domain import must return the same module object so existing tests that patch
`app.services.series_planning_service.generate_story_plan_with_expert` still
patch the real implementation.

## Scope

This migration does not change production behavior, database tables, artifact
schemas, public API paths, or service call signatures.

This migration updates domain-owned modules to import the domain service path.
Dirty orchestration services such as `production_run_service.py` and
`one_sentence_video_service.py` may keep using the legacy facade until their own
domain migration slices.

## Exit Criteria

- `server/app/domains/ai_video_series/series_planning_service.py` exists.
- `server/app/services/series_planning_service.py` is a <=20 line facade with no
  business functions.
- Legacy and domain imports resolve to the same module object.
- Domain modules no longer import `app.services.series_planning_service`.
- Existing `test_series_planning_service.py` passes through the legacy facade.
