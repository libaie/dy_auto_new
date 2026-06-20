# Video Production Plan Service Domain Design

## Context

`app.services.production_plan_service` converts locked series style and episode
storyboards into production plans, production episodes, scenes, shots, and
segments. It is the planning bridge into the video production control plane, but
it still lives in the generic services folder.

## Approved Approach

Move the implementation to
`app.domains.video_production.production_plan_service` and keep
`app.services.production_plan_service` as a temporary compatibility facade.
Update the clean director planning router imports and domain boundary docs to
use the domain path directly. Leave `production_run_service.py` and
`one_sentence_video_service.py` on the legacy path for now because both have
unrelated work in progress.

Inside the moved module, import production status constants from
`app.domains.video_production.production_status`.

## Boundaries

- Preserve `MAX_SEGMENT_SECONDS`, `DEFAULT_FRAME_SECONDS`, and all helper
  behavior including `_reference_roles`.
- Preserve `create_episode_production_plan`,
  `ensure_episode_production_plan`, and `ensure_shot_segments` behavior.
- Preserve existing callers that import `app.services.production_plan_service`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.production_plan_service`,
  `app.services.production_plan_service`, `create_episode_production_plan`, and
  `ensure_shot_segments`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def create_episode_production_plan`.
- Prove the moved service imports `production_status` from the domain path.
- Prove clean director planning router imports use the domain path.
- Prove the director planning README and same-day design spec name the domain
  plan service boundary.
- Run production plan behavior tests after migration.
