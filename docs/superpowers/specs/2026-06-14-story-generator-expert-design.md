# Story Generator Expert Design

## Goal

Add and actually call an independent `story_generator` expert for series story planning, using the same durable operating model as style lock: queued job, background worker, expert source metadata, model trace, visible status, and preserved human edits.

## Current Behavior

Series story planning currently runs synchronously through `POST /api/series/{series_id}/story-plan`. The backend calls `generate_series_story_plan()` in `server/app/services/series_planning_service.py`, which directly calls `ai_generator.generate_custom()` with a prompt-level role: "short-drama whole-season story planning assistant".

This is not a real expert invocation:

- no `story_generator` expert exists in the agency manifest
- no durable planning job exists
- no worker consumes planning jobs
- no `AgencyExpertInvocation` or expert source metadata is created for generation
- no frontend state mirrors style lock's `locking` status model

## Requirements

- Add `story_generator` as a first-class agency expert.
- Add a `story_planning` stage separate from `storyboard`.
- Invoke `story_generator` when the user clicks "generate whole-season story plan".
- Use the model-center `script_generation` runtime scene for story generation.
- Queue story planning through `ProductionJob`, matching style lock's durable pattern.
- Add a background worker step that consumes story-planning jobs.
- Persist generated `series_story_plan`, `season_arc`, `continuity_ledger`, and `episode_outline` artifacts in `AITextArtifact`.
- Preserve human-approved episode outlines unless generation is forced.
- Keep deterministic fallback behavior when the model config, model call, or JSON parsing fails.
- Expose planning status in the series detail response so the frontend can display queued/running/completed/failed state.
- Show the story expert source in artifact traces and agency console labels.

## Non-Goals

- Do not generate second-by-second storyboards for all episodes during story planning.
- Do not replace the existing storyboard review stage.
- Do not create a new model-center scene unless existing `script_generation` cannot support the flow.
- Do not overwrite human-approved outlines in normal runs.
- Do not refactor unrelated production job or agency console infrastructure.

## Expert Definition

Add `story_generator` to the agency team as a core creative expert.

Responsibilities:

- create whole-season story spine
- create episode cards with hooks, goals, conflicts, reversals, and cliffhangers
- maintain previous/next episode handoffs
- track foreshadowing introduced and resolved
- use locked character and scene IDs instead of inventing untracked assets

Recommended source file:

- `server/app/data/agency_agents_zh/creative/story-generator.md`

The manifest should include `story_generator` before `narrative_designer`, because story generation precedes storyboard and narrative review. The frontend labels should show it as "故事生成专家".

## Stage Model

Add `story_planning` to `STAGE_DAG`.

Recommended topology:

```json
{
  "story_planning": {
    "reviewers": ["narrative_designer", "douyin_strategist"],
    "lead": "story_generator",
    "qa": []
  }
}
```

The lead generates the final story plan. Reviewers are optional quality context for the agency console and future review. The first implementation should call only the `story_generator` generation runtime for the content body to keep scope tight.

## Generation Runtime

Create a small story-generation runtime service rather than forcing story generation through the existing agency review schema. The review runtime expects fields such as `decision`, `findings`, and `required_changes`; story generation needs a different JSON contract.

Proposed file:

- `server/app/services/story_generator_expert.py`

Public API:

```python
async def generate_story_plan_with_expert(
    db: Session,
    *,
    series: Series,
    episodes: list[Episode],
    character_ids: list[str],
    scene_ids: list[str],
    existing_artifacts: list[dict[str, Any]],
    runtime_config: dict[str, Any] | None = None,
) -> StoryGeneratorResult:
```

The service should:

- read `story_generator` markdown through `agency_manifest`
- resolve `script_generation` through `resolve_runtime_model_config`
- create or resume an `AgencyExpertInvocation` for `stage="story_planning"`, `role="lead"`, `expert_id="story_generator"`
- build a strict JSON prompt for `series_story_plan`, `season_arc`, and `episode_outlines`
- call an OpenAI-compatible chat completion client using the resolved runtime config
- parse JSON using the same robust extraction approach as existing planning code
- finalize the invocation with generated artifact summaries, evidence, token usage, and a redacted model snapshot
- return parsed content plus trace metadata

Trace metadata should include:

- `stage: "story_planning"`
- `stage_status: "expert"`
- `expert_id: "story_generator"`
- `scene_key: "script_generation"`
- `source_repo`, `source_commit`, `source_path`, `source_sha256`
- `invocation_id`
- redacted model config snapshot
- token usage when available
- raw output preview, capped

## Durable Job Flow

Mirror style lock's API and worker pattern.

Backend constants:

- `STORY_PLANNING_STAGE = "story_planning"`
- `STORY_PLANNING_ACTIVE_JOB_STATUSES`
- `STORY_PLANNING_JOB_LEASE_SECONDS`

API:

- `POST /api/series/{series_id}/story-plan`

New behavior:

- if a story-planning job is active, return `409 STORY_PLANNING_IN_PROGRESS`
- otherwise enqueue a `ProductionJob` with stage `story_planning`
- update a lightweight planning status on `Series.story_bible_json.story_planning`
- return `{ ok, status: "planning", job_id, story_planning }`

Worker:

- add `_run_story_plan_worker_step(db, lease_id, batch_size=1)`
- add `POST /api/series/story-plan/worker-step`
- add a background loop in `server/app/main.py` with the same interval, lease, batch-size, cancellation, and session-close shape as `_style_lock_worker`

Job completion:

- call `generate_series_story_plan(db, series_id)`
- mark job completed on success
- mark job failed/retryable on exceptions
- write `story_bible_json.story_planning.status` as `completed`, `failed`, or `fallback`

## Story Planning Service Changes

`generate_series_story_plan()` should stop calling `ai_generator.generate_custom()` directly. It should call `generate_story_plan_with_expert()` when generation is needed.

Fallback remains inside `generate_series_story_plan()`:

- model config missing -> fallback artifacts
- expert markdown invalid -> fallback artifacts
- model call failure -> fallback artifacts
- invalid JSON -> fallback artifacts

Fallback trace should still be explicit:

- `stage: "story_planning"`
- `stage_status: "fallback"`
- `expert_id: "story_generator"`
- `error_type`
- `error`

Existing idempotency rules remain:

- if all required approved AI/fallback artifacts exist, do not call the expert
- preserve approved human edits
- replace only system backfill or legacy backfill artifacts unless `force=True`

## Frontend Changes

Series detail should treat story planning like style lock:

- disable the button when status is `planning`, `queued`, or `running`
- show "故事规划中..." from persisted state, not only local request state
- after clicking, rely on polling/reload to show progress
- show source text as "故事生成专家" when trace has `expert_id: "story_generator"`
- keep "系统回退规划" for fallback

API client can keep `generateSeriesStoryPlan(id)`, but should tolerate the new queued response shape.

## Agency Console Visibility

Add labels for:

- stage `story_planning` -> "故事规划"
- expert `story_generator` -> "故事生成专家"

The console should display `story_planning` in the stage graph from the persisted `AgencyExpertInvocation` row. The AI text artifact workbench should also expose the expert source metadata from `model_trace_json`.

## Error Handling

- Missing model config does not fail the user-facing flow; it creates deterministic fallback artifacts and records the error.
- Active duplicate job returns 409 with code `STORY_PLANNING_IN_PROGRESS`.
- Worker exceptions mark the job retryable through existing production queue helpers.
- Manifest/hash mismatch falls back and records `AGENCY_MANIFEST_INVALID` or the concrete error type in trace.
- Frontend shows backend error message when enqueue fails.

## Testing

Backend tests:

- manifest includes `story_generator` and hashes match
- video agency team includes `story_generator`
- `STAGE_DAG` contains `story_planning`
- `generate_series_story_plan()` calls the story expert runtime and stores expert trace
- story expert generation creates and finalizes an `AgencyExpertInvocation`
- `generate_series_story_plan()` preserves human-approved outlines
- fallback still creates artifacts with `expert_id: "story_generator"`
- `POST /api/series/{id}/story-plan` enqueues a story-planning job
- duplicate story-planning enqueue returns 409
- story-planning worker processes a queued job and completes the plan
- background worker calls `_run_story_plan_worker_step`

Frontend tests:

- API client accepts queued story-plan response
- series detail disables button while persisted story planning status is active
- series detail labels expert-generated artifacts as "故事生成专家"
- agency labels include `story_generator` and `story_planning`

## Rollout Notes

This change upgrades story planning from a synchronous prompt call into a durable creative stage. Existing approved artifacts remain valid. Series without story planning status should display as not yet planned. Existing one-sentence flows that write story artifacts can keep their direct deterministic artifacts; their traces should continue to identify `source: "one_sentence"` unless they intentionally opt into the new expert worker later.
