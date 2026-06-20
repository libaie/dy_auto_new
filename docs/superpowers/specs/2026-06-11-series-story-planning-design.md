# Series Story Planning Design

Date: 2026-06-11

## Problem

Current series mode creates episode placeholders and system backfilled `episode_outline` artifacts, but it does not have a real series-level story generation step. Starting an episode can now generate a per-episode script and second-accurate storyboard, but the story input is still mostly the series title/logline plus deterministic placeholder context.

That means a multi-episode work does not yet receive a coherent season arc, per-episode dramatic handoffs, or a dedicated story expert before production starts.

## Answer

For series content, the system should generate the whole series story plan once, then expand only the selected episode into a full script/storyboard at production time.

This is the right split:

- Up front: generate `series_story_plan`, `season_arc`, and one rich approved `episode_outline` story card per episode.
- Per episode: use the selected episode card plus continuity artifacts as source context for the existing script pipeline.
- Per shot: keep second-accurate storyboard generation in the per-episode pipeline, because generating every shot for all episodes up front is expensive and hard to revise.

## Success Criteria

- A user can click one action on a series detail page and get non-empty story planning artifacts for every target episode.
- Existing system backfilled outlines are replaced by richer AI story cards unless a human-approved outline exists.
- Starting production for an episode injects the approved series story plan and episode outline into the script generation prompt.
- No new database migration is required for the first pass; use `AITextArtifact`.
- If no AI model is configured or the model call fails, the UI still gets structured fallback story cards with explicit fallback trace, not empty content.

## Proposed Expert Roles

The first implementation records these roles in prompts and `model_trace_json`; it does not need a new agency manifest entry yet.

- `series_showrunner`: owns theme, genre promise, season spine, and finale direction.
- `story_generator`: creates episode cards with hooks, conflicts, reversals, and cliffhangers.
- `continuity_editor`: checks handoffs, unresolved promises, character state changes, and contradictions.
- `douyin_hook_editor`: sharpens the first 3 seconds and next-episode cliffhanger for short-video consumption.

## Model Usage

- Series story planning: use the configured `script_generation` LLM scene through the existing AI config path.
- Script expansion: keep the existing `script_generation` runtime model in `ScriptGenerationPipeline`.
- Expert review gates: keep `llm_agency_expert_review`.
- Image generation: keep configured `image_generation`.
- Video rendering: keep configured `video_rendering`.
- Final composition: keep existing compose scene key used by video production.

Fallback behavior is part of the contract: when `script_generation` is unavailable, create deterministic but connected story cards and mark `model_trace_json.stage_status = "fallback"`.

## Artifact Contract

Series-level artifacts:

- `series_story_plan`: whole-series premise, genre promise, theme, protagonists, antagonistic force, season question, finale promise.
- `season_arc`: ordered episode beats and handoff map.
- `continuity_ledger`: existing artifact, retained and enriched by the planning flow.

Episode-level artifacts:

- `episode_outline`: upgraded from placeholder into a story card. Required fields:
  - `episode_number`
  - `title`
  - `hook`
  - `episode_goal`
  - `central_conflict`
  - `reversal`
  - `cliffhanger`
  - `previous_episode_handoff`
  - `next_episode_handoff`
  - `character_state_changes`
  - `foreshadowing_introduced`
  - `foreshadowing_resolved`
  - `character_ids`
  - `scene_ids`

Preservation rule: do not overwrite latest approved `episode_outline` when its `source_type` is `human_edit`, unless a future force/regenerate UI explicitly asks for it.

## Data Flow

```mermaid
flowchart LR
    A["Create or open series"] --> B["Ensure episode placeholders"]
    B --> C["Generate series story plan"]
    C --> D["Approve AITextArtifact records"]
    D --> E["User starts one episode"]
    E --> F["Inject series_story_plan + season_arc + episode_outline"]
    F --> G["ScriptGenerationPipeline"]
    G --> H["Second-accurate storyboard frames"]
    H --> I["Image/video production"]
```

## API

Add:

`POST /api/series/{series_id}/story-plan`

Response fields:

- `ok`
- `series_id`
- `target_episode_count`
- `created_episode_numbers`
- `replaced_outline_episode_numbers`
- `preserved_outline_episode_numbers`
- `artifacts`
- `model_trace`

The endpoint should call `ensure_episode_placeholders` first, then generate planning artifacts idempotently.

## UI

On `SeriesDetailPage.vue`:

- Add a "生成整季故事规划" action near existing style lock and text workbench actions.
- Show a compact status line: planned episode count, planning source (`ai` or `fallback`), and latest generated time when available.
- In each expanded episode, display the richer `episode_outline` story card above script/storyboard.

## Autoplan Review

Decision: selective expansion.

Keep scope small enough to ship now:

- Use `AITextArtifact`, not new tables.
- Use current `script_generation` model config, not a new model center scene.
- Use prompt-level expert roles, not a new agency runtime manifest.

Required expansion:

- Production prompt must consume the generated story plan, otherwise the feature only fills UI text and does not fix output quality.
- Fallback must be structured and visible, otherwise "empty multi-episode mode" can still happen when AI config is missing.

## Plan CEO Review

The highest leverage product change is not "generate all episode scripts at once"; it is "make series planning visible and binding." Users need confidence that a series has a story spine before they spend money on images/videos.

Non-goals:

- Do not generate full second-by-second storyboard for every episode up front.
- Do not add a complex approval workflow beyond the existing AI text artifact workbench.
- Do not introduce new database tables in this pass.

## OpenClaw CEO Review

Risk challenged: a "Generate all" button could hide a weak season and create expensive downstream work.

Chosen tradeoff: generate all episode story cards once, but generate scripts/videos one episode at a time. This gives continuity without forcing irreversible production cost.

## Design Review

Score: 8/10.

The UI should remain operational and dense. A simple action button plus artifact status is enough. Avoid a landing-style explainer or large new page. The text workbench remains the detailed review surface.

Required polish:

- Button states must distinguish "planning", "planned", and "fallback created".
- Episode card display should use compact labels and preformatted JSON/text, matching current episode expansion style.

## Engineering Review

Score: 8/10.

The architecture fits existing boundaries:

- `series_planning_service.py` already owns placeholder and continuity artifacts.
- `AITextArtifactService` already versions and approves text artifacts.
- `production_run_service.py` already assembles per-episode production context.

Main implementation risks:

- Artifact ordering tests must be updated if new series artifact types are consumed by runs.
- `episode_outline` overwrite must preserve human edits.
- AI JSON parsing must tolerate fenced JSON and malformed model output.
- Production prompts must remain compact enough for the configured model context.

## Verification

- Backend service tests for story plan generation, idempotency, fallback, and human-edit preservation.
- API tests for `POST /api/series/{series_id}/story-plan`.
- Production start tests proving consumed artifacts include story plan and script source prompt includes story card content.
- Frontend API/client and series detail tests for the new action and story card display.
