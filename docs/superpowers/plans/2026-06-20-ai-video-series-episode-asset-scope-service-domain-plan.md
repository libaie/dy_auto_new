# AI Video Series Episode Asset Scope Service Domain Plan

Status: auto-approved.

## Success Criteria

Episode asset scope normalization lives under
`app.domains.ai_video_series.episode_asset_scope_service`, while old imports
keep working through a thin facade.

## Steps

1. Add boundary and facade tests.
   Verify: spec/plan mention `app.domains.ai_video_series.episode_asset_scope_service`,
   `app.services.episode_asset_scope_service`, `EpisodeAssetScopeError`, and
   `normalize_episode_asset_scope`.

2. Verify red state.
   Verify: tests fail because the domain service module does not exist and the
   old service file still contains implementation code.

3. Move implementation.
   Verify: copy the current service implementation into the domain and replace
   the legacy service with a `sys.modules` facade.

4. Update domain-owned imports.
   Verify: `series_planning_service.py` imports
   `app.domains.ai_video_series.episode_asset_scope_service`.

5. Run focused regression.
   Verify: new boundary tests plus existing episode asset scope and series
   planning tests pass.
