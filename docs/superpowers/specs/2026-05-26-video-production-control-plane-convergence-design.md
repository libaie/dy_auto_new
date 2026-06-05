<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260526-103018.md -->

# AI Video Production Control Plane Convergence Design

## Summary

This design consolidates the unfinished parts of two existing designs:

- `2026-05-25-dy-auto-pixelle-stage-gated-integration-design.md`
- `2026-05-25-series-scale-long-video-production-design.md`

The two designs do not conflict. They describe different layers:

- The Pixelle stage-gated design defines how dy_auto calls Pixelle-Video through explicit image, video, and compose stages.
- The series-scale long-video design defines how dy_auto plans, tracks, retries, reviews, and packages many shots and segments.

The next implementation stage must converge these layers into one control plane. dy_auto owns production truth through `production_*` tables. Pixelle-Video remains the execution layer. `VideoProductionRun` remains a stage execution record and compatibility bridge, not the main long-video state machine.

The first target is stable 3-8 minute episode production with many shots and segments. The system must be observable, reviewable, retryable, resumable, and cost-aware before expanding to Volume-level and 240+ minute collection production.

## Current Baseline

Already implemented or partially implemented:

- Pixelle stage APIs exist for batch image generation, batch video generation, composition, and stage task status.
- dy_auto has staged video production routes for creating runs, starting image/video stages, syncing results, composing, regenerating assets, and reviewing assets.
- `production_*` models exist for plan, episode, scene, shot, segment, job, cost event, and collection.
- A production tree API exists for plans/runs.
- Segment retry, bulk review, collection creation, and cost service foundations exist.
- The frontend has initial production monitor, review center, and collection builder pages.
- Seedream/Seedance Ark Plan V3 defaults are configured with `/api/plan/v3`.

Important gaps:

- `production_*` and `VideoProductionRun` are not yet fully unified around one ownership model.
- There is no first-class `ProductionVolume`.
- Director routes are not aligned with the long-video API shape: `/series-plan`, `/episode-plan`, and `/shot-segments` are not all present as formal contracts.
- Run-level `pause`, `resume`, `retry`, and `costs` APIs are incomplete.
- Review storage is split conceptually between the long-video design's `production_reviews` idea and the implemented `VideoReviewRecord`.
- The frontend production monitor is useful but not yet a complete control room with retry impact, cost ledger, provider trace, and state explanations.
- Real paid-provider end-to-end validation is not completed and should remain a manual smoke gate until mocked flows are stable.

Current code already has some fields this convergence depends on. `VideoProductionAsset` already includes `production_segment_id`, `target_type`, `target_id`, `provider_task_id`, and `prompt_hash`. The remaining model work should not re-add those fields. It should add only the missing fields and change the execution path to actually use the production links.

## Product Goal

Give the operator a transparent AI video production control room:

1. Plan an episode from a locked series style bible.
2. Split it into scenes, shots, and 5-8 second segments.
3. Generate key images through Pixelle stage APIs.
4. Run AI review and route exceptions to human review.
5. Generate video segments only after image gates pass.
6. Run AI/human video review.
7. Compose the final episode.
8. Persist final video assets and write back to episode/video library.
9. Support local retry and resume without rerunning the entire episode.
10. Expose every model call, provider task, review decision, version, and cost event.

## Product Principles

The business promise remains one-sentence content production. The control room exists to make automation visible and recoverable; it must not become a manual editing workflow.

Principles:

- Default path: user gives one sentence or an episode brief, then the system plans, generates, reviews, and composes automatically.
- Human work is exception handling, not required per-segment operation.
- The production monitor shows every background step, but it should not force the operator to drive every step manually.
- AI review auto-approval is the default when confidence is high and policy passes.
- Human review queues should show exceptions first: failed audit, low confidence, provider failure, stale version, budget block, and drift risk.
- Retry is local and explainable. A failed Segment should not make the user rerun the whole episode.
- Existing staged production and auto-plan flows must remain available during migration until linked production runs are proven by mocked E2E.

### North-Star User Flow Contract

Stage 1 must preserve the product promise as a single visible user flow:

```text
series detail / episode brief
  -> ensure style lock
  -> create episode production plan
  -> create shot segments
  -> create linked production run
  -> start autopilot image stage
  -> open production control room
  -> continue automatically until a review, budget, provider, or retry gate blocks
```

The user should not need to understand which internal route created the plan, segments, run, jobs, or stage tasks. Those steps must appear in the control room as visible progress, not as required manual setup.

This means Stage 1 implementation must include a single frontend entry action from the series or episode context. It may call multiple backend APIs internally, but the user-facing action is still one production start flow.

### Named Error And Repair Contract

Every blocking failure returned by planning, run creation, stage execution, review, retry, pause/resume, and compose must include:

- `error_code`
- `message`
- `repair_action`
- `repair_route` when an in-app route can fix it
- `retryable`
- `affected_ids`

Minimum error codes:

| Code | Trigger | User-visible repair |
|---|---|---|
| `STYLE_LOCK_MISSING` | Series has no locked style bible | Lock style before production |
| `STORYBOARD_MISSING` | Episode has no usable storyboard snapshot | Generate automatic storyboard |
| `SEGMENT_PLAN_MISSING` | No `ProductionSegment` rows exist | Generate shot segments |
| `RUN_LINK_AMBIGUOUS` | Legacy run matches multiple production plans | Repair run-plan link |
| `RUN_LINK_MISSING` | Linked production run cannot resolve plan/episode | Recreate or repair run |
| `PROVIDER_TASK_PENDING` | Provider task is not complete yet | Keep waiting or sync later |
| `PROVIDER_TASK_FAILED` | Pixelle/provider returned failed task | Inspect provider trace and retry allowed scope |
| `ASSET_URL_MISSING` | Provider response has no usable asset URL | Retry provider task or repair asset |
| `ASSET_COPY_FAILED` | dy_auto could not copy/register returned asset | Retry asset registration |
| `STALE_ASSET_VERSION` | Human action targets a non-latest asset | Reload latest version |
| `BUDGET_EXCEEDED` | Actual or estimated cost exceeds budget | Adjust budget or pause production |
| `PAUSED_BY_OPERATOR` | Run or plan is paused | Resume queued work |
| `RETRY_IMPACT_BLOCKED` | Retry would break continuity or approved downstream work | Review retry impact before confirming |

Do not return generic `Action failed` or raw provider errors without one of these names.

## Non-Goals For The Next Implementation Stage

The next stage will not implement:

- Full 240+ minute end-to-end production in one run.
- Full Volume management UI.
- Visual timeline editing.
- Douyin publishing.
- Multi-user reviewer roles and assignment.
- Advanced fallback chains across many providers.
- A second Pixelle model configuration UI.
- Shared database between dy_auto and Pixelle-Video.
- Required paid-provider E2E as a merge condition.

These are not rejected permanently. They are deferred until the control plane is stable.

## Core Architecture Decision

`production_*` is the business source of truth.

```text
Series
  -> ProductionPlan
    -> ProductionEpisode
      -> ProductionScene
        -> ProductionShot
          -> ProductionSegment
            -> ProductionJob
            -> VideoProductionAsset
            -> VideoReviewRecord
            -> ProductionCostEvent
```

`VideoProductionRun` is a stage execution record:

```text
VideoProductionRun
  production_plan_id
  production_episode_id
  series_id
  episode_id
  current_stage
  status
  pixelle_stage_task_id
  storyboard_json snapshot
  model_trace_json
```

Ownership rules:

- Production planning, status, retry scope, cost, and progress belong to `production_*`.
- Stage submission and Pixelle polling belong to `VideoProductionRun`.
- Linked production runs must build image, video, and compose payloads from `ProductionSegment` rows. They must not build payloads from `VideoProductionRun.storyboard_json` except as a legacy fallback for runs without production links.
- Pixelle never decides whether the next stage is allowed. It only returns task status, assets, and structured errors.
- `Episode.storyboard_json` remains a compatibility snapshot, not the long-video production source of truth.
- `GeneratedVideo` and `Episode.video_url` are final write-back targets.

## Data Model Convergence

### Required Additions

Add nullable links to `VideoProductionRun`:

- `production_plan_id`
- `production_episode_id`
- `production_link_status`

Migration rules for these links:

- Add real foreign keys to `production_plans.id` and `production_episodes.id`.
- Backfill legacy runs only when a single matching `ProductionEpisode` can be resolved by `series_id` and `episode_id`.
- Set `production_link_status` to one of:
  - `linked`
  - `legacy_unlinked`
  - `ambiguous`
  - `missing_plan`
- Keep trace-based lookup through `model_trace_json.production_plan_id` only during one compatibility window.
- New run creation must always write the real columns.
- `/runs/{run_id}/tree` must read real columns first and return a repair error when a legacy run cannot be uniquely linked. It must not repeat expensive ambiguity scans for runs already marked `ambiguous` or `missing_plan`.

`VideoProductionAsset` already has `production_segment_id`, `target_type`, `target_id`, `provider_task_id`, and `prompt_hash`. Add only the remaining version-truth and storage fields:

- `production_shot_id`
- `is_latest`
- `source_version`
- `copy_status`
- `checksum`
- `size_bytes`

Add review targeting fields to `VideoReviewRecord` or equivalent review storage:

- `target_type`
- `target_id`
- `production_segment_id`
- `asset_version`
- `is_latest_asset_review`

This design does not require a new `production_reviews` table in the next implementation stage. Use `VideoReviewRecord` as the unified review table and extend it. A separate `production_reviews` table can be introduced later only if the existing table becomes too constrained.

Required indexes and invariants:

- Index `VideoProductionRun(production_plan_id, production_episode_id)`.
- Index `VideoProductionAsset(production_segment_id, asset_type, is_latest)`.
- Index `VideoReviewRecord(target_type, target_id, asset_version)`.
- Index `ProductionJob(plan_id, status, resume_status)`.
- Add `resume_status`, `blocked_reason`, and `paused_at` to `ProductionJob`, unless an explicit pause ledger table is introduced in the same migration.
- Enforce at service level that only one latest asset exists per `production_segment_id + asset_type`.
- Stage 1 must not rely on a database partial unique index as the only latest-asset guard because local SQLite tests and deployed SQL engines may differ. The invariant must be enforced in one transaction that demotes old latest assets before inserting or promoting the new latest asset.
- Every review write must copy the reviewed asset version into `asset_version`.
- Every review write must copy `target_type`, `target_id`, and `production_segment_id` from the reviewed asset at review time.
- Human approval must fail when `is_latest` is false.

### Deferred Model

`ProductionVolume` is deferred to the following stage. The first stable target is episode-level production:

```text
ProductionPlan -> ProductionEpisode -> ProductionScene -> ProductionShot -> ProductionSegment
```

When Volume is added later, it should sit between `ProductionPlan` and `ProductionEpisode` without changing Segment execution semantics.

## Director Planning Contracts

The current `/api/director/auto-plan` remains for compatibility.

Add these formal long-video planning routes:

```text
POST /api/director/episode-plan
POST /api/director/shot-segments
```

Compatibility rule:

- Existing `POST /api/director/episode-production-plan` remains as a compatibility alias.
- The canonical implementation should move into one service used by both route names.
- The compatibility route should behave like `POST /api/director/episode-plan` with `include_segments: true`.
- Do not keep two independent segmentation implementations.

### `POST /api/director/episode-plan`

Input:

```json
{
  "series_id": "series-id",
  "episode_id": "episode-id",
  "target_duration_seconds": 360,
  "budget_limit": 50.0,
  "include_segments": true
}
```

Behavior:

- Load `Series.story_bible_json.style_lock`.
- Require locked style before planning.
- Generate or reuse `Episode.storyboard_json`.
- Create or update one `ProductionPlan`.
- Create `ProductionEpisode`, `ProductionScene`, and `ProductionShot` rows.
- When `include_segments` is true, call the same idempotent segmentation service used by `/shot-segments`.
- Keep `Episode.storyboard_json` synchronized as a readable snapshot.

### `POST /api/director/shot-segments`

Input:

```json
{
  "production_episode_id": "production-episode-id",
  "preferred_segment_seconds": 8
}
```

Behavior:

- Split every `ProductionShot` into 5-8 second `ProductionSegment` rows.
- Be idempotent for existing segments unless `force_regenerate` is explicitly provided later.
- Preserve character anchors, scene references, style references, narration, prompts, and continuity notes.
- Set `continuity_mode` per segment:
  - `continuous_action`
  - `narrative_cut`
  - `scene_change`
  - `montage`
- Record `previous_segment_id` only when continuity requires it.

`/api/director/series-plan` remains deferred until Volume-level planning begins.

## Production Run APIs

Use one route family for execution and control:

```text
POST /api/video-production/runs
GET  /api/video-production/runs/{run_id}
GET  /api/video-production/runs/{run_id}/tree
GET  /api/video-production/runs/{run_id}/costs

POST /api/video-production/runs/{run_id}/pause
POST /api/video-production/runs/{run_id}/resume
POST /api/video-production/runs/{run_id}/retry

POST /api/video-production/runs/{run_id}/start-images
POST /api/video-production/runs/{run_id}/sync-image-results
POST /api/video-production/runs/{run_id}/start-videos
POST /api/video-production/runs/{run_id}/sync-video-results
POST /api/video-production/runs/{run_id}/compose
POST /api/video-production/runs/{run_id}/sync-compose-results

GET  /api/video-production/segments/{segment_id}/detail
GET  /api/video-production/segments/{segment_id}/retry-impact
POST /api/video-production/segments/{segment_id}/retry
POST /api/video-production/reviews/bulk-action
POST /api/video-production/collections
```

Payload rule:

- `GET /api/video-production/runs/{run_id}` should return run summary, current stage, linked production ids, and aggregate counts. For linked production runs it must not return all assets for the run. Large or historical asset payloads belong to `GET /api/video-production/segments/{segment_id}/detail` and review item APIs.

### Run Creation

`POST /api/video-production/runs` must:

- Accept `series_id`, `episode_id`, and optional `production_plan_id`.
- Resolve the correct `ProductionEpisode`.
- Create a `VideoProductionRun` linked to `production_plan_id` and `production_episode_id`.
- Refuse to start if no segment plan exists.
- Return clear repair instructions when style lock, storyboard, plan, or segment rows are missing.
- Mark compatibility-only runs explicitly when they fall back to `storyboard_json`; linked production runs must use `ProductionSegment` rows.

### Pause

`POST /api/video-production/runs/{run_id}/pause` must:

- Mark plan or episode scope as paused.
- Block queued and retry-wait jobs.
- Store each paused job's previous status in `resume_status` or an equivalent pause ledger.
- Store `blocked_reason` on the job or pause ledger.
- Not cancel already leased/running Pixelle tasks.
- Show the operator which tasks are still running.

### Resume

`POST /api/video-production/runs/{run_id}/resume` must:

- Restore paused jobs to queued or retry-wait as appropriate.
- Keep failed terminal jobs unchanged.
- Restore from the recorded `resume_status` instead of guessing from current status.
- Recompute visible progress.

### Retry

`POST /api/video-production/runs/{run_id}/retry` must:

- Retry only failed or retryable nodes by default.
- Support explicit scope:
  - `run`
  - `episode`
  - `scene`
  - `shot`
  - `segment`
- Preserve old assets, old reviews, provider task ids, and cost events.
- Return the same impact shape as `GET /segments/{segment_id}/retry-impact` when retrying segment scope.

### Segment Detail

`GET /api/video-production/segments/{segment_id}/detail` must return the data the control room needs without requiring the frontend to join many payloads:

- segment, shot, scene, episode, and plan ids
- latest image asset and historical image versions
- latest video asset and historical video versions
- reviews for the selected latest assets
- provider task ids
- model trace
- prompt hash and prompt excerpt
- reference roles and URLs
- segment cost summary
- allowed actions
- repair instructions when the node is blocked

Query contract:

- The endpoint loads only the selected segment, its parent shot/scene/episode/plan, latest assets, a paginated asset history, and reviews for returned assets.
- The endpoint must not hydrate every asset in the run.
- Historical image and video versions must be paginated or capped with `history_limit`.
- Tests must assert the endpoint still behaves acceptably for a run with at least 30 Segments.

### Retry Impact

`GET /api/video-production/segments/{segment_id}/retry-impact` must be a dry run. It must not mutate data. It returns:

- current segment version
- target new version
- affected downstream segments
- blocked descendants by continuity mode
- old latest assets that will become non-latest
- estimated extra cost
- whether the retry is allowed

### Costs

`GET /api/video-production/runs/{run_id}/costs` must return:

- Known actual cost.
- Estimated remaining cost.
- Cost by stage.
- Cost by provider/model.
- Cost by episode/scene/shot/segment where available.
- Budget status:
  - `ok`
  - `near_limit`
  - `budget_blocked`

Cost calculation contract:

- `actual_cost` is the sum of persisted `ProductionCostEvent.actual_cost`.
- `estimated_remaining_cost` is calculated from unfinished jobs or unfinished segments, their stage, target duration, and the selected model config's pricing metadata when available.
- When pricing metadata is missing, the response must set `estimate_status: "unknown"` and return `unknown_estimate_reasons` instead of silently returning `0`.
- Budget blocking must use the same estimate source that the API reports, so the operator sees the reason before or when work is paused.

## Observability And Runbook

Observability is part of Stage 1 scope because the operator is trusting an automated, paid-provider production chain.

### Metrics

Record and expose at least these counters/timers:

- planning duration
- segment count by episode
- image stage submit/sync duration
- video stage submit/sync duration
- compose duration
- provider task failure count by provider/model/stage
- AI review pass/fail/needs-human counts
- human review count and average time-to-decision
- retry count by scope
- pause/resume count and reason
- cost actual vs estimated by run/stage/provider/model
- final compose success/failure count

### Audit Events

Persist or emit structured audit events for:

- style lock used for production
- production plan created or reused
- run created and linked
- stage submitted
- provider task synced
- asset registered
- AI review decision
- human review decision
- retry impact viewed
- retry confirmed
- pause/resume
- budget block
- final write-back

Each event should include `run_id`, `production_plan_id`, `production_episode_id`, `production_segment_id` when relevant, provider task id when relevant, and redacted model config metadata.

### Operator Runbook

The control room should make the first repair step visible for these production failures:

- style lock missing
- segment plan missing
- ambiguous legacy run link
- provider task pending too long
- provider task failed
- asset URL missing
- stale review target
- budget blocked
- retry impact not allowed

Stage 1 does not need an external alerting stack, but it must expose enough structured state that a dashboard or alert can be added without changing core execution semantics.

## State Model

Use these primary production states:

```text
planned
image_queued
image_running
image_review_pending
image_approved
video_queued
video_running
video_review_pending
video_approved
compose_queued
composing
completed
```

Use these exceptional states:

```text
paused
blocked_by_review
retry_wait
failed_retryable
failed_terminal
budget_blocked
```

Stored-state compatibility:

Current code already uses states such as `ready`, `retry_queued`, `failed`, and `superseded`. Stage 1 must define one canonical stored-state table before implementation starts:

| Meaning | Canonical stored state | Current compatible state | API display label |
|---|---|---|---|
| planned and ready to run | `planned` | `ready` | Planned |
| queued retry after a local retry | `retry_queued` | `retry_queued` | Retry queued |
| provider retry delay | `retry_wait` | `retry_wait` | Retry wait |
| old version replaced by retry | `superseded` | `superseded` | Superseded |
| retryable failure | `failed_retryable` | `failed` with `retryable=true` | Failed, retry available |
| terminal failure | `failed_terminal` | `failed` with `retryable=false` | Failed |
| budget stop | `budget_blocked` | `blocked` with reason `budget_exceeded` | Budget blocked |

### Aggregate Status Rules

Stage 1 must introduce one status aggregation service instead of spreading parent updates across routers:

```text
recompute_segment_status(segment_id)
  -> recompute_shot_status(shot_id)
  -> recompute_scene_status(scene_id)
  -> recompute_episode_status(episode_plan_id)
  -> recompute_plan_status(plan_id)
```

Call this service after:

- stage submission
- stage sync
- AI review write
- human review write
- retry mutation
- pause/resume
- budget block
- final compose sync

Parent status rules:

- Any `failed_terminal` child makes the parent `failed_terminal`.
- Any `failed_retryable` child makes the parent `failed_retryable` unless another child is running.
- Any review-pending child makes the parent `blocked_by_review`.
- Any running child makes the parent running for that stage.
- All completed children make the parent `completed`.
- Paused applies only when all runnable non-terminal descendants are paused or blocked by a pause ledger.

API display labels may normalize compatibility states, but storage writes must use the canonical table above.

The implementation may keep current compatible values during migration, but the API must normalize them so the frontend does not encode migration details.

State ownership:

- Segment state is the atomic truth.
- Shot state is derived from child segments.
- Scene state is derived from child shots.
- ProductionEpisode state is derived from child scenes.
- ProductionPlan state is derived from child episodes and queue state.
- VideoProductionRun status reflects the currently active stage execution batch.

No stage can advance if any latest required asset is missing, rejected, failed, or waiting for human review.

## Review Convergence

Review policy:

- AI review runs first.
- Human review is required for failed AI review, low confidence, malformed audit output, or audit service failure.
- Audit failure must never auto-approve.
- Human approval only unlocks the next stage for the latest asset version.

Review records must preserve:

- reviewer type: `ai` or `human`
- reviewer id when available
- target type and target id
- asset id and asset version
- status
- score
- issue list
- model trace
- created time

Bulk review must:

- Reject stale asset versions.
- Return partial success/failure details.
- Record reviewer and comment.
- Update only latest assets unless the request explicitly targets historical audit.

## Retry And Versioning

Segment retry creates a new version. It must not overwrite:

- old image assets
- old video assets
- old reviews
- old provider task ids
- old cost events

Retry impact rules:

- `continuous_action`: retrying a segment may block downstream continuous segments.
- `narrative_cut`: retrying a segment does not automatically block later segments unless they use its end frame.
- `scene_change`: retry is local to the segment.
- `montage`: retry is local unless explicitly linked.

Retry service rules:

- Calculate impact before mutation.
- Execute retry in one database transaction.
- Mark previous latest assets as non-latest before inserting new target jobs.
- Update dependent `previous_segment_id` links when continuity requires the new segment version.
- Create new jobs with fresh idempotency keys.
- On transaction failure, preserve the old latest assets and old segment state.

The UI must show retry impact before executing retry:

- affected segment count
- affected downstream segments
- old latest version
- new target version
- estimated extra cost

## Pixelle Execution Boundary

Pixelle-Video remains execution-only:

```text
dy_auto production control plane
  -> Pixelle /api/stages/images/batch
  -> Pixelle /api/stages/videos/batch
  -> Pixelle /api/stages/compose
  -> Pixelle /api/stages/tasks/{stage_task_id}
```

Pixelle response requirements:

- `stage_task_id`
- per-frame/segment asset result
- structured error code
- retryable flag
- provider task id
- model metadata without secrets
- last frame URL when available

dy_auto responsibilities:

- Resolve runtime model config.
- Send only the stage config needed for the current task.
- Redact secrets from logs and API responses.
- Copy or register returned assets into dy_auto asset records.
- Decide whether the next stage can start.

### Linked vs Legacy Stage Execution

The implementation must keep two explicit execution paths during the compatibility window:

- Linked path: runs with `production_plan_id`, `production_episode_id`, and `production_link_status = "linked"`.
- Legacy path: runs without production links, kept only for existing storyboard-based staged production.

Linked path requirements:

- `build_image_stage_frames_for_segments(db, run)` queries `ProductionSegment` with parent Shot, Scene, Episode, latest style-lock references, and continuity metadata.
- `build_video_stage_frames_for_segments(db, run)` queries latest approved image assets by `production_segment_id + asset_type + is_latest`, not by `frame_id`.
- `build_compose_segments_for_production(db, run)` queries latest approved video assets by `production_segment_id + asset_type + is_latest`.
- Stage submit and sync must write `ProductionSegment.status`, `VideoProductionAsset.production_segment_id`, `target_type`, `target_id`, `source_version`, `provider_task_id`, `prompt_hash`, cost events, and reviews.
- Idempotency keys must include `run_id`, `production_segment_id`, stage, segment version, and prompt/source hash.

Legacy path requirements:

- Existing storyboard-frame builders may remain for compatibility.
- Legacy path must not mutate `production_*` rows unless the run has been repaired and linked first.
- Legacy path responses should identify the run as `legacy_unlinked` so the UI can show repair instructions rather than pretending it is long-video production.

## Frontend Control Room

Enhance the current `VideoProductionMonitorPage` into a production control room.

### Design Scope And Baseline

No project-level `DESIGN.md` currently exists, so Stage 1C must define enough local design rules for this page instead of leaving the implementer to infer them from existing screens.

Reuse existing dy_auto operational patterns:

- dark slate workspace
- compact data-dense panels
- semantic status colors
- two-pane review-center behavior where selection on the left updates detail on the right
- rounded controls no larger than 8px radius unless an existing component already requires more

Do not use a marketing-style layout, hero section, decorative card grid, or tutorial copy. This is an operator surface for repeated monitoring and exception handling.

Design completeness target: the control room is successful when an operator can answer these questions in five seconds:

1. Is the run healthy, blocked, paused, or failed?
2. What is happening now?
3. What needs human attention?
4. Which Segment is affected?
5. What action is safe to take next?

### Operator Mental Model

The UI must separate three concepts:

- `Run`: the automation attempt and current stage.
- `Plan`: the production hierarchy and aggregate progress.
- `Segment`: the smallest retryable/reviewable unit.

Do not make `VideoProductionRun` look like the source of all truth. Linked runs should visually show the production plan id and episode id near the run summary. Legacy unlinked runs should show a repair banner rather than the full control room.

### Information Hierarchy

Desktop first-screen priority:

1. Run health strip: status, current stage, next blocker, cost/budget, pause/resume.
2. Stage timeline: storyboard -> image -> image review -> video -> video review -> compose -> complete.
3. Exception queue: failed, human-review, stale, budget-blocked, retry-wait Segments.
4. Production tree for navigation.
5. Selected Segment detail and preview.
6. Action panel and audit trail.

The top area must be a dense status strip, not a large header. The H1 should stay compact. The largest visual area should be the selected Segment preview because this is the user's inspection task.

Desktop layout:

```text
Top: run health strip, stage timeline, budget/cost, pause/resume

Left: production tree and exception filters
  Episode -> Scene -> Shot -> Segment

Center: selected Segment preview
  media preview, prompt, narration, references, current review result

Right: action panel
  allowed actions, retry impact, provider trace, cost, repair instructions
```

Panel behavior:

- Tree panel is navigation and counts only.
- Detail panel is the source of truth for selected Segment data.
- Action panel only shows actions allowed by the Segment detail response.
- Audit trail is collapsible by default but always visible as a section header with counts.
- Prompt/model trace can be collapsed behind "Prompt" and "Trace" tabs so dense technical data does not bury the media preview.

Required visible information:

- current stage
- current status
- provider task id
- model provider/name/config version
- prompt hash or prompt excerpt
- reference URLs and reference roles
- asset version
- review status
- failure reason
- retryability
- cost

### Status And State Design

Use a fixed visible state taxonomy. Do not surface raw backend state names alone.

| User-facing state | Backend states | Visual treatment | Primary action |
|---|---|---|---|
| Planning | `planned`, `ready` | neutral gray | none |
| Queued | `image_queued`, `video_queued`, `compose_queued` | gray with queue position when known | pause |
| Running | `image_running`, `video_running`, `composing` | blue progress treatment | inspect provider trace |
| Waiting for AI Review | `image_review_pending`, `video_review_pending` with AI review in progress | amber | none |
| Needs Human Review | `blocked_by_review`, failed AI audit, low confidence | amber with exception count | open review/approve/reject |
| Paused | `paused` | neutral with pause reason | resume |
| Retry Wait | `retry_wait`, `retry_queued` | amber with next retry time | view impact/cancel retry when supported |
| Budget Blocked | `budget_blocked` | red/amber budget banner | adjust budget/resume later |
| Failed | `failed_retryable`, `failed_terminal` | red; terminal failure disables retry | retry if allowed |
| Completed | `completed` | green | view final video |

Every long-running step must show both a label and a short explanation. For example: `Waiting for provider`, `AI review running`, `Human review needed`, `Paused by budget limit`.

### Autopilot And Human-Intervention Design

The default experience is autopilot. The page must not imply that the user must manually click through every stage.

Required controls:

- Primary run control: `Start` or `Resume`, only when a user action is required.
- Secondary run controls: `Pause`, `Retry failed`, `View costs`.
- Stage sync controls should be hidden under a developer/debug affordance when automatic polling is active. They must not be the main happy-path controls.
- Review actions appear only for assets/Segments that are blocked by review.

Required copy rule:

- Replace generic text such as `No segments` or `Action failed` with state-specific recovery text.
- Do not add instructional paragraphs. Use short labels, banners, and repair actions.

Examples:

- Empty linked run: `No segment plan yet. Generate shot segments before starting production.`
- Ambiguous legacy run: `This run is not linked to one production plan. Repair the link before using the control room.`
- Stale asset: `A newer version exists. Reload latest before reviewing.`
- Provider failure: `Seedance returned a retryable failure for this Segment. Preview impact before retrying.`

Frontend API dependency:

The control room must be built against `GET /api/video-production/segments/{segment_id}/detail`, not by guessing from the sparse tree response. The tree response is for navigation and counts. The detail response is for preview, provider trace, reviews, latest asset versions, allowed actions, retry impact entry points, and repair instructions.

The frontend must not hide background work. Every long-running stage must show one of:

- queued
- running
- waiting for provider
- waiting for AI review
- waiting for human review
- paused
- retry wait
- failed
- completed

### Retry Impact Dialog

Retry must never be a blind destructive action.

Before confirming retry, show:

- current Segment id and version
- target version
- affected downstream Segments
- continuity reason
- old latest assets that will be preserved as history
- estimated extra cost or unknown estimate reason
- whether final compose must be rerun

Confirmation button copy must name the scope, for example `Retry this Segment` or `Retry 4 affected Segments`. Disable confirmation when retry is not allowed.

### Responsive Behavior

Desktop `>= 1280px`:

- persistent three-column control room
- sticky run health strip
- selected Segment preview stays centered

Tablet `768px-1279px`:

- two-column layout: tree/filters on the left, detail/action stacked on the right
- action panel becomes sticky below the detail header

Mobile `< 768px`:

- single-column layout
- production tree opens as a drawer
- stage timeline becomes horizontal scroll with visible labels
- primary action bar is sticky at the bottom
- all touch targets are at least 44px high

The mobile layout must preserve the core workflow: choose exception -> inspect Segment -> review/retry/resume. It must not simply stack every desktop panel in order.

### Accessibility

Stage 1C must include:

- keyboard navigation through tree nodes
- visible focus styles on tree rows, action buttons, and review controls
- `aria-current` or equivalent on the selected Segment
- `aria-live="polite"` for stage/status updates
- text labels for all status colors
- contrast-safe colors for slate background and amber/red/green status text
- no action that is discoverable only by hover
- media preview alt text using Segment id and asset type

### Visual Quality Bar

Avoid these failure modes:

- nested cards inside cards
- every metric rendered as the same card weight
- raw JSON as the default view for model trace
- status colors without labels
- oversized title/header wasting first viewport space
- manual stage buttons dominating the happy path
- tree rows resizing when status labels change
- action buttons shifting layout after a Segment update

Preferred visual language:

- compact dashboard strip for run health
- stable-height tree rows
- segmented controls for filters
- icon plus text only for high-risk actions when icons exist
- tabs for media/prompt/review/trace in the Segment detail panel
- monospace only for ids, hashes, and provider task ids

## Next Development Roadmap

### Stage 1: Control Plane Convergence

Goal: make 3-8 minute episode production stable and transparent.

Scope mode: hold Stage 1 scope. Do not expand into Volume UI, provider fallback chains, multi-user review assignment, or 240+ minute production in this stage. The accepted expansion inside Stage 1 is product hardening: one user-facing start flow, named repairable errors, and production observability.

Deliverables:

- Add `production_plan_id` and `production_episode_id` links to `VideoProductionRun`.
- Add production segment links and latest-version fields to `VideoProductionAsset`.
- Extend `VideoReviewRecord` to support production target semantics.
- Add `/api/director/episode-plan`.
- Add `/api/director/shot-segments`.
- Enforce run creation from a persisted segment plan.
- Add run-level `pause`, `resume`, `retry`, and `costs`.
- Add segment detail and retry impact APIs.
- Replace linked-run stage payload builders so they query `ProductionSegment` rows instead of `storyboard_json`.
- Make stage transitions update `ProductionSegment` and parent aggregate statuses.
- Add retry impact calculation.
- Add named error/repair responses across planning, run creation, stage sync, review, retry, and compose.
- Add production observability events and runbook-ready metrics.
- Upgrade the frontend production monitor into a control room.
- Add mocked full episode E2E from planning to final compose.

Acceptance:

- A locked series and episode can generate a production plan, split into segments, run image stage, pass review, run video stage, pass review, compose, and write final video records.
- A failed segment can be retried without overwriting previous versions.
- The operator can pause and resume queued work.
- The operator can see cost and provider trace for every segment.

Stage 1 implementation should be split into three milestones:

#### Stage 1A: Backend Control-Plane Binding

Deliverables:

- Add and backfill `production_plan_id` and `production_episode_id`.
- Add `production_link_status` and deterministic repair statuses for legacy runs.
- Add `ProductionJob.resume_status`, `blocked_reason`, and `paused_at` or an equivalent pause ledger.
- Normalize run-tree lookup around real foreign keys.
- Add segment detail, retry impact, and costs read APIs.
- Make `GET /runs/{run_id}` summary-only for linked runs and move asset detail to segment detail/review APIs.
- Add compatibility repair responses for ambiguous legacy runs.

Exit gate:

- Existing staged production still works.
- New linked runs can be created from persisted production plans.
- No frontend rewrite depends on guessed `model_trace_json` plan ids.

#### Stage 1B: Linked Stage Execution

Deliverables:

- Build image, video, and compose payloads from `ProductionSegment` rows for linked runs.
- Write Segment, asset, review, and cost status during stage submit/sync.
- Add one bottom-up status aggregation service for Segment -> Shot -> Scene -> Episode -> Plan.
- Add pause, resume, retry, and retry-impact mutation paths.
- Preserve old asset and review versions.

Exit gate:

- Mocked backend integration can complete planning -> image -> review -> video -> review -> compose -> final write-back.
- Segment retry does not overwrite previous versions.
- Pause does not cancel running Pixelle tasks.

#### Stage 1C: Operator Control Room

Deliverables:

- Upgrade production monitor around tree + segment detail + action panel.
- Add run health strip, stage timeline, exception queue, and selected Segment detail tabs.
- Add explicit autopilot mode so manual stage sync buttons do not dominate the happy path.
- Add retry impact dialog.
- Add run controls for pause, resume, retry, and cost view.
- Add explicit loading, empty, blocked, stale-version, provider-failed, and paused states.
- Add responsive desktop/tablet/mobile layouts and keyboard/screen-reader support.

Exit gate:

- The operator can start from an episode, watch every stage, inspect a failed Segment, preview retry impact, retry it locally, and continue production without leaving the production context.
- The operator can identify the next required human action in under five seconds on desktop and mobile.

### Stage 1 Product Metrics

Stage 1 is successful when these are true in mocked E2E and local QA:

- One sentence or episode brief can lead to a persisted plan, linked production run, started autopilot image stage, and visible control room without the user manually sequencing internal APIs.
- A 3-8 minute episode can be represented as at least 30 Segments without flat-loading all assets into the main run payload.
- Every Segment has visible status, latest asset version, review state, retryability, provider trace, and cost trace.
- The happy path requires no manual Segment-by-Segment approval when AI review passes.
- Any failed Segment gives a local retry action and a visible impact preview.
- Final composition writes back to `Episode.video_url`, duration, status, and video library records.
- Every blocking failure has a named `error_code` and visible repair action.
- A maintainer can inspect run-level metrics/events to identify which stage, provider, model, or review gate is blocking production.

### Stage 2: Volume And Collection Scale

Goal: expand from stable single-episode production to multi-episode and Volume-aware production.

Deliverables:

- Add `ProductionVolume`.
- Add `/api/director/series-plan`.
- Add Volume-aware `episode-plan` generation.
- Add collection-level progress and cost rollups.
- Add collection compose retry that does not disturb approved episode videos.
- Add production tree Volume level.
- Add pagination and branch loading for large trees.
- Add cached aggregate counters on plan, volume, and episode rows.

Acceptance:

- A series can be planned into Volumes and Episodes.
- Operators can inspect Volume progress without loading every segment.
- Approved episodes remain safe when collection composition fails.

### Stage 3: Queue Hardening And Provider Operations

Goal: make production resilient under longer runs and provider instability.

Deliverables:

- Harden `ProductionJob` leases and stale job recovery.
- Add provider concurrency limits.
- Add stage polling backoff and jitter.
- Add retry-after handling for provider rate limits.
- Add asset copy/register background handling with checksum and size.
- Add cleanup/repair actions for missing assets.
- Add manual paid-provider smoke checklist.

Acceptance:

- Provider timeout does not lose run state.
- Rate limits pause only affected jobs.
- Missing or inaccessible assets are visible and repairable.

### Stage 4: Long-Form Operator Experience

Goal: make 240+ minute production manageable without hiding operational complexity.

Deliverables:

- Virtualized production tree.
- Saved filters and review queues.
- Batch low-risk approval.
- Batch retry with impact preview.
- Character drift freeze workflow.
- Style drift reports across episodes.
- Episode and Volume acceptance gates.

Acceptance:

- Thousands of segments can be filtered and reviewed without loading the full tree at once.
- Drift issues can block only affected branches.
- Operators can manage review backlog from the production context.

## Test Plan

Backend tests:

- `test_video_production_start_flow_contract.py`
  - one user-facing start flow ensures style lock, creates/reuses plan, creates segments, creates a linked run, starts autopilot, and returns the control-room route.
- `test_video_production_named_errors.py`
  - style lock missing, storyboard missing, missing segments, ambiguous run link, stale asset, provider failure, and budget block return named error codes with repair actions.
- `test_video_production_observability_events.py`
  - planning, run creation, stage submit/sync, review, retry, pause/resume, budget block, and final write-back emit structured events with redacted model metadata.
- `test_video_production_migration_backfill.py`
  - backfills uniquely resolvable runs, marks ambiguous runs, and avoids trace lookup after link status is set.
- `test_director_episode_plan.py`
  - creates production plan, episode, scenes, and shots from a locked series.
- `test_director_shot_segments.py`
  - splits long shots into 5-8 second segments and records continuity links.
- `test_video_production_run_binding.py`
  - run creation links `VideoProductionRun` to `ProductionPlan` and `ProductionEpisode`.
- `test_video_production_linked_vs_legacy_builders.py`
  - linked runs build image/video/compose payloads from `ProductionSegment`; legacy runs keep storyboard fallback.
- `test_video_production_asset_latest_invariant.py`
  - old latest assets are demoted in the same transaction before a new latest version is created.
- `test_video_production_status_aggregation.py`
  - segment state changes recompute Shot, Scene, Episode, and Plan statuses.
- `test_video_production_pause_resume.py`
  - pause blocks queued jobs and resume restores them.
- `test_video_production_pause_resume_status_snapshot.py`
  - resume restores the recorded `resume_status` and does not guess from `blocked`.
- `test_video_production_retry_scope.py`
  - run/episode/shot/segment retry preserves old versions and blocks only affected downstream nodes.
- `test_video_production_retry_impact.py`
  - retry impact is returned before mutation and reports continuous downstream segments.
- `test_video_production_costs_api.py`
  - returns actual, estimated, stage, provider, and budget summaries.
- `test_video_production_cost_unknown_estimate.py`
  - missing pricing metadata returns `estimate_status: "unknown"` with reasons.
- `test_video_production_segment_detail_api.py`
  - returns latest assets, paginated history, reviews, provider trace, allowed actions, and repair instructions for one Segment.
- `test_video_production_segment_detail_query_shape.py`
  - a 30+ Segment run does not require loading every run asset for one Segment detail response.
- `test_video_production_legacy_run_linking.py`
  - ambiguous legacy runs return repair instructions instead of guessing from JSON trace.
- `test_video_production_review_latest_version.py`
  - stale asset approval cannot unlock the next stage.
- `test_video_production_partial_pixelle_failure.py`
  - partial stage failures save successful assets and mark failed segments retryable.
- `test_video_production_pause_running_provider.py`
  - pausing a run blocks queued jobs but does not cancel already running Pixelle tasks.
- `test_video_production_retry_transaction_rollback.py`
  - failed retry transaction leaves old latest assets and segment statuses intact.
- `test_video_production_control_plane_e2e.py`
  - mocked planning -> image -> image review -> video -> video review -> compose -> final write-back.

Frontend tests:

- `production-control-room.test.js`
  - renders tree, selected segment, stage steps, provider trace, and action panel.
- `production-run-summary.test.js`
  - linked runs render without relying on an all-assets payload from `GET /runs/{run_id}`.
- `production-control-room-autopilot.test.js`
  - happy-path automation shows current work and next blocker without requiring manual stage buttons.
- `production-run-controls.test.js`
  - pause, resume, retry, and costs call the correct APIs and refresh visible state.
- `production-retry-impact.test.js`
  - retry dialog shows downstream scope and estimated cost before confirmation.
- `production-segment-detail.test.js`
  - selected segment loads detail payload instead of relying on sparse tree data.
- `production-control-room-responsive.test.js`
  - verifies desktop three-column layout, tablet two-column layout, and mobile tree drawer/sticky action bar.
- `production-control-room-a11y.test.js`
  - verifies keyboard tree navigation, visible focus, selected Segment semantics, live status updates, and text labels for status colors.
- `production-control-room-empty-states.test.js`
  - verifies missing plan, missing segments, ambiguous legacy run, stale asset, provider failure, paused, and budget-blocked recovery states.
- `review-center-production-targets.test.js`
  - review center deep-links to run, segment, asset version, and stale conflict state.

Pixelle tests:

- Stage image/video/compose contracts remain stable.
- Stage auth rejects missing API key when runtime credentials are present.
- Seedance provider continues to use `/api/plan/v3`.
- Stage task status returns structured per-asset failures.

## Migration Order

1. Add nullable database fields and migration.
2. Backfill production run links where uniquely resolvable and mark ambiguous legacy runs.
3. Add latest-version and review-target serializers without changing behavior.
4. Add director planning route aliases and make segmentation idempotent.
5. Bind new runs to production plans and make tree lookup prefer real columns over JSON trace.
6. Add read-only segment detail, retry impact, and costs APIs.
7. Update stage submit/sync to read and write `ProductionSegment` state for linked runs.
8. Add pause/resume/retry control APIs.
9. Upgrade frontend control room against the detail and control APIs.
10. Add mocked E2E.
11. Add manual paid-provider smoke checklist.

This order keeps existing staged production usable while the control plane becomes authoritative.

## Success Criteria

The next stage is complete when:

- `production_*` is the source of truth for episode production status.
- `VideoProductionRun` is linked to production plan rows and no longer acts as an isolated state machine.
- Every Segment has visible status, latest asset version, review state, retryability, model trace, and cost trace.
- The production monitor shows all major backend steps.
- Segment retry is local and versioned.
- Pause/resume works for queued work.
- Mocked full episode E2E passes.
- Existing auto-plan, model center, Pixelle stage APIs, and review center regressions pass.

## Open Decisions Resolved

- Use `VideoReviewRecord` as the unified review table for the next stage.
- Defer `ProductionVolume` until single-episode production is stable.
- Do not require paid-provider E2E as a merge gate.
- Keep Pixelle-Video execution-only.
- Keep dy_auto as the only model configuration authority.

## GSTACK REVIEW REPORT

Review run: `/autoplan` on 2026-05-26.

Restore point:

`C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260526-103018.md`

### Scope Decision

Mode: selective expansion.

The plan remains focused on Stage 1 control-plane convergence. The review rejected expanding into full `ProductionVolume`, 240+ minute end-to-end production, multi-user workflow, or provider fallback chains in the next implementation stage. The accepted expansion is narrower but important: add segment detail and retry impact APIs before frontend work so the control room is driven by stable backend contracts.

### CEO Review

Premises accepted:

- dy_auto should own orchestration state.
- Pixelle-Video should stay execution-only.
- `production_*` should become the long-video source of truth.
- The first implementation target should be stable 3-8 minute episode production, not 240+ minute end-to-end production.

Strategic corrections applied:

- The plan now explicitly says linked production runs must build payloads from `ProductionSegment` rows, not `storyboard_json`.
- The plan now treats trace-based run linking as temporary migration compatibility, not a permanent mechanism.
- The plan now defers `ProductionVolume` while keeping a path to add it without changing Segment semantics.

### Design Review

Initial rating: 7/10.

Main gap: the control room described a tree and action panel, but the frontend could not obtain enough data from the current sparse tree API. The plan now requires `GET /api/video-production/segments/{segment_id}/detail` so the UI can show latest assets, historical versions, reviews, provider trace, model trace, cost, allowed actions, and repair instructions without reverse-engineering multiple payloads.

Remaining design constraint:

- The implementation plan must specify exact empty, loading, failed-provider, stale-version, blocked-review, and paused states for the control room.

### Plan Design Review

Review run: `/plan-design-review` on 2026-05-26.

Mockup status: `DESIGN_NOT_AVAILABLE`. The local gstack designer binary was not available, so this review used a text-only plan critique and existing Vue screens as evidence. Visual mockups should still be generated before final UI polish if the designer tool becomes available.

Design completeness rating: 6/10 -> 8.5/10 after this revision.

What a 10/10 plan would add next:

- approved visual mockups for desktop, tablet, and mobile control room
- exact component inventory and reusable Vue component names
- final copy strings for all recovery banners
- final keyboard interaction spec for tree navigation

Ratings after revision:

| Dimension | Before | After | Resolution |
|---|---:|---:|---|
| Information architecture | 6/10 | 9/10 | Added run health strip, stage timeline, exception queue, production tree, Segment detail, and action hierarchy. |
| Interaction state coverage | 5/10 | 9/10 | Added fixed user-facing state taxonomy, state-specific recovery copy, retry impact dialog, and autopilot/manual-control rules. |
| User journey | 6/10 | 8/10 | Clarified the default autopilot path and human exception path. |
| Visual specificity | 5/10 | 8/10 | Added local design baseline because no `DESIGN.md` exists. |
| AI slop risk | 6/10 | 9/10 | Explicitly rejected marketing layout, decorative card grids, nested cards, and raw JSON-first traces. |
| Responsive behavior | 4/10 | 8/10 | Added desktop/tablet/mobile layout rules, tree drawer, stage timeline behavior, and sticky mobile action bar. |
| Accessibility | 3/10 | 8/10 | Added keyboard navigation, focus, live regions, text status labels, contrast, and touch target requirements. |

Findings applied in this revision:

| Severity | Finding | Resolution |
|---|---|---|
| P1 | The control room could become a manual step-by-step cockpit, breaking the one-sentence autopilot promise. | Added autopilot design rules and moved manual sync controls out of the happy-path hierarchy. |
| P1 | The operator would not know the next required human action quickly enough. | Added five-second success criteria and a first-screen hierarchy focused on health, blocker, exception queue, and selected Segment. |
| P1 | Retry was described technically but not as a trust-building interaction. | Added retry impact dialog content, scope-specific confirmation copy, and disabled-confirm rules. |
| P2 | State names risk leaking backend vocabulary into the UI. | Added user-facing state taxonomy with visual treatment and primary actions. |
| P2 | Empty/error states were still generic. | Added state-specific recovery copy examples for missing segments, ambiguous legacy links, stale assets, and provider failures. |
| P2 | Responsive behavior was underspecified. | Added desktop, tablet, and mobile layout requirements. |
| P2 | Accessibility would likely be missed if not explicit. | Added keyboard, ARIA, live-update, contrast, and touch target requirements. |

### OpenClaw CEO Review

Review run: `/gstack-openclaw-ceo-review` on 2026-05-26.

Mode decision: `HOLD SCOPE`.

Reason: the current Stage 1 already crosses data model, routers, services, frontend, review, retry, costs, and provider execution. Expanding into Volume UI, provider fallback chains, multi-user review assignment, or 240+ minute production would dilute the next implementation. The correct CEO move is to hold the Stage 1 boundary but raise the standard inside it.

Alternative approaches considered:

| Approach | Effort | Risk | Decision |
|---|---:|---:|---|
| Minimal viable: repair current staged monitor and keep storyboard as execution source | M | Medium | Rejected because it does not solve long-video consistency or Segment-level retry. |
| Recommended: Stage 1 control-plane convergence with one user-facing start flow, named errors, observability, and Segment source of truth | L | Medium | Accepted. This is the narrowest version that protects the product promise. |
| Ideal architecture: add Volume, full collection orchestration, provider fallback, team review workflow, and paid-provider canary | XL | High | Deferred until Stage 1 is stable. |

Strongest CEO challenges applied:

| Severity | Challenge | Resolution |
|---|---|---|
| P1 | The plan could ship as technically correct but still force users to manually understand internal pipeline steps. | Added North-Star User Flow Contract requiring one visible start flow from series/episode context into an autopilot run and control room. |
| P1 | Failure handling was still too generic for a production workflow that spends real provider money. | Added named error and repair contract with minimum error codes and required repair fields. |
| P1 | Observability was treated mostly as UI visibility, not as a production operating system. | Added metrics, structured audit events, and operator runbook requirements. |
| P2 | The roadmap could drift back toward 240+ minute scope before the episode wedge is stable. | Added Stage 1 scope mode and explicitly held Volume, fallback chains, multi-user review, and 240+ minute production out of Stage 1. |

CEO verdict:

- The plan is ready for implementation planning only if the next plan starts with the one user-facing start flow and named repairable errors.
- Do not start with the control room UI alone. A beautiful monitor on top of a manually sequenced backend would miss the product.
- Do not start with Volume. The single-episode control plane is the wedge.

### Engineering Review

Findings fixed in this document:

| Severity | Finding | Resolution |
|---|---|---|
| Critical | `VideoProductionRun` could remain an isolated state machine. | Added rule that linked runs use `ProductionSegment` payload builders and status writes. |
| Critical | Tree lookup currently guesses from `model_trace_json`. | Added real FK migration, backfill, repair errors for ambiguous legacy runs, and temporary trace fallback only. |
| High | Director route contract conflicted with existing `/episode-production-plan`. | Added compatibility alias and one shared idempotent service. |
| High | Asset/review version truth was incomplete. | Added missing asset fields, review target fields, indexes, latest-version invariant, and stale human approval failure. |
| High | Pause/resume/retry/cost APIs lacked implementation shape. | Added `resume_status` or pause ledger, `blocked_reason`, costs API requirements, and retry impact dry-run endpoint. |
| High | Retry did not protect continuity-dependent downstream segments. | Added transactional retry rules and continuity-mode impact rules. |
| Medium | State vocabulary conflicted with current constants. | Added stored-state compatibility table and API normalization rule. |
| Medium | Frontend acceptance was not reachable from current API. | Added segment detail API dependency and frontend test requirement. |
| Medium | Migration order could mutate stages before links/version truth existed. | Reordered migration to bind and expose read-only data before changing stage sync writes. |
| Medium | Tests missed dangerous compatibility boundaries. | Added legacy ambiguity, partial Pixelle failure, pause-running-provider, retry rollback, and segment detail tests. |

### Plan Engineering Review

Review run: `/plan-eng-review` on 2026-05-26.

Step 0 scope decision: proceed with Stage 1, but keep it split into 1A/1B/1C. The complexity check is intentionally triggered because this touches migrations, services, routers, and frontend. The reduction is not to delete scope; it is to keep implementation ordered so Stage 1A exposes stable read contracts before Stage 1B mutates execution behavior.

Findings applied in this revision:

| Severity | Finding | Confidence | Resolution |
|---|---|---:|---|
| P1 | Latest-asset uniqueness was service-level only and could drift across SQLite/MySQL if implemented with a partial-index assumption. | 9/10 | Added cross-DB invariant: demote old latest assets and insert/promote new latest in one transaction; do not rely on partial unique indexes as the only guard. |
| P1 | Run backfill needed a deterministic link status so ambiguous legacy runs are not repeatedly guessed from trace JSON. | 9/10 | Added `production_link_status` values and repair behavior for `linked`, `legacy_unlinked`, `ambiguous`, and `missing_plan`. |
| P1 | Pause/resume could not safely restore jobs because current jobs only store `blocked` and error code. | 9/10 | Added `resume_status`, `blocked_reason`, and `paused_at` or an equivalent pause ledger as Stage 1A data requirements. |
| P1 | Linked stage execution still needed a hard dual-path contract to avoid silently reusing storyboard-frame builders. | 9/10 | Added linked vs legacy execution section with required builder ownership and forbidden `production_*` mutation from legacy runs. |
| P1 | Parent status updates were underspecified and risked scattered, inconsistent router writes. | 8/10 | Added one bottom-up aggregate status service and parent-state rules. |
| P2 | Segment detail could become an N+1/full-run asset load endpoint. | 8/10 | Added query contract: selected Segment only, capped/paginated history, no whole-run asset hydration, plus a 30+ Segment query-shape test. |
| P2 | Cost estimates could falsely report zero when model pricing is unknown. | 8/10 | Added explicit `estimate_status: "unknown"` and `unknown_estimate_reasons` contract. |
| P2 | Review target fields could drift from asset target fields. | 8/10 | Added review-time snapshot requirement for `target_type`, `target_id`, `production_segment_id`, and `asset_version`. |

Engineering acceptance note:

- The next implementation plan must name the exact migration revision, linked-run resolver service, production-stage payload builders, status aggregation service, and control-room API client functions. If those names are missing, implementation will likely reintroduce the current storyboard-centered behavior.

### DX Review

Developer persona: dy_auto maintainer implementing the next production-control-plane slice.

DX concerns:

- The plan is implementable, but only if route aliases, state vocabulary, and linked-run migration rules are frozen before coding.
- The implementation plan must name exact files and test commands because the current repo has a large dirty worktree and adjacent unrelated changes.
- The paid-provider smoke checklist must stay manual and separate from mocked CI tests.

### Final Autoplan Verdict

Status: `DONE_WITH_CONCERNS`.

The plan is now ready for implementation planning, not immediate coding. The next step should be a `writing-plans` pass that turns Stage 1 into a file-by-file implementation plan with migration, service, router, frontend, and test checkpoints.

### Stage 1 Implementation Plan

Implementation plan written:

`docs/superpowers/plans/2026-05-26-video-production-control-plane-stage1.md`

The implementation plan preserves Stage 1 scope and starts from the one user-facing start flow, named repairable errors, and production observability before frontend polish.
