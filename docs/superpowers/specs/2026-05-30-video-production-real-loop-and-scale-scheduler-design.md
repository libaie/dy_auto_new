<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260531-002540.md -->
# Video Production Real Loop And Scale Scheduler Design

## Summary

This phase builds the next hard boundary for dy_auto video production:

1. A real 60-90 second one-sentence-to-video loop with real provider calls, strict cost limits, and mandatory human review gates.
2. A 240-minute multi-episode mock scheduling track that validates long-form production stability without spending provider credits or generating a real 240-minute video file.

The phase keeps dy_auto as the control plane. Existing production services, review gates, assets, queues, and monitor pages should be reused and tightened instead of replaced.

## Confirmed Boundaries

### In Scope

- One-sentence production entry for a real 60-90 second sample video.
- Real image provider call for the short sample, using configured model center settings.
- Real image-to-video provider call for the short sample, using configured model center settings.
- Human approval required after image generation before video generation.
- Human approval required after video segment generation before final compose.
- Human final approval required before marking the run completed and library-ready.
- Cost and retry limits for the real provider path.
- Multi-episode mock scale scheduling for a total 240-minute production shape.
- Mock scale shape: 40 episodes x 6 minutes by default.
- Queue, lease, retry, failure injection, resume, and monitoring validation for the mock scale path.
- Clear UI labeling between real production runs and mock scheduling drills.

### Out Of Scope

- 3D expert console redesign.
- Douyin publishing loop.
- Real 240-minute provider execution.
- Real 240-minute final video composition.
- Automatic review approval.
- Automatic strategy self-optimization.
- Standalone BI analytics dashboard.
- Visual timeline editor.
- Large real-cost provider stress tests.
- Rebuilding the existing video production control plane from scratch.

## Product Goals

### Goal 1: Real One-Click Sample Video

The user can enter one sentence and produce a real short video through visible, auditable stages:

```text
Prompt
  -> series / episode / style lock / storyboard
  -> real image generation
  -> human image review gate
  -> real image-to-video generation
  -> human video segment review gate
  -> final compose
  -> human final review gate
  -> completed video asset in library
```

The first acceptance target is 60-90 seconds. The system should cap the number of real provider calls and stop safely when budget, model configuration, provider, review, or asset constraints are not satisfied.

### Goal 2: Long-Form Scheduling Stability

The user can create a mock long-form production plan totaling 240 minutes, for example 40 episodes x 6 minutes. The system validates scheduling and recovery under large scale without calling real providers.

The mock scale run should exercise:

- production plan creation
- scene / shot / segment decomposition
- job enqueueing
- job leasing
- retry after failure
- expired lease release
- interruption and resume
- review gate transitions
- monitor progress and exception visibility

### Product Success Metrics

This phase is successful only if it improves operator trust in "one sentence to video". Do not count a hidden backend run
or a mock-only drill as product success.

Required success metrics:

- A valid `真实短片` request can create a real provider-backed 60-90 second sample run from one sentence.
- The operator can always see the current stage, current gate, next allowed action, and blocked reason.
- No real provider call can happen without an explicit run type, model configuration, and budget guard.
- The final video can enter the library only after human final approval.
- A `模拟长剧调度` run can exercise the 240-minute production shape without any real provider call.
- The monitor can inspect the mock-scale run through aggregates and paginated detail without loading the whole tree.
- Every blocked production action returns a named, repairable reason rather than a generic failure.

### No-Go Conditions

Do not treat the phase as shippable if any of these are true:

- real-short duration outside 60-90 seconds creates partial database rows
- AI final audit can mark a real run completed without human final approval
- mock-scale execution can call a real provider client
- mock final compose markers can create or update real library assets
- readiness is missing from mutation responses touched by this phase
- primary production UI labels are still garbled or English on touched controls
- monitor loads the full mock production tree instead of bounded aggregate plus paginated detail
- provider preflight failure writes a provider task id

## Existing System To Reuse

The current repo already has most of the control-plane pieces needed for this phase:

- `server/app/services/one_sentence_video_service.py`
  - Creates one-sentence series, episode, style scaffold, storyboard, and production run.
- `server/app/services/video_production_service.py`
  - Owns video stage execution, review actions, final compose, final video persistence, and regeneration paths.
- `server/app/services/video_production_state.py`
  - Enforces image and video review gate prerequisites.
- `server/app/services/production_queue_service.py`
  - Provides queue, lease, retry, pause, and resume primitives.
- `server/app/services/production_plan_service.py`
  - Owns production plan / episode / scene / shot / segment structure.
- `server/app/services/production_segment_service.py`
  - Owns segment decomposition and continuity structure.
- `server/app/services/production_run_service.py`
  - Starts linked episode production runs.
- `server/app/services/production_status_aggregation.py`
  - Aggregates production state for monitoring.
- `web/src/views/OneSentenceVideoPage.vue`
  - Existing entry point for one-sentence production.
- `web/src/views/VideoProductionMonitorPage.vue`
  - Existing monitor surface for run, tree, exception segments, review blockers, and compose actions.

This phase should strengthen these modules instead of creating a parallel production stack.

## Implementation Architecture

Keep the implementation incremental. This phase should add a small number of shared primitives around the current control
plane instead of creating a second video production stack.

Required implementation pieces:

- `VideoProductionRun.run_type` migration and helper functions for run-type reads.
- Shared backend guards in or beside `video_production_state.py`.
- A shared readiness service used by every run mutation route.
- A mock-scale driver that uses the existing production plan, segment, asset, review, queue, and audit-event tables.
- A queue completion primitive in `production_queue_service.py` so the mock driver can exercise queued -> leased ->
  completed transitions without bypassing the queue model.

Do not add a new provider client, new media library table, new review table, or new frontend dashboard shell for this
phase. Reuse the model center, Pixelle/Seedance bridge, `VideoProductionAsset`, `VideoReviewRecord`, `GeneratedVideo`, the
existing review page, and the existing monitor page.

Suggested service dependency shape:

```text
video_production.py routes
  -> one_sentence_video_service / mock_scale_service
  -> video_production_readiness_service
  -> video_production_state guards
  -> video_production_service stage executors
  -> production_queue_service
  -> production_tree_service / production_status_aggregation
```

Provider submission should remain inside the existing stage executors. The mock-scale driver must never import or call
provider submission helpers.

## Run Types

This phase introduces an explicit operational distinction between real production and mock scale validation.

Run type must be persisted on the production run, not inferred from UI route names. Add an explicit
`VideoProductionRun.run_type` column with an index. Do not use `model_trace_json.run_type` as the only storage for new
runs; JSON can be read only as a backward-compatibility fallback for old rows created before the migration.

Allowed values for this phase:

- `real_short_e2e`
- `mock_series_scale`
- `legacy_episode_run`

`legacy_episode_run` exists only to keep current manually started episode production compatible. New one-sentence real
sample runs must use `real_short_e2e`; new mock scheduler runs must use `mock_series_scale`.

Expose `run_type` through every run payload, readiness payload, monitor payload, audit event, and mock asset metadata.
Stage services must read the persisted run type before provider submission, final writeback, or bulk mock review actions.

Run-type helpers should centralize this logic:

```text
get_run_type(run) -> str
assert_run_type(run, allowed)
assert_real_provider_allowed(run, stage, estimated_units, estimated_cost)
assert_mock_provider_only(run, stage)
```

### `real_short_e2e`

Purpose: produce a real 60-90 second video sample.

Properties:

- Real provider calls are allowed.
- Default target duration is 60 seconds.
- Maximum accepted target duration is 90 seconds.
- Default shot count target is 8-12 shots.
- Segment duration target is 5-8 seconds.
- Human gates are mandatory.
- Cost and retry limits are mandatory.
- Output can enter the real video library after final approval.

### `mock_series_scale`

Purpose: validate 240-minute multi-episode scheduling stability.

Properties:

- Real provider calls are not allowed.
- Default shape is 40 episodes x 6 minutes.
- Mock assets are persisted with clear mock metadata.
- Mock video segments are persisted as scheduling artifacts, not real generated videos.
- Final compose is represented by a mock compose marker, not a real 240-minute media file.
- Output cannot be presented as a real finished production.
- Monitoring must label the run as a scheduling drill.

### Run Type Enforcement

Backend services must enforce run type before any side effect:

- `real_short_e2e` can call real image, video, audit, and compose providers only after the configured safety checks pass.
- `legacy_episode_run` can continue using existing manual episode production routes, but it must not be created by the
  new one-sentence real-short or mock-scale entry points.
- `mock_series_scale` must use mock execution code paths only and must reject attempts to call real providers.
- bulk mock approvals must require `run_type = mock_series_scale`.
- real review endpoints may still approve real assets one by one or by selected asset list, but they must not expose full-series mock shortcuts.
- final library writeback must reject mock final compose markers.

## Real Short E2E Flow

### Input

Required:

- `prompt`

Optional:

- `title`
- `genre`
- `target_duration_seconds`, constrained to 60-90 seconds for the real path
- `budget_limit`
- `autostart_images`
- provider/model choices through the existing model configuration center

### Story And Plan Creation

The real path uses the existing one-sentence creation flow:

1. Create `Series`.
2. Create primary `Character` and `Scene` scaffolds.
3. Create `Episode`.
4. Generate `Episode.storyboard_json`.
5. Link to `ProductionPlan`, `ProductionEpisode`, `ProductionScene`, `ProductionShot`, and `ProductionSegment`.
6. Create `VideoProductionRun`.

The storyboard must include, per frame or segment:

- stable frame or segment id
- scene id
- character ids
- duration
- image prompt
- video prompt
- narration or audio mode
- continuity notes
- shot type
- references if available

### Duration And Shot Limits

For `real_short_e2e`:

- Minimum duration: 60 seconds.
- Maximum duration: 90 seconds.
- Maximum real image generation units: 12.
- Maximum real video generation units: 12.
- Provider retry limit: 1 retry per image or video unit.
- Any attempt to exceed these limits must return a recoverable error before provider submission.

If the user asks for a longer real video, the UI should route them to long-form planning or mock scheduling, not silently submit a large real provider run.

The current one-sentence payload shape can stay backward compatible, but the real-short endpoint or payload mode must clamp
`target_duration_seconds` to 60-90 seconds before any series, episode, plan, or provider task is created. Existing long-duration
values belong to mock scheduling or later long-form planning only.

Engineering requirement: reject invalid real-short duration before any database mutation. Do not create a partial
`Series`, `Episode`, `ProductionPlan`, or `VideoProductionRun` when `run_type = real_short_e2e` and the requested duration
is outside 60-90 seconds.

### Image Stage

Image generation uses the existing configured image provider path. The first implementation should prefer current model-center routing and existing image production strategy decisions instead of hard-coding a provider.

Required behavior:

- Before submission, show estimated cost and provider/model selection.
- Persist task and asset snapshots.
- Persist actual provider response and errors with secrets redacted.
- Persist resulting images as reviewable assets.
- Move the run to `image_review_pending` when all image tasks finish and at least one asset exists per required segment.
- Move to `image_human_review_required` if an image task fails beyond retry or an image asset is rejected.

### Image Review Gate

Human approval is mandatory.

The system must not start video generation until:

- every required segment has a latest image asset
- every required image asset is `approved`
- the run status is `image_approved`

This must be enforced by backend state checks, not only by disabled frontend buttons.

### Video Segment Stage

Video generation uses the existing configured video provider path. The first real target is image-to-video using approved image assets from the image gate.

Required behavior:

- Submit only approved image assets to the video stage.
- Preserve segment id and asset lineage.
- Persist provider task id, response snapshot, status, and resulting video segment asset.
- Move to `video_review_pending` when all required video segments finish.
- Move to `video_human_review_required` if a video segment fails beyond retry or is rejected.

### Video Review Gate

Human approval is mandatory.

The system must not start compose until:

- every required segment has a latest video segment asset
- every required video segment asset is `approved`
- the run status is `video_segments_approved`

This must be enforced by backend state checks.

### Final Compose And Final Review

After all video segments are approved:

1. Compose can start.
2. Compose writes a final video asset.
3. Run enters `final_review_pending`.
4. Human final approval marks the final asset approved.
5. The run enters `completed`.
6. The final video is visible in the video library.

Final completion must not happen when the final video asset has not been human-approved.

AI final audit may create a recommendation, but it must not directly mark the run `completed` in this phase. A human final
review record is required for `completed`, `Episode.video_url` writeback, and `GeneratedVideo` library visibility.

## Mock 240-Minute Scale Flow

### Input

Required:

- series or story seed
- episode count
- episode duration

Default:

- 40 episodes
- 6 minutes per episode
- total 240 minutes

### Plan Shape

Each episode should contain a deterministic production tree:

```text
ProductionEpisode
  -> ProductionScene[]
    -> ProductionShot[]
      -> ProductionSegment[]
```

The exact defaults can follow existing production plan helpers, but the generated shape must be stable enough for tests and monitor pagination.

Suggested initial shape:

- 40 episodes
- 6 minutes per episode
- 6 scenes per episode
- 3 shots per scene
- 2 segments per shot
- 36 segments per episode
- 1440 total segments

This is large enough to test scheduling stability while staying manageable for local tests.

### Mock Provider Rules

Mock scale mode must never call real provider clients.

Mock execution should create:

- mock image assets
- mock video segment assets
- mock compose markers
- production events
- job status transitions

Mock execution must drive the existing queue lifecycle:

```text
enqueue_job -> claim_next_job -> mark_job_completed
                          \-> fail_job -> retry_wait / failed
release_expired_leases -> queued
```

Add `mark_job_completed(db, job_id, provider_task_id=None)` to `production_queue_service.py` and use it from the mock
driver. Do not mark jobs completed by directly editing `ProductionJob.status` in the mock scheduler.

Every mock asset should include metadata identifying:

- `mock: true`
- run type
- episode id
- segment id
- generation stage
- deterministic mock provider id

### Queue And Resume

Mock scale mode must exercise the existing job queue:

- enqueue image jobs per segment
- claim jobs by lease id
- mark jobs complete
- fail jobs with retryable and non-retryable errors
- release expired leases
- resume blocked or retry-wait jobs

Interruption and resume requirements:

- Re-running the scheduler must not duplicate completed assets.
- Re-running the scheduler must not skip unfinished segments.
- Existing completed jobs remain completed.
- Retryable failures continue from retry state.
- Non-retryable failures are visible as human intervention items.

### Failure Injection

The mock scale path should accept a failure profile:

- `0_percent`
- `1_percent`
- `5_percent`
- `10_percent`

Failure injection must be deterministic when given a seed. This makes tests reproducible.

Failure types:

- image mock generation failed
- video mock generation failed
- compose mock failed
- lease expired before completion

### Mock Review Gate Actions

The mock scale path should support bulk gate simulation:

- approve all image assets for one episode
- approve all image assets for the full mock series
- reject selected assets
- approve all video segment assets for one episode
- approve all video segment assets for the full mock series
- mark final mock compose reviewed

These actions simulate human gate progression for scheduling tests. They must be clearly labeled as mock review actions and should not be available for real provider runs unless they call the normal real review endpoints.

Mock bulk actions must be idempotent by `(run_id, stage, asset_type, asset_id, latest_version)`. Running the same mock approval
twice should not create duplicate latest assets, duplicate completion events, or conflicting review records.

Mock asset creation must also be idempotent. Use a stable key such as
`(run_id, production_segment_id, asset_type, source_version, mock_provider_id)` before inserting a mock asset. If an asset
already exists for that key, return it and update only safe status fields.

## Stage Gate State Machine

The gate state machine is shared by real and mock runs.

### Statuses

| Status | Meaning |
|---|---|
| `draft` | Run exists but production has not started. |
| `storyboard_ready` | Storyboard and production tree are ready. |
| `image_batch_running` | Image generation jobs are running. |
| `image_review_pending` | Image jobs finished; human review is required. |
| `image_human_review_required` | Image failures or rejections require human action. |
| `image_approved` | All required image assets are approved. |
| `video_batch_running` | Video segment generation jobs are running. |
| `video_review_pending` | Video jobs finished; human review is required. |
| `video_human_review_required` | Video failures or rejections require human action. |
| `video_segments_approved` | All required video segment assets are approved. |
| `composing` | Final compose is running. |
| `final_review_pending` | Final video exists; human final review is required. |
| `completed` | Final video is approved and library-ready. |

### Backend Enforcement

Backend services must enforce:

- video stage starts only after image approval
- compose starts only after video segment approval
- completed status requires approved final video asset
- completed status requires a human final review record for the latest final video asset
- rejected or failed assets do not count as approved
- mock bulk approval cannot apply to real provider runs
- real provider calls cannot occur in mock scale runs
- real provider calls require the persisted run type to be `real_short_e2e`
- mock final compose markers cannot create or update real video library assets

Suggested service-level guards:

- `assert_real_provider_allowed(run, stage, estimated_units, estimated_cost)`
- `assert_mock_provider_only(run, stage)`
- `assert_can_complete_final(db, run, final_asset)`

These guards should live beside the existing stage-gate checks so all routes and background drivers share the same enforcement.

`assert_can_complete_final` must verify:

- run type is not `mock_series_scale`
- final asset is the latest `final_video`
- final asset status is `approved`
- latest review record for the final asset includes `review_type = human` and `status = approved`
- the final asset URL or local path is present

AI final audit can write a recommendation and set the final asset to `review_pending`, but it must not call
`complete_final_video` directly.

## Frontend Requirements

### Shared Design Rules

This phase is an operator console, not a marketing page. The UI should stay dense, task-focused, and built for repeated
production operations. Do not add a landing-page hero, decorative card wall, or visual timeline editor for this phase.

All new or touched production labels must be Chinese and valid UTF-8. Existing mojibake and English production labels on
the one-sentence page, monitor page, and review page must be repaired while the related controls are touched. API ids,
model ids, provider ids, and raw debug fields may stay in their original form, but the primary operator label must be
Chinese.

The process must not feel like a dark box. Every production surface should expose:

- current run type
- current stage
- current gate
- next allowed action
- blocked reasons
- provider/model configuration state
- estimated next cost for real provider actions
- review status and latest asset lineage

Use consistent semantic color language across the touched pages:

- green: approved, completed, library-ready
- amber: waiting, pending review, human action required
- blue: running, provider task in progress, queue execution
- red: failed, rejected, budget blocked, provider blocked
- violet: mock drill or diagnostic-only state

Every run header must show a run-type badge:

- `真实短片` for `real_short_e2e`
- `模拟长剧调度` for `mock_series_scale`

Raw status values such as `image_batch_running` or `video_segments_approved` may appear only as secondary debug text.
Primary status labels must use Chinese names.

Navigation between the one-sentence entry, production monitor, and review center must be explicit. When a gate is blocked,
the UI should provide a visible action to open the relevant review queue or configuration page instead of relying on the
operator to infer the next page.

Accessibility and layout requirements:

- changing readiness and gate messages should use an `aria-live` region
- review queues and paginated production trees must be keyboard navigable
- long provider errors, prompts, asset ids, and model ids must wrap without overflowing cards or buttons
- mobile and narrow desktop layouts must preserve readable stage names, action buttons, and blocked reasons

### One-Sentence Page

The page should expose two explicit paths:

- `真实短片`
- `模拟长剧调度`

Use a top-level segmented control for these modes. The selected mode changes both validation and visible copy; it must not
only set a hidden request value.

For `真实短片`, show:

- one-sentence prompt
- optional title
- target duration constrained to 60-90 seconds
- estimated shot count
- estimated real provider cost
- selected image model and video model
- provider configuration check
- budget cap
- autostart image stage toggle

For `模拟长剧调度`, show:

- episode count
- episode duration
- total planned duration
- failure injection profile
- deterministic seed
- clear mock-only warning that the output cannot enter the real video library

The UI must clearly show:

- run type
- target duration
- whether real provider cost can occur
- current stage
- current gate
- next allowed action
- provider/model configuration warnings
- budget warning or blocked reason

Autopilot must stop at human gates and say that review is required. It must not silently advance.

After run creation, show a visible production timeline with these Chinese stage names:

```text
内容策划 -> 风格锁定 -> 分镜规划 -> 图像生成 -> 图像审查 -> 视频生成 -> 视频审查 -> 合成 -> 终审入库
```

Autopilot stop messages must be explicit, for example `已到达图像人工审查闸门，请先审核通过后再继续生成视频`.

### Production Monitor

The monitor should use the first viewport as an operational dashboard, not a decorative card. The top health strip should
show:

- run-type badge
- overall status
- current gate
- next allowed action
- estimated next cost for real provider actions
- provider/model configuration state
- queue totals
- review totals

The monitor should also show:

- total episodes
- total scenes, shots, segments
- completed image assets
- approved image assets
- completed video segments
- approved video segments
- queued jobs
- leased jobs
- retry-wait jobs
- failed jobs
- current bottleneck stage
- exception segments

For mock scale drill, the monitor must label output as mock scheduling validation.

For real short E2E, the monitor must expose review and retry actions without hiding provider errors.

The monitor needs a Chinese stage timeline with state text for waiting, running, pending review, approved, failed, and
blocked states. Long raw provider errors should be collapsible, but their summarized cause and next action must stay
visible.

The monitor must not load the full 1440-segment mock tree into one client payload. Use server-side aggregates for the top
health strip and paginated detail for episode / scene / shot / segment drill-down.

The tree detail view must support filtering by episode, stage, and status. Selecting a segment should open a detail panel
with:

- image prompt and video prompt
- character and scene references
- latest image asset
- latest video segment asset
- final asset lineage if composed
- audit notes
- review history
- retry impact and cost impact

For `模拟长剧调度`, the monitor must show a persistent banner that this is a scheduling drill and cannot be published or
added to the real library.

### Review Center

The existing AI video review page should be treated as the review center for this phase. It must distinguish image review,
video segment review, and final review instead of presenting all reviews as one generic queue.

The review center should group queues by:

- asset type
- stage gate
- run type
- review status

Each review item should show:

- media preview large enough for inspection
- prompt
- reference images or source asset
- model/provider trace
- AI audit summary
- human review history
- blocked reason if it cannot be approved

Controls must be Chinese and gate-specific:

- approve latest image asset
- reject image asset
- regenerate image asset
- approve latest video segment
- reject video segment
- regenerate video segment
- approve final video into library
- reject final video

For real runs, bulk approval is allowed only for explicitly selected latest assets and must show the selected count before
submission. Full-series bulk approval shortcuts are allowed only for `模拟长剧调度` and must be visibly labeled as mock
drill actions.

Final review must be visually and textually distinct from image/video review. It is the only gate that can mark a real
short run completed and library-ready.

## API Requirements

The implementation can extend existing routes, but the API shape should remain explicit.

Prefer reusing current routes where they already match the lifecycle:

- existing one-sentence creation can accept an explicit `run_type` or be wrapped by a stricter real-short route
- existing start/sync/review/compose routes should call shared run-type and gate guards
- existing tree and cost routes should be extended with aggregates instead of duplicating monitor endpoints

Suggested additions:

```text
POST /api/video-production/one-sentence/start-real-short
POST /api/video-production/mock-scale/start
POST /api/video-production/mock-scale/{run_id}/drive
POST /api/video-production/mock-scale/{run_id}/inject-failures
POST /api/video-production/mock-scale/{run_id}/approve-images
POST /api/video-production/mock-scale/{run_id}/approve-videos
GET  /api/video-production/runs/{run_id}/readiness
```

These route names are suggestions. If existing route structure already covers the action cleanly, reuse existing routes and add explicit `run_type` and payload fields instead.

### Readiness Contract

`GET /api/video-production/runs/{run_id}/readiness` should return enough data for the UI to avoid dark-box production:

- `run_type`
- `current_stage`
- `current_gate`
- `next_allowed_actions`
- `blocked_reasons`
- `missing_assets`
- `unapproved_assets`
- `provider_config_status`
- `budget_status`
- `estimated_next_cost`
- `real_provider_allowed`
- `mock_only`

Readiness must be computed by one backend service, not reimplemented in each route. Suggested shape:

```text
build_run_readiness(db, run) -> dict
```

All start, sync, drive, review, retry, pause, resume, and compose endpoints touched by this phase should return the same
readiness block after mutating state. This keeps the one-sentence page, monitor, and review center consistent.

Readiness should include human-readable problem details for each blocked reason:

- `code`
- `message`
- `repair_action`
- `repair_route`
- `affected_ids`
- `retryable`

## Cost And Safety Requirements

For `real_short_e2e`:

- provider calls require configured model scene for image and video stages
- missing provider config must block before submission
- cost preview must be visible before expensive stage starts
- budget limit must be enforced before provider submission
- retries must be capped
- provider errors must be redacted
- no secret can be stored in run or asset snapshots
- real provider smoke tests require an explicit environment flag such as `DY_AUTO_ALLOW_REAL_PROVIDER_E2E=1`
- provider smoke tests must also require a per-run budget cap and a maximum shot count before submission

Cost preflight must happen in the stage guard, not only in the UI. Use configured cost profile metadata when available. If
pricing metadata is unavailable, readiness must say the estimate is unknown and real provider submission should require an
explicit budget cap that still bounds the maximum units for the stage.

Provider submission must be all-or-blocked per stage. If preflight fails, persist an audit event and a readiness blocker,
but do not create a provider task id or partial provider asset.

For `mock_series_scale`:

- provider calls must be impossible
- mock metadata must be explicit
- mock final output must not be listed as a real final video

Provider response snapshots may be persisted only after secret redaction. Persist enough non-secret data for debugging:
provider task id, status, model id, model config version, response status, provider error code, retryability, and sanitized
message.

## Operational Observability

Observability is part of the product boundary for this phase. Operators must be able to answer "what is happening, why did
it stop, what costs money next, and who approved the gate" from dy_auto without reading server logs.

Required audit events:

- `run.created`
- `run_type.assigned`
- `readiness.blocked`
- `provider_config.blocked`
- `budget.blocked`
- `provider_task.submitted`
- `provider_task.completed`
- `provider_task.failed`
- `image_review.pending`
- `image_review.approved`
- `video_review.pending`
- `video_review.approved`
- `final_review.pending`
- `final_review.approved`
- `run.completed`
- `mock_scale.job.claimed`
- `mock_scale.job.completed`
- `mock_scale.job.failed`
- `mock_scale.lease.expired`

Required bounded counters for the monitor:

- total episodes, scenes, shots, and segments
- queued, leased, retry-wait, failed, and completed jobs
- generated, pending-review, approved, rejected, and failed image assets
- generated, pending-review, approved, rejected, and failed video segment assets
- current bottleneck stage
- next action and blocked reason count
- estimated next cost and actual cost to date for real runs

Minimum runbook:

```text
If provider config is missing -> open model configuration center -> configure required scene -> retry stage.
If budget is blocked -> raise budget cap or reduce shot count -> retry stage.
If image review blocks -> open review center -> approve, reject, or regenerate latest image assets.
If video review blocks -> open review center -> approve, reject, or regenerate latest video segment assets.
If final review blocks -> inspect final video -> human approve into library or reject back to compose-ready state.
If mock scheduler stalls -> release expired leases -> inspect failed jobs -> resume or rerun deterministic driver.
```

## Developer Experience Requirements

The implementation must be easy to verify locally because this phase crosses migrations, API contracts, queue behavior,
provider safety, and frontend state. Add or update implementation notes in the relevant plan or docs with copy-paste
commands for:

- backend focused tests for run type, readiness, real-short preflight, final human gate, and mock scheduler
- frontend focused tests for one-sentence page, production monitor, and review center
- mocked E2E tests
- opt-in provider smoke test with `DY_AUTO_ALLOW_REAL_PROVIDER_E2E=1`

Required developer-facing details:

- migration name and rollback expectation for `VideoProductionRun.run_type`
- model-center scene keys required by the real path
- readiness response example with one happy path and one blocked path
- named error codes for duration limit, provider config missing, budget blocked, review gate blocked, stale asset, mock-only violation, and final approval missing
- mock-scale seed and failure profile examples
- provider smoke-test safety checklist showing max duration, max shot count, budget cap, and env flag

### Commands

Backend mocked E2E and scheduler validation:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_real_short_mocked_e2e.py tests/test_video_production_mock_scale_api.py tests/test_video_production_full_mocked_e2e.py -q
```

Frontend focused Vitest slice:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/one-sentence-video-page.test.js src/__tests__/video-production-monitor-page.test.js src/__tests__/review-bulk-actions.test.js
```

Opt-in provider smoke. This command calls real providers and consumes provider budget; run it only with a configured model
center, a strict budget cap, and the explicit environment flag:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
$env:DY_AUTO_ALLOW_REAL_PROVIDER_E2E = "1"
python scripts\smoke_seedance_short_video.py --prompt "A courier crosses a rainy neon city to deliver one impossible message." --title "Rain Courier" --budget 1.0 --duration 60
```

Every new repairable error returned by this phase should include:

- `code`
- `message`
- `cause`
- `repair_action`
- `repair_route`
- `affected_ids`
- `retryable`

Target time-to-verify for a developer on an already configured local repo:

- under 5 minutes for unit test slice
- under 10 minutes for mocked real-short E2E
- under 15 minutes for mock-scale scheduler E2E

## Implementation Sequence

Recommended order:

1. Add `run_type`, run-type helpers, migration tests, and payload exposure.
2. Add shared readiness service and return readiness from existing run mutation routes.
3. Harden real-short preflight: duration/shot limits, cost budget, provider config, and final human approval.
4. Add queue completion primitive and mock-scale driver behind mock-only guards.
5. Add frontend mode selector, Chinese labels, readiness display, monitor badges, and review-center gate separation.
6. Add mocked E2E coverage and the opt-in provider smoke test guard.

Do not start the frontend mode switch before the backend can return `run_type` and readiness. Otherwise the UI will need
temporary inference logic that will become technical debt.

## Testing Strategy

### Unit Tests

Backend:

- `VideoProductionRun.run_type` migration sets explicit values for new rows and preserves legacy rows as `legacy_episode_run`
- run payloads, readiness payloads, audit events, and asset metadata expose `run_type`
- real short duration and shot limits
- one-sentence real-short route rejects values outside 60-90 seconds before creating any database rows
- persisted run type is included in run payloads and stage event metadata
- missing model config blocks before provider submission
- budget cap blocks before provider submission
- provider task id is not written when provider preflight fails
- readiness endpoint returns next actions, blocked reasons, provider config status, and budget status
- every mutation endpoint touched by this phase returns the same readiness block
- video cannot start before image approval
- compose cannot start before video segment approval
- completed cannot be set before final review approval
- AI final audit approval does not complete a real-short run without human final approval
- `assert_can_complete_final` rejects mock final compose markers and final assets without human approval
- mock scale plan creates expected episode / scene / shot / segment counts
- mock scale enqueue/claim/complete uses `production_queue_service.mark_job_completed`
- mock scale execution is idempotent
- mock asset creation is idempotent by stable mock asset key
- mock scale retry and lease expiry behavior
- mock scale driver never imports or calls real provider submission helpers
- mock bulk approvals do not apply to real runs
- selected real bulk approval cannot approve stale assets or a full unselected run
- mock final compose marker cannot create `GeneratedVideo`

Frontend:

- one-sentence page shows real vs mock mode labels
- one-sentence page uses Chinese copy for new production controls and gate messages
- one-sentence page has no mojibake in touched production controls
- one-sentence page does not expose English primary stage labels for touched controls
- autopilot stops at image review gate
- autopilot stops at video review gate
- autopilot stops at final review gate
- one-sentence mode selector changes validation and visible fields
- monitor shows mock scheduling label
- monitor shows `真实短片` and `模拟长剧调度` run-type badges
- monitor shows Chinese health strip labels, current gate, next action, and blocked reasons
- monitor shows exception counts and waiting review counts
- monitor uses aggregates plus pagination for mock scale runs
- review center distinguishes image review, video segment review, and final review
- review center bulk actions distinguish selected real assets from mock drill shortcuts
- responsive tests verify long prompts, provider errors, and model ids do not overflow key controls

### Mocked E2E Tests

- 60-90 second real-short flow with providers mocked as successful, preserving real stage gates.
- 60-90 second real-short flow does not complete after AI final audit until human final approval.
- 60-90 second real-short flow with image failure and retry.
- 60-90 second real-short flow with video failure and human intervention.
- real-short request above 90 seconds fails with no created series, episode, run, or provider task.
- 40 x 6 minute mock scale drill completes all mock stages with no duplicate assets after resume.
- 40 x 6 minute mock scale drill with deterministic 5% failure injection.
- mock scale drill proves provider clients are not called.

### Provider Smoke Test

Real provider smoke test is opt-in only.

Requirements:

- explicit environment flag
- strict duration and shot caps
- strict budget cap
- no automatic large-scale loop
- no provider call in normal CI

## Acceptance Criteria

### Real Short E2E

- User enters one sentence.
- System creates a real-short production run.
- Run creates 8-12 planned shots for 60-90 seconds.
- Image stage uses configured real image provider.
- Image assets persist and enter human review.
- Video stage is blocked until image assets are approved.
- Video stage uses configured real video provider after approval.
- Video segment assets persist and enter human review.
- Compose is blocked until video segment assets are approved.
- Final video enters final review.
- Final approval marks the run completed and library-ready.
- Failure at any stage is visible and recoverable.

### Mock Scale Scheduling

- User creates a 240-minute scale drill.
- System creates 40 episode plans of 6 minutes each.
- System creates deterministic scenes, shots, segments, and jobs.
- Mock execution can run in batches.
- Resume does not duplicate completed assets.
- Failure injection is deterministic.
- Failed and retrying jobs are visible.
- Bulk mock review actions advance gates only for mock runs.
- Monitor can show total progress and exceptions without loading the entire tree at once.

## Backlog After This Phase

- Real 3-5 minute provider E2E.
- Real 10-minute provider E2E.
- Real multi-episode provider execution.
- More advanced role anchor reference generation.
- More detailed cost dashboard.
- Provider-specific optimization for Seedance continuation frames.
- Automated AI review mode with user-configured thresholds.
- Export packages for external editing tools.

## Risks And Controls

| Risk | Control |
|---|---|
| Real provider cost runs away | duration, shot, retry, and budget caps |
| Mock output confused with real output | explicit run type and mock metadata |
| Human gate bypass | backend state checks before every stage |
| Long mock run overwhelms UI | aggregate monitor plus pagination |
| Resume duplicates assets | idempotency keys per run/stage/segment/version |
| Provider secrets leak in errors | redaction before persistence |
| Scope grows into new editor/dashboard | out-of-scope list and phase acceptance criteria |

## Spec Self-Review

- Placeholder scan: no unresolved placeholder terms are intentionally left in the spec.
- Internal consistency: real provider work is limited to the short sample path; 240-minute work is mock scheduling only.
- Scope check: this remains a large phase but is split into two explicit tracks with separate acceptance criteria.
- Ambiguity check: human gates are mandatory; automatic review approval is out of scope.

## GSTACK REVIEW REPORT

Autoplan review date: 2026-05-31

Autoplan restore point: `C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260531-002540.md`

Full report: `docs/superpowers/reports/2026-05-31-video-production-real-loop-and-scale-scheduler-autoplan-final-review.md`

### Review Status

| Review | Status | Findings |
|---|---|---|
| CEO | clean | Scope is correct after success metrics, no-go conditions, and observability requirements. |
| Design | clean | Existing pages should be reused; Chinese copy, run-type badges, and visible gates are required. |
| Eng | clean | Implementation must start with explicit run type, readiness service, final human gate, and mock-only guards. |
| DX | clean | Verification commands, migration expectations, readiness examples, and named repairable errors are required. |

### Cross-Phase Themes

| Theme | Action |
|---|---|
| No hidden automation | Readiness, audit events, current gate, next action, and blocked reasons are release requirements. |
| Real and mock must not blur | `run_type`, mock metadata, mock-only guards, and visible badges are required. |
| Final human review is mandatory | AI final audit is recommendation-only; final writeback requires human approval. |
| Monitor must stay bounded | Aggregates plus paginated detail are required for mock-scale runs. |
| Errors must be repairable | Named error codes and repair actions are required in readiness and mutation responses. |

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Hold scope on real-short plus mock-scale | Auto | Focus as subtraction | Proves value and stability without uncontrolled provider cost. | Real long-provider execution now |
| 2 | CEO | Add no-go conditions | Auto | Choose completeness | Prevents fake completion or unsafe hidden behavior. | Soft acceptance wording |
| 3 | Design | Reuse existing three UI surfaces | Auto | DRY | Existing pages match the workflow. | New dashboard shell |
| 4 | Design | Require Chinese and valid UTF-8 primary copy | Auto | Explicit over clever | Operator trust requires readable UI. | Raw English production labels |
| 5 | Eng | Require explicit `run_type` column | Auto | Explicit over clever | JSON-only mode is unsafe for enforcement. | Infer mode from route or trace JSON |
| 6 | Eng | Make AI final audit recommendation-only | Auto | Choose completeness | The user requires human gates. | AI audit auto-completion |
| 7 | Eng | Add shared readiness service | Auto | DRY | Prevents divergent route payloads. | Per-route readiness builders |
| 8 | Eng | Add queue completion primitive | Auto | Explicit over clever | Mock scheduler must exercise queue lifecycle. | Direct job status edits |
| 9 | DX | Add verification and error-contract requirements | Auto | Bias toward action | Implementers need fast local confidence. | Leave commands and errors implicit |

### Final Gate

Status: approved for implementation planning.

User challenges: none.

Taste decisions requiring user input: none.
