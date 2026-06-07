# Series Continuity and AI Text Artifact Transparency Design

Date: 2026-06-08

Status: Approved by user for automated spec and review flow. Awaiting implementation plan.

Related user request:

> 系统不应该是多个剧集的吗? 怎么一集就没了，而且必须要保证系列剧集的剧情链接合理性和人物一致性。现在还存在暗箱操作，AI 的所有产出都应该展示出来进行追溯，并要支持人工调整或 AI 重新生成。这些产出包括所有的文字信息的产出，比如剧本、分镜剧本、台词等。

## Goal

Fix the series production model so a one-sentence idea becomes a real multi-episode series, not a single completed episode pretending the full series is done. The system must:

1. Create and preserve the full target episode set for a series.
2. Keep plot continuity, character consistency, world rules, foreshadowing, and prior episode state connected across episodes.
3. Make every AI text output visible, versioned, reviewable, editable, regeneratable, approvable, and traceable to the video run that consumed it.
4. Prevent video production from silently consuming unapproved or stale text artifacts.
5. Repair existing broken series such as `f49718b7-e0ec-4012-b7fa-5c5229105d47`, whose database state has `total_episodes=30` but only one persisted episode.

## Existing System Context

Observed from the current codebase and database:

- `server/app/services/one_sentence_video_service.py` creates a `Series(total_episodes=1)` and only creates episode 1 for the one-sentence path.
- `server/app/routers/series.py` already creates placeholder `Episode` rows for `range(1, total_episodes + 1)` in the normal series creation path.
- The real series `f49718b7-e0ec-4012-b7fa-5c5229105d47` has:
  - `Series.total_episodes = 30`
  - persisted episode count = 1
  - episode 1 status = `done`
  - no persisted `EpisodeScript` rows
- `web/src/views/SeriesDetailPage.vue` derives the next runnable episode from existing `episodes`. If only E01 exists and E01 is done, there is no E02 for the UI to offer.
- `server/app/services/script_pipeline.py` already persists structured script artifacts in `EpisodeScript`, `ScriptDramaticBeat`, `ScriptSceneOutline`, and `ScriptVisualShot`, and writes compatibility snapshots into `Episode.script_json` and `Episode.storyboard_json`.
- `AgencyCreativePatch` and `CreativePatchWorkbench` already support expert patches for script, storyboard, image prompt, video prompt, and edit manifests, but they are not a universal text artifact ledger.
- `AIVideoReviewPage.vue` and `AgencyConsolePage.vue` expose useful traces, model reviews, and repair records, but not a complete browse/edit/regenerate/approve workflow for all AI text outputs.

Reusable project pieces:

- `Series.total_episodes`, `Episode.episode_number`, `Episode.status`
- `Series.story_bible_json`, `Series.style_lock_json`
- `Character`, `Scene`, and asset/reference anchor systems
- `EpisodeScript`, `ScriptDramaticBeat`, `ScriptSceneOutline`, `ScriptVisualShot`
- `PipelineRun.layers_json`
- `AgencyExpertInvocation` and agency trace persistence
- `ProductionPlan`, `ProductionEpisode`, `ProductionScene`, `ProductionShot`, `ProductionSegment`
- `AgencyCreativePatch`
- Existing frontend series detail, production monitor, agency console, and creative patch UI patterns

## Chosen Approach

Use the "planned series plus pilot-first production" approach.

The system should generate the complete series plan and episode placeholders immediately, but it does not have to render every video at once. For example, a one-sentence request can create a 30-episode series, generate story bible and E01-E30 outlines, then start producing E01. After E01 is done, the next action is "生成第 2 集", not "全部剧集已完成".

This approach keeps product cost under control while preserving the user's mental model: the series exists as a series from the start.

## Requirements

### Multi-Episode Series Creation

1. One-sentence series creation must persist `Series.total_episodes` from the requested target. Default to 30 when no explicit target is provided.
2. The system must create `Episode` placeholders from episode 1 through `Series.total_episodes`.
3. Episode placeholders must be idempotent. Running repair twice must not create duplicates.
4. A series with only E01 done and `total_episodes > 1` is not completed.
5. Existing series with missing placeholders must be repairable through a service and API.

### Series Planning

On creation or repair, the system must be able to produce:

1. `series_bible`
   - world rules
   - genre and tone
   - protagonist/antagonist goals
   - core conflict
   - character sheets
   - character relationships
   - style lock
   - continuity constraints
2. `episode_outline` for every target episode
   - title
   - episode goal
   - previous episode handoff
   - central conflict
   - character state changes
   - foreshadowing introduced/resolved
   - cliffhanger or next hook
3. `continuity_ledger`
   - episode timeline
   - character state timeline
   - open foreshadowing
   - resolved foreshadowing
   - forbidden contradictions
   - visual continuity anchors

### Episode Generation Context

Before generating an episode script, storyboard, dialogue, image prompts, or video prompts, the system must assemble context from approved artifact versions:

1. Latest approved `series_bible`
2. Latest approved `episode_outline` for the target episode
3. Latest approved previous episode summary, when `episode_number > 1`
4. Latest approved character state after the previous episode
5. Open foreshadowing and unresolved plot obligations
6. Approved style lock and visual anchors

If any required approved artifact is missing, production must fail with an actionable reason instead of silently inventing missing context.

### AI Text Artifact Transparency

All AI-generated text outputs must be stored as first-class versioned artifacts, including:

- `series_bible`
- `episode_outline`
- `continuity_ledger`
- `episode_summary`
- `character_state`
- `episode_script`
- `dialogue`
- `storyboard`
- `image_prompt`
- `video_prompt`
- `review_output`
- `repair_plan`

Each artifact version must record:

- input prompt or structured input
- full output
- model/provider trace
- expert review trace, when any
- source type: `ai`, `human_edit`, `ai_regenerate`, `expert_patch`, `migration`
- parent artifact version, when derived from another version
- status: `draft`, `review_pending`, `approved`, `superseded`, `rejected`, `stale`
- downstream consumers, especially video production runs and segments

Artifacts must never be overwritten in place. Manual editing and AI regeneration always create a new version.

Each artifact type must have a typed validator or serializer. The universal ledger stores all text artifacts, but implementation must not accept arbitrary unvalidated JSON for critical artifact types such as `series_bible`, `episode_outline`, `episode_script`, `storyboard`, `image_prompt`, and `video_prompt`.

### Approval and Consumption Rules

1. Video production consumes approved artifact versions only.
2. A `VideoProductionRun` or equivalent run record must bind the exact artifact ids it consumed.
3. A run must continue to show the artifact versions it used even if newer versions are later approved.
4. Approving a new upstream artifact version must mark downstream dependent artifacts as `stale` when they were derived from older content.
5. The UI must show stale state and offer targeted regeneration, such as "基于新版剧本重生分镜".

### Security and Audit Rules

Manual edit, AI regeneration, approve, reject, and repair actions alter production inputs. They must:

1. Require the same authentication model used by the rest of the application.
2. Record actor identity when available.
3. Record before/after lineage and source type.
4. Write an audit event for approvals, rejections, human edits, AI regenerations, and production starts that consume artifacts.
5. Treat user-edited artifact content as untrusted content, not system instructions for tools or providers.
6. Reject mutation requests when the caller lacks permission, with a stable error code.

### Concurrency and Idempotency Rules

Artifact and production actions must be safe under double clicks, retries, and concurrent reviewers.

1. Approval must use optimistic concurrency or a database constraint so only one active approved version can exist for a target/type.
2. If two approvals race, one succeeds and the other receives a conflict response.
3. Regenerate, edit, approve, reject, repair placeholders, and start production should accept or derive an idempotency key.
4. Repeating the same idempotent request must return the existing result or a clear conflict, not create duplicate versions/runs.
5. Production start must re-check artifact status at commit time before binding consumers.

## Data Model

### New Table: `ai_text_artifacts`

Add a universal text artifact ledger.

Suggested fields:

```text
id
series_id
episode_id nullable
run_id nullable
production_plan_id nullable
target_type
target_id
artifact_type
version
status
source_type
parent_artifact_id nullable
input_json
content_json nullable
content_text nullable
model_trace_json nullable
review_trace_json nullable
consumer_trace_json nullable
created_by nullable
created_at
approved_at nullable
superseded_at nullable
stale_reason nullable
```

Suggested constraints and indexes:

- Unique version per `(target_type, target_id, artifact_type, version)`.
- Fast lookup by `(series_id, artifact_type, status)`.
- Fast lookup by `(episode_id, artifact_type, status)`.
- Fast lookup by `(parent_artifact_id)`.
- Enforce at most one active approved artifact per `(target_type, target_id, artifact_type)` using a database-level strategy when the dialect supports it safely. Keep an application-level optimistic locking fallback for dialects where a partial unique index is not available.

### New Table: `ai_text_artifact_consumers`

Bind production runs, plans, shots, and segments to the exact text versions they consumed.

Suggested fields:

```text
id
artifact_id
consumer_type
consumer_id
series_id
episode_id nullable
run_id nullable
created_at
metadata_json nullable
```

This table answers: "Which AI text did this video segment come from?"

### Compatibility Snapshots

Keep existing snapshot fields for compatibility:

- `Series.story_bible_json`
- `Series.style_lock_json`
- `Episode.script_json`
- `Episode.storyboard_json`
- `PipelineRun.layers_json`

The new artifact ledger becomes the source of truth for traceability and versioning. Snapshot fields remain read-optimized compatibility caches.

## Services

### `series_planning_service`

Responsibilities:

- `ensure_episode_placeholders(series_id)`
- `repair_missing_episode_placeholders(series_id)`
- `is_series_completed(series_id)`
- `next_producible_episode(series_id)`

Rules:

- Completion is true only when all persisted target episodes are `done` or equivalent final state.
- If `Series.total_episodes > episode_count`, the series is incomplete and repairable.
- Placeholder creation is idempotent.

### `series_story_planner_service`

Responsibilities:

- Generate `series_bible` artifact.
- Generate all `episode_outline` artifacts.
- Generate initial `continuity_ledger` artifact.
- Update `Episode.title`, `Episode.summary`, and status snapshots from approved outline artifacts.

This service should reuse existing AI provider/config infrastructure instead of creating a new model runtime.

### `ai_text_artifact_service`

Responsibilities:

- `create_artifact`
- `latest_artifact`
- `list_versions`
- `approve_artifact`
- `reject_artifact`
- `edit_artifact`
- `regenerate_artifact`
- `mark_downstream_stale`
- `bind_consumer`
- `lineage`

Rules:

- Editing creates `source_type=human_edit` and `parent_artifact_id`.
- Regeneration creates `source_type=ai_regenerate` and `parent_artifact_id`.
- Approval supersedes the previous approved artifact of the same target/type.
- Approval of upstream content marks downstream derived artifacts stale.

### `episode_generation_context_service`

Responsibilities:

- Assemble approved context for episode generation.
- Validate required artifacts by episode number and artifact type.
- Produce a clear missing-context report.

For E02 generation, the required context should include:

```text
Series Bible vN
Episode Outline E02 vN
Episode Summary E01 vN
Character State after E01 vN
Open Foreshadowing vN
Style Lock vN
Visual Anchors vN
```

### `video_production_artifact_binding`

Responsibilities:

- Validate approved artifact versions before run start.
- Bind consumed artifact ids to run/plan/segment records.
- Expose the consumed versions in production monitor responses.

## API Design

Add or extend endpoints:

```text
POST /api/series/{series_id}/ensure-episodes
POST /api/series/{series_id}/plan
GET  /api/series/{series_id}/plan
POST /api/series/{series_id}/continuity-review

GET  /api/ai-text-artifacts?series_id=&episode_id=&artifact_type=
GET  /api/ai-text-artifacts/{id}
GET  /api/ai-text-artifacts/{id}/lineage
GET  /api/ai-text-artifacts/{id}/diff?against_id=
POST /api/ai-text-artifacts/{id}/approve
POST /api/ai-text-artifacts/{id}/reject
POST /api/ai-text-artifacts/{id}/edit
POST /api/ai-text-artifacts/{id}/regenerate

POST /api/video-production/runs/start
GET  /api/video-production/runs/{run_id}
```

`POST /api/video-production/runs/start` must reject production when required approved artifacts are missing or stale. The response must include actionable error codes.

List endpoints must support pagination and filters for status, artifact type, episode number, source type, and stale state. Mutation endpoints should support an idempotency key header or request field.

Example missing-context response:

```json
{
  "error": "missing_required_text_artifacts",
  "series_id": "f49718b7-e0ec-4012-b7fa-5c5229105d47",
  "episode_number": 2,
  "missing": [
    {
      "artifact_type": "episode_outline",
      "target": "episode:2",
      "action": "generate_or_approve_episode_outline"
    }
  ]
}
```

Additional stable error codes:

| Error code | Trigger |
| --- | --- |
| `artifact_approval_conflict` | Another version became the active approved artifact first. |
| `artifact_mutation_forbidden` | Caller cannot edit, regenerate, approve, or reject this artifact. |
| `artifact_validation_failed` | Artifact content does not match the type-specific schema. |
| `artifact_regeneration_failed` | AI regeneration failed or returned malformed output. |
| `planning_generation_failed` | Series bible or episode outline generation failed. |
| `idempotency_conflict` | Same idempotency key was reused with different inputs. |

## Frontend Design

### Series Detail Page

Update `web/src/views/SeriesDetailPage.vue` so the first viewport clearly shows:

- target episode count
- persisted episode count
- planned episode count
- done episode count
- next producible episode
- continuity status
- missing planning/approval actions

Button behavior:

- E01 done and E02 exists or can be repaired: `生成第 2 集`
- production active: `剧集生产中，打开监控`
- missing plan: `补齐系列规划`
- missing approved text artifact: `审查并批准文本产出`
- all target episodes done: `全部剧集已完成`

The phrase `全部剧集已完成` must only appear when every target episode is complete.

### Series Plan Page

Add a planning view for:

- story bible
- character sheets and relationships
- style lock
- E01-E30 outline list
- continuity ledger
- foreshadowing tracker
- character state timeline
- visual anchors

Each block must show:

- current approved version
- draft or stale versions
- AI input
- AI output
- model trace
- review trace
- edit/regenerate/approve/reject actions
- downstream consumers

The page must include loading, empty, partial-planning, and error states. Large episode lists should be lazy-loaded or virtualized rather than rendering every artifact for every episode at once.

### AI Text Artifact Workbench

Add a reusable workbench component.

Left panel:

- Series
  - story bible
  - style lock
  - continuity ledger
  - foreshadowing
  - character states
- Episode
  - outline
  - script
  - dialogue
  - storyboard
  - image prompts
  - video prompts
  - review outputs

Center panel:

- structured artifact content
- diff between versions
- readable rendering for scripts and storyboard

Right panel:

- status
- source type
- parent version
- model trace
- review trace
- consumers
- actions

Required actions:

- manual edit
- AI regenerate
- approve
- reject
- view lineage
- regenerate downstream artifacts when stale

Workbench requirements:

- Default to a "needs action" view that highlights missing approvals, stale artifacts, and failed regenerations.
- Support search and filters by episode, artifact type, status, and source type.
- Support keyboard navigation for core actions.
- Preserve responsive behavior for narrow screens by collapsing the version/action panel behind a tab or drawer.

### Video Production Monitor

Show the exact consumed artifact versions, for example:

```text
Series Bible v3
Episode Outline E02 v2
Episode Script E02 v4
Storyboard E02 v2
Image Prompt Set E02 v3
Video Prompt Set E02 v3
```

This turns production from a black box into a reproducible chain.

## Continuity Rules

### Story Continuity

Each episode generation must read from the approved continuity context. After the episode completes, generate a continuity writeback package:

- episode summary
- character state changes
- relationship changes
- new foreshadowing
- resolved foreshadowing
- new contradictions or risks
- next episode hook

The writeback package is an artifact and must be reviewed before it becomes the next episode's source context.

### Character Consistency

Every character reference in script, storyboard, and prompts should resolve to a stable character id when possible.

Rules:

- First character creation writes or links `Character`.
- Repeated appearances use the same `character_id`.
- Visual prompts inherit approved character anchors and reference images.
- A character design change marks downstream prompts and rendered assets stale.
- Production should warn when a major character appears without a visual anchor.

### Scene and Style Consistency

Scene and world references should resolve to stable scene ids or world-rule ids when possible.

Rules:

- Recurring locations use stable `scene_id`.
- Style lock changes mark image/video prompts stale.
- Prompt generation must include approved style lock and continuity constraints.

## State Model

### Series Status

Use or derive these states:

```text
draft
planning
planned
producing
partially_completed
completed
blocked
```

`completed` is valid only when all target episodes are complete.

### Episode Status

Use or derive these states:

```text
pending
planned
scripting
script_review_pending
storyboard_pending
storyboard_review_pending
production_ready
rendering
final_review_pending
done
blocked
```

### Text Artifact Status

```text
draft
review_pending
approved
superseded
rejected
stale
```

## Error and Rescue Map

| Error code | Trigger | User-facing action |
| --- | --- | --- |
| `missing_episode_placeholders` | `total_episodes` is greater than persisted episode count | `补齐剧集占位` |
| `missing_series_plan` | No approved story bible or episode outlines | `生成系列规划` |
| `missing_approved_series_bible` | Episode production lacks approved bible | `审查并批准故事圣经` |
| `missing_approved_episode_outline` | Episode production lacks approved outline | `生成或批准本集大纲` |
| `missing_previous_episode_handoff` | E02+ lacks previous summary or character state | `运行连续性重审` |
| `stale_script` | Approved outline changed after script generation | `基于新版大纲重生剧本` |
| `stale_storyboard` | Approved script changed after storyboard generation | `基于新版剧本重生分镜` |
| `stale_prompt_set` | Storyboard or style lock changed after prompt generation | `基于新版分镜重生提示词` |
| `missing_character_anchor` | Major character lacks visual anchor | `补齐角色参考图` |
| `run_uses_superseded_artifact` | User wants latest version after old run | `用新版重新生产` |

No error should silently flip a series to completed.

## Observability and Runbook

Add metrics or structured logs for:

- episode placeholder repairs
- series planning attempts and failures
- artifact versions created by type and source
- approval/rejection counts
- stale downstream artifact counts
- production starts blocked by missing or stale artifacts
- production runs and segments bound to artifact versions
- migration dry-run and backfill results

Add a short operator runbook covering:

1. Repairing missing episode placeholders.
2. Re-running series planning after malformed AI output.
3. Resolving concurrent approval conflicts.
4. Diagnosing why production start is blocked.
5. Verifying which text artifacts a video run consumed.

## Migration and Repair

Migration steps:

1. Add `ai_text_artifacts`.
2. Add `ai_text_artifact_consumers`.
3. Provide a dry-run mode that reports rows to create/update without mutating data.
4. Migrate `Series.story_bible_json` and `Series.style_lock_json` into `series_bible` or `style_lock` artifacts with `source_type=migration`.
5. Migrate `Episode.script_json` into `episode_script` artifacts with `source_type=migration`.
6. Migrate `Episode.storyboard_json` into `storyboard`, `dialogue`, `image_prompt`, and `video_prompt` artifacts where data exists.
7. Backfill consumers from known `VideoProductionRun` and `ProductionSegment` metadata when possible.
8. Repair series where `total_episodes > persisted episode count`, including `f49718b7-e0ec-4012-b7fa-5c5229105d47`, by creating missing episode placeholders.
9. Write a migration report with created artifacts, repaired series, skipped rows, validation failures, and rollback notes.

Repair must be idempotent and log what it created. If a migration step fails, existing compatibility snapshots must remain intact.

## Acceptance Criteria

Backend tests:

- `test_one_sentence_creates_series_episode_placeholders`
- `test_completed_pilot_does_not_complete_series`
- `test_missing_placeholders_repair_is_idempotent`
- `test_start_production_requires_approved_text_artifacts`
- `test_manual_edit_creates_new_artifact_version`
- `test_regenerate_creates_child_artifact_version`
- `test_approve_script_marks_storyboard_and_prompts_stale`
- `test_video_run_binds_consumed_artifact_versions`
- `test_episode_generation_context_requires_previous_handoff_for_episode_2`
- `test_migration_creates_artifacts_from_existing_episode_snapshots`
- `test_concurrent_approval_allows_one_active_approved_version`
- `test_artifact_mutation_requires_authorization`
- `test_artifact_list_paginates_large_series`
- `test_migration_dry_run_reports_repairs_without_mutating`
- `test_idempotent_start_production_does_not_create_duplicate_runs`

Frontend tests:

- `series-detail-agency`: E01 done with `total_episodes=30` shows `生成第 2 集`, not `全部剧集已完成`.
- `series-detail-agency`: missing placeholders shows `补齐剧集占位`.
- `series-plan-page`: shows story bible, episode outlines, continuity ledger, and approval states.
- `ai-text-artifact-workbench`: supports version history, manual edit, AI regenerate, approve, reject, and lineage.
- `video-production-monitor-page`: shows consumed artifact versions.
- `ai-text-artifact-workbench`: stale downstream artifacts show targeted regeneration actions.
- `series-plan-page`: handles loading, empty, partial-planning, and error states.
- `ai-text-artifact-workbench`: supports filtering, search, pagination/lazy loading, and responsive layout.

Manual verification:

1. Create a one-sentence series.
2. Confirm E01-E30 placeholders exist.
3. Produce E01 only.
4. Confirm series detail shows E01 done and next action `生成第 2 集`.
5. Open the artifact workbench and inspect AI inputs, outputs, model traces, approvals, and consumers.
6. Manually edit E01 script.
7. Confirm a new script version is created and dependent storyboard/prompts are stale.
8. Regenerate storyboard from the edited script.
9. Start production and confirm the run binds approved artifact ids.

## Non-Goals

- Do not render all episodes automatically in the first implementation.
- Do not replace existing `EpisodeScript` structured tables; integrate them into the artifact ledger.
- Do not remove compatibility snapshots from `Series`, `Episode`, or `PipelineRun`.
- Do not create a second AI provider runtime.
- Do not hide expert patch features; link them to the artifact lineage where possible.

## Rollout Plan

1. Migration and backend models.
2. Episode placeholder repair service and tests.
3. AI text artifact service and tests.
4. Series planning service and artifact generation.
5. Episode context assembly and production start gate.
6. Frontend series detail fixes.
7. Series plan page and artifact workbench.
8. Production monitor consumed-artifact display.
9. Migration/backfill command and one-time repair for known broken series.

## Review Automation Requirements

This spec must pass:

1. Self-review for ambiguity, missing tests, and hidden state changes.
2. `plan-ceo-review` strategy/scope review.
3. `gstack-openclaw-ceo-review` independent CEO challenge.
4. `autoplan` style pipeline: CEO, design, engineering, and DX review, with auto-decisions and a decision audit trail.

Review reports must be written under `docs/superpowers/reports/` and any accepted review findings must be reflected back into this spec before implementation planning begins.

## GSTACK REVIEW REPORT

| Review | Trigger | Status | Findings |
| --- | --- | --- | --- |
| Self Review | Brainstorming spec self-review | Clear after amendments | Added auth/audit, concurrency, observability, pagination, and migration dry-run requirements. |
| CEO Review | `plan-ceo-review` | Clear after amendments | Confirmed planned-series plus pilot-first approach; rejected minimal button-only fix and render-all-episodes scope. |
| OpenClaw CEO Review | `gstack-openclaw-ceo-review` | Clear after amendments | Challenged trust, ledger typing, UI overload, and migration safety. |
| Autoplan Review | `autoplan` | Approved with amendments applied | Ran CEO, design, engineering, and DX phases in automated single-reviewer mode with decision audit trail and test plan artifact. |

Review artifacts:

- `docs/superpowers/reports/2026-06-08-series-continuity-ai-artifact-transparency-self-review.md`
- `docs/superpowers/reports/2026-06-08-series-continuity-ai-artifact-transparency-plan-ceo-review.md`
- `docs/superpowers/reports/2026-06-08-series-continuity-ai-artifact-transparency-openclaw-ceo-review.md`
- `docs/superpowers/reports/2026-06-08-series-continuity-ai-artifact-transparency-autoplan-review.md`
- `docs/superpowers/reports/2026-06-08-series-continuity-ai-artifact-transparency-test-plan.md`
