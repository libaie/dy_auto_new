# AI Video Series Episode Asset Scope Service Domain Design

Status: auto-approved.

## Goal

Move `app.services.episode_asset_scope_service` into the `ai_video_series`
domain because episode-level character and scene scope normalization is part of
multi-episode story planning, not a generic shared service.

## Domain Boundary

The new domain-owned implementation is:

- `app.domains.ai_video_series.episode_asset_scope_service`
- `episode_asset_scope_service.py`

It owns:

- `EpisodeAssetScopeError`
- `normalize_episode_asset_scope`
- generated character and scene fallback/validation helpers

## Compatibility

Keep `app.services.episode_asset_scope_service` as a thin `sys.modules` facade
to `app.domains.ai_video_series.episode_asset_scope_service`. Legacy imports
and tests must resolve to the same module object during migration.

## Scope

This migration does not change normalization behavior, generated asset metadata,
database models, or public API responses. It updates the already-domain-owned
`series_planning_service` to import the domain path.

## Exit Criteria

- `server/app/domains/ai_video_series/episode_asset_scope_service.py` exists.
- `server/app/services/episode_asset_scope_service.py` is a <=20 line facade.
- Legacy and domain imports resolve to the same module object.
- `series_planning_service.py` imports the domain service path.
- Existing episode asset scope and series planning tests pass.
