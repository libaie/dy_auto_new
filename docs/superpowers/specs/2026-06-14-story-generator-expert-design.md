<!-- /autoplan restore point: C:\Users\szm\.gstack\projects\dy_auto_new\codex-bailian-high-quality-video-pipeline-autoplan-restore-20260614-031811.md -->
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
- build a strict JSON prompt and JSON Schema for `series_story_plan`, `season_arc`, and `episode_outlines`
- call an OpenAI-compatible chat completion client using the resolved runtime config
- send `response_format: {"type": "json_schema", ... "strict": true}` when the selected runtime config declares schema-output support; otherwise use the strict prompt plus robust parsing path
- parse JSON using the same robust extraction approach as existing planning code
- finalize the invocation with a safe generation summary, generated artifact counts, evidence, token usage, and a redacted model snapshot
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

Production start:

- keep the existing `production_run_service.py` preflight call to `generate_series_story_plan(db, series_id)`
- that direct preflight call must use the same `story_generator` runtime path as the worker so production cannot silently fall back to the old generic LLM path
- do not enqueue a second job from production preflight; production start needs the artifacts synchronously before script/storyboard expansion can consume them

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
- when finalizing `AgencyExpertInvocation`, keep `output_summary` free of `creative_patches`, `required_changes`, or failure-like summary text unless generation actually failed, so existing repair-task classifiers do not create false manual gates for successful generation

## Frontend Changes

Series detail should treat story planning like style lock:

- disable the button when status is `planning`, `queued`, or `running`
- show "故事规划中..." from persisted state, not only local request state
- after clicking, poll/reload every few seconds while persisted story-planning status is active, then stop polling once status is `completed`, `fallback`, or `failed`
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
- successful story expert invocation does not create repair tasks or creative patches
- `generate_series_story_plan()` preserves human-approved outlines
- fallback still creates artifacts with `expert_id: "story_generator"`
- `POST /api/series/{id}/story-plan` enqueues a story-planning job
- duplicate story-planning enqueue returns 409
- story-planning worker processes a queued job and completes the plan
- background worker calls `_run_story_plan_worker_step`
- production start consumes the same expert-generated story artifacts through the existing `generate_series_story_plan()` preflight path

Frontend tests:

- API client accepts queued story-plan response
- series detail disables button while persisted story planning status is active
- series detail polls while story planning is active and stops when terminal
- series detail labels expert-generated artifacts as "故事生成专家"
- agency labels include `story_generator` and `story_planning`

## Autoplan Review Notes

Autoplan checked this specification against the current code paths in `series_planning_service.py`, `series.py`, `main.py`, `agency_orchestrator.py`, `agency_repair_classifier.py`, and `SeriesDetailPage.vue`.

Key auto-decisions:

- Keep the durable job/worker design because it is the only option that matches style lock's user-visible operating model.
- Add schema-output support when the selected provider supports it, because model-structured JSON reduces missing-key failures compared with prompt-only JSON.
- Keep production-start preflight synchronous but force it through the same `story_generator` runtime path, because production needs artifacts before script generation.
- Store safe invocation summaries instead of raw full story payloads in `AgencyExpertInvocation.output_summary_json`, because existing repair and creative-patch code interprets specific keys as review actions.
- Add active-status frontend polling, because a queued job without reload/polling would make the button appear stuck or completed too early.

## Autoplan Review Output

### Phase 0 Intake

Plan summary: upgrade series story planning from a synchronous generic LLM prompt into a durable `story_generator` expert stage that mirrors style lock.

Scope detection:

- UI scope: yes. `SeriesDetailPage.vue` has user-facing generate button, status text, source labels, and reload behavior.
- DX scope: limited internal DX. The plan adds backend endpoints, worker steps, runtime config behavior, and test commands that future maintainers need to verify.
- Existing leverage: style lock already has the queue, worker, persisted status, agency trace, and frontend status pattern this feature should copy.
- Dual voice status: degraded. The local Codex CLI exists but failed with `Access is denied`; no callable Agent tool was available in this desktop turn. This review was completed in primary-review mode and marks outside voices unavailable.

### CEO Review

Premises checked:

| Premise | Verdict | Reason |
|---|---|---|
| The missing expert is a product defect, not just copy | Accepted | Current code uses prompt text only; it creates no expert source, invocation, worker, or status truth. |
| Story planning should match style lock's operating model | Accepted | The user explicitly approved "完整同风格锁定模式"; existing style lock has the right durable pattern. |
| Story planning must not generate all second-level storyboards | Accepted | The user needs precise storyboard seconds later, but whole-season planning should produce episode cards and continuity, not every shot. |
| Production start may continue calling story planning directly | Accepted with constraint | It can stay synchronous only if it calls the same `story_generator` runtime path and records the same trace. |

Strategic findings:

| Area | Finding | Decision |
|---|---|---|
| Product trust | Users need to see that planning is actually queued/running/completed, not an empty or silent sync call. | Keep persisted `story_planning` status. |
| Scope control | Adding optional reviewer rounds inside the first implementation would delay the critical fix. | First pass calls the lead generator only; reviewer topology exists for later review. |
| Asset continuity | The expert must use locked character/scene IDs or later storyboard/image steps drift. | Put locked IDs in the generation contract and prompt. |
| Six-month regret | If production start uses a different old path, teams will debug two story planners. | Force one shared runtime path. |

Dream state delta:

- Current: generic synchronous prompt writes artifacts or fallback with weak provenance.
- After this plan: `story_generator` produces traceable story artifacts, the UI shows durable progress, production start consumes the same output path, and failures leave explicit fallback traces.
- Not pursued now: automatic full-season second-by-second storyboard generation.

CEO completion summary:

| Section | Result |
|---|---|
| Architecture | Existing style lock pattern reused, no new queue abstraction. |
| Error/rescue | Model, JSON, manifest, and worker failures named below. |
| Security | No new user data boundary; redact model config snapshots. |
| Data flow | Worker, direct production preflight, and frontend polling covered. |
| Tests | Critical queue, invocation, fallback, and UI states mapped. |
| Quality score | 8.5/10 after adding production preflight, repair-safe summaries, and polling. |

CEO consensus: primary reviewer confirmed 6/6 critical strategy points; external voices unavailable.

### Design Review

Design classification: internal app UI. Reuse the existing series detail and style-lock status patterns. No new visual system is needed.

| Dimension | Before | After | Review result |
|---|---:|---:|---|
| Information architecture | 8 | 9 | Story planning remains on series detail; no new screen. |
| Interaction states | 6 | 9 | Active persisted statuses and terminal states are now specified. |
| User journey | 7 | 8 | Click, queued, running, completed/fallback/failed, and refresh behavior are specified. |
| AI slop risk | 7 | 8 | Source label changes from generic "AI 故事规划" to "故事生成专家". |
| Design system alignment | 8 | 8 | Reuse existing button/status area and style lock conventions. |
| Responsive/accessibility | 6 | 8 | Disable state and status copy are specified; implementation should preserve existing test selectors. |
| Unresolved design decisions | 6 | 9 | Polling lifecycle and failure display are explicit. |

Design litmus scorecard:

| Check | Status |
|---|---|
| User can tell work is still active after refresh | Pass after polling/status addition |
| Button state comes from backend truth, not local spinner only | Pass |
| Empty/fallback/failed states are named | Pass |
| Visual redesign avoided | Pass |

Design consensus: 7/7 dimensions reviewed; external voices skipped as unavailable.

### Engineering Review

Architecture flow:

```text
SeriesDetailPage
  | POST /api/series/{id}/story-plan
  v
series router
  | reject active ProductionJob
  | enqueue stage=story_planning
  | write story_bible_json.story_planning.status
  v
ProductionJob queue
  | background worker / worker-step
  v
generate_series_story_plan()
  | idempotency + human-edit preservation
  v
generate_story_plan_with_expert()
  | story_generator markdown
  | script_generation runtime config
  | strict JSON/schema response when supported
  | AgencyExpertInvocation
  v
AITextArtifact rows + model_trace_json
  | frontend reload/poll
  v
SeriesDetailPage status + source labels
```

State machine:

```text
idle
  -> queued
  -> running
  -> completed
  -> fallback
  -> failed

queued/running + second POST -> 409 STORY_PLANNING_IN_PROGRESS
failed/fallback/completed + new POST -> new job allowed, subject to idempotency and force rules
```

Test coverage diagram:

```text
POST story-plan
  -> enqueue job [integration]
  -> duplicate 409 [integration]
  -> persisted status [integration + component]

worker-step
  -> claim stage=story_planning [unit/integration]
  -> complete artifacts [integration]
  -> exception retry/fail [unit]

story generator runtime
  -> invocation created/finalized [unit]
  -> schema JSON request when supported [unit]
  -> malformed JSON fallback [unit]
  -> repair-safe summary [unit]
  -> human outline preserved [unit]

production start
  -> direct preflight calls same runtime [contract]

frontend
  -> active status disables button [component]
  -> polling starts/stops correctly [component]
  -> source label says 故事生成专家 [component]
```

Error & rescue registry:

| Failure | Trigger | Rescue | User-visible result | Test |
|---|---|---|---|---|
| `STORY_PLANNING_IN_PROGRESS` | Active queued/running job exists | Return 409 without enqueue | Button stays active-state after reload | API duplicate test |
| `MODEL_CONFIG_MISSING` | `script_generation` config missing | Deterministic fallback artifacts | "系统回退规划" | planning fallback test |
| `AGENCY_MANIFEST_INVALID` | Missing/hash-mismatched expert markdown | Fallback trace with error type | Fallback status | manifest/fallback test |
| `JSON_PARSE_ERROR` | Model returns malformed JSON | Robust extraction then fallback | Fallback status | malformed-output test |
| `WORKER_EXCEPTION` | Job execution raises unexpectedly | Existing queue helper marks retry/fail | Failed planning status | worker failure test |
| `REPAIR_FALSE_POSITIVE` | Output summary includes repair keywords | Store safe generation summary only | No manual repair gate | invocation side-effect test |

Failure modes registry:

| Codepath | Realistic failure | Criticality | Plan response |
|---|---|---|---|
| Router enqueue | Stale story bible says idle while job exists | High | Query active `ProductionJob` first. |
| Worker claim | Lease expires or concurrent worker claims | Medium | Reuse existing `claim_next_job` lease pattern. |
| Story runtime | Provider lacks schema response support | Medium | Feature-detect and use strict prompt/parser fallback. |
| Artifact persistence | Human-approved outline overwritten | High | Preserve approved human artifacts unless forced. |
| Production preflight | Old generic LLM path still runs | High | `generate_series_story_plan()` owns the shared expert path. |
| Frontend polling | Poll loop never stops | Medium | Stop on `completed`, `fallback`, or `failed`. |

Performance and observability:

- Queueing avoids request timeouts for manual generation.
- Production-start synchronous preflight can still be slow; this is intentional because downstream scripts need story artifacts before continuing.
- Traces should include invocation ID, scene key, expert ID, source metadata, token usage when present, and capped raw output preview.

Engineering completion summary:

| Section | Result |
|---|---|
| Scope challenge | Accepted as-is; durable mode is required by user approval. |
| Architecture | Diagram written; style lock pattern reused. |
| Test review | Coverage diagram written; test artifact saved at `C:\Users\szm\.gstack\projects\dy_auto_new\story-generator-expert-test-plan-2026-06-14.md`. |
| NOT in scope | Written below. |
| Existing code | Written below. |
| Failure modes | 6 mapped, 0 unresolved critical gaps after spec updates. |

Engineering consensus: 6/6 key implementation risks covered; external voices unavailable.

### DX Review

Developer persona: backend/frontend maintainer extending series production flows.

Developer journey:

```text
read spec
  -> locate style-lock analog
  -> add story_generator manifest/team/stage
  -> implement runtime + queue worker
  -> add frontend status/polling
  -> run backend + frontend targeted tests
```

DX scorecard:

| Dimension | Before | After | Notes |
|---|---:|---:|---|
| Getting started | 6 | 8 | Spec names analog files and test commands. |
| API design | 7 | 8 | Response shape and duplicate error are explicit. |
| Error/debugging | 6 | 9 | Error types and traces are named. |
| Documentation | 7 | 8 | Plan and test artifact now exist. |
| Upgrade/migration | 7 | 8 | Existing artifacts remain valid. |
| Dev environment | 7 | 7 | Uses current pytest/vitest setup. |
| Ecosystem consistency | 8 | 9 | Matches style lock and model-center scenes. |
| Measurement | 5 | 7 | Tests cover correctness; no runtime metric dashboard in scope. |
| TTHW | 20 min | 10 min | Target is time for a maintainer to run focused checks locally. |

DX implementation checklist:

- Error responses include stable codes for active jobs.
- Test commands are copyable from the test artifact.
- Worker step can be invoked directly in tests.
- Trace metadata makes provider/model/source debugging possible.

### Cross-Phase Themes

| Theme | Phases | Signal |
|---|---|---|
| Durable truth beats transient UI state | CEO, Design, Eng | The core user complaint is empty/missing progress; status must live in persisted data. |
| One generation path | CEO, Eng, DX | Worker and production preflight must share `generate_series_story_plan()` and `story_generator` runtime. |
| Provenance matters | CEO, Eng | Expert source, invocation, and artifact trace are required for trust and debugging. |
| Scope must not drift into full storyboard generation | CEO, Eng | Second-by-second storyboard precision belongs to storyboard/script phases, not whole-season planning. |

### NOT in Scope

- Generating second-by-second storyboards for every episode during story planning.
- Running full narrative/douyin reviewer passes before first story-generator implementation.
- Creating a new model-center scene unless `script_generation` cannot support the contract.
- Reworking the production queue abstraction beyond adding the new stage.
- Redesigning the series detail page visually.

### What Already Exists

- Style lock durable job pattern in `server/app/routers/series.py` and background loop in `server/app/main.py`.
- `ProductionJob` queue claim/complete/failure helpers.
- `AITextArtifact` persistence and approval behavior.
- Agency manifest/source metadata validation.
- Agency invocation persistence plus repair and creative-patch side effects.
- Existing series detail generate button, status slot, and source label helpers.

### Autoplan Completion Summary

| Phase | Status |
|---|---|
| CEO | Complete in primary-review mode; 4 premises checked and accepted. |
| Design | Complete; 7 dimensions scored, no unresolved design choice. |
| Eng | Complete; architecture, state, test, error, and failure diagrams written. |
| DX | Complete for internal maintainer DX; public developer docs not applicable. |
| Test artifact | Written to gstack project directory. |
| User challenges | 0 |
| Taste decisions | 0 |
| Auto-decisions | 7 |

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | Use full durable story-planning job/worker mode | Auto-decided | Completeness | The user explicitly asked for the style-lock mode, and the current sync endpoint is the core defect. | Prompt-only expert rename |
| 2 | Eng | Use `story_generator` as a generation runtime, not agency review schema | Auto-decided | Architecture fit | Existing agency review schema expects decisions/findings; generation needs story JSON. | Force story content through review output fields |
| 3 | Eng | Add schema-output request support when runtime config allows it | Auto-decided | Reliability | Structured JSON output is more reliable than prompt-only JSON for required keys. | Rely only on markdown-free prompt instructions |
| 4 | Eng | Keep production preflight synchronous but route it through the same expert runtime | Auto-decided | User outcome | Episode production must not start without story artifacts and must not use a different model path. | Enqueue production preflight and wait out-of-band |
| 5 | Eng | Keep invocation output summaries repair-safe | Auto-decided | Safety | Existing repair classifiers inspect output summaries and could create false gates from generation text. | Store full generated story payload as invocation summary |
| 6 | Design | Poll active story-planning status on the series detail page | Auto-decided | UX truthfulness | Queued background work needs visible persisted progress, matching style lock behavior. | Use only transient local button state |
| 7 | CEO | Defer full reviewer-pass orchestration for the first implementation | Auto-decided | Scope control | The user's immediate defect is missing generation/expert/status; optional reviewer rounds can land after the lead generator path works. | Run narrative and Douyin review roles before first ship |

## Rollout Notes

This change upgrades story planning from a synchronous prompt call into a durable creative stage. Existing approved artifacts remain valid. Series without story planning status should display as not yet planned. Existing one-sentence flows that write story artifacts can keep their direct deterministic artifacts; their traces should continue to identify `source: "one_sentence"` unless they intentionally opt into the new expert worker later.
