# AI Video Series Planning Service Domain Plan

Status: auto-approved.

## Success Criteria

`series_planning_service` implementation lives under
`app.domains.ai_video_series`, while old imports keep working through a thin
facade.

## Steps

1. Add boundary and facade tests.
   Verify: spec/plan mention `app.domains.ai_video_series.series_planning_service`,
   `app.services.series_planning_service`, `generate_series_story_plan`,
   `ensure_episode_placeholders`, `ensure_series_continuity_artifacts`, and
   `generate_story_plan_with_expert`.

2. Verify red state.
   Verify: tests fail because the domain service module does not exist and the
   old service file still contains implementation code.

3. Move implementation.
   Verify: copy the current worktree implementation into
   `server/app/domains/ai_video_series/series_planning_service.py` and replace
   `server/app/services/series_planning_service.py` with a `sys.modules` facade.

4. Update domain-owned imports.
   Verify: `router.py` and `story_planning.py` import the domain service path
   instead of the legacy service path.

5. Run focused regression.
   Verify: new boundary tests plus `test_series_planning_service.py`,
   `test_series_api.py`, and selected style-lock/story-plan tests pass.
