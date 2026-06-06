# Dramatic Script Pipeline Design

Date: 2026-06-06

Status: Approved design, awaiting spec review before implementation.

## Goal

Refactor dy_auto script generation from a single black-box text generation step into a Dramatic Structure Matrix pipeline. A one-sentence prompt or episode outline should become a structured short-drama script through three gated stages:

1. Dramatic beats.
2. Scene outlines.
3. Visual shots and model prompts.

The implementation must preserve high-impact short-drama constraints: a hook in the first three seconds, escalating conflict, reversal, climax, and cliffhanger. Scripts must not be stored as one text blob.

## Existing System Context

The current short-drama path lives mostly in `server/app/services/one_sentence_video_service.py`. It builds style lock data, deterministic storyboard frames, and then calls existing expert review gates through `AgencyOrchestrator`.

Reusable project pieces:

- `server/app/db_models.py`
  - `Episode.script_json` and `Episode.storyboard_json` already provide compatibility snapshots.
  - `PipelineRun.layers_json` already stores persistent pipeline state.
  - `AgencyExpertInvocation` already stores expert gate invocations and supports `pipeline_run_id`.
- `server/app/services/agency_orchestrator.py`
  - Provides staged expert calls, idempotency keys, manifest verification, and persisted expert invocation records.
- `server/app/services/runtime_model_config.py`
  - Resolves enabled model rows by scene key.
  - Existing model seed already includes `script_generation` and `llm_agency_expert_review` scene keys.
- `server/app/services/agency_runtime.py`
  - Supports OpenAI-compatible providers, including Bailian.
  - Validates expert output as strict JSON.

The new work should reuse these systems instead of creating another expert review platform.

## Chosen Approach

Use a strict-delivery package migration:

- Move `server/app/models.py` to `server/app/models/__init__.py`.
- Keep all current exports compatible so existing `from app.models import ...` imports continue to work.
- Add `server/app/models/script.py` for script-domain Pydantic V2 models and enums.
- Add SQLAlchemy persistence models in `server/app/db_models.py`.
- Add `server/app/services/script_pipeline.py` for the async pipeline controller.
- Add strict JSON Markdown templates under `server/app/prompts/templates/`.

This matches the requested `models/script.py` artifact while keeping old API imports stable.

## Data Model

### Pydantic Domain Models

`server/app/models/script.py` will define Pydantic V2 models:

- `DramaticBeatType`
  - `HOOK`
  - `CONFLICT_1`
  - `REVERSAL`
  - `CLIMAX`
  - `CLIFFHANGER`
- `PipelineStage`
  - `dramatic_beats`
  - `scene_outlines`
  - `visual_shots`
- `DramaticBeat`
  - `beat_type`
  - `emotional_value`
  - `plot_summary`
- `SceneOutline`
  - `scene_number`
  - `dramatic_beat_type`
  - `location`
  - `characters`
  - `conflict`
  - `emotional_turn`
  - `visual_mandate`
- `VisualShot`
  - `shot_number`
  - `scene_number`
  - `beat_type`
  - `narration`
  - `visual_prompt`
  - `video_prompt`
  - `duration`
- `EpisodeScript`
  - `series_id`
  - `episode_id`
  - `source_prompt`
  - `tags`
  - `target_duration_seconds`
  - `dramatic_beats`
  - `scene_outlines`
  - `visual_shots`
  - `agency_trace`

Validation rules:

- A script must include the five required beat types.
- `VisualShot.shot_number` must be positive.
- `VisualShot.duration` must be positive.
- `VisualShot.narration` must contain at least one emotional tone marker.
- Stage outputs must be JSON objects matching the expected schema.

### SQLAlchemy Persistence

`server/app/db_models.py` will add structured script tables:

- `EpisodeScript`
  - One row per generated episode script version.
  - Links to `series_id`, `episode_id`, and optional `pipeline_run_id`.
  - Stores metadata, tags, source prompt, status, and trace JSON.
- `ScriptDramaticBeat`
  - Child rows ordered by `order_index`.
  - Stores beat type, emotional value, and plot summary.
- `ScriptSceneOutline`
  - Child rows ordered by `scene_number`.
  - Links each scene to a dramatic beat type.
  - Stores conflict, emotional turn, visual mandate, location, and character list as structured fields.
- `ScriptVisualShot`
  - Child rows ordered by `shot_number`.
  - Stores narration, visual prompt, video prompt, duration, scene number, and beat type.

`Episode.script_json` and `Episode.storyboard_json` will be compatibility snapshots derived from these structured tables. They are not the source of truth for the new script module.

## Pipeline Controller

`server/app/services/script_pipeline.py` will implement:

- `ScriptGenerationError`
  - Carries `stage`, `pipeline_run_id`, `attempts`, `error_code`, and `human_intervention_required`.
- `DynamicPromptBuilder`
  - Loads Markdown templates.
  - Injects tag constraints and beat constraints.
  - Renders strict system and user prompt payloads.
- `ScriptGenerationPipeline`
  - Async orchestration of the three generation stages.
  - Calls the configured script-generation model.
  - Validates model JSON with Pydantic.
  - Runs expert gates after Stage 1 and Stage 2.
- `PipelineManager`
  - Creates or resumes `PipelineRun`.
  - Persists stage status in `PipelineRun.layers_json`.
  - Saves structured script rows and compatibility snapshots.

The pipeline must never call the model once to generate the whole script. Stage 2 can only run after Stage 1 output is validated and Gate 1 passes. Stage 3 can only run after Stage 2 output is validated and Gate 2 passes.

## Stage Flow

### Stage 1: Dramatic Beats

Input:

- Source prompt or episode outline.
- Tags such as `歪嘴战神`, `都市逆袭`, `主母黑化`.
- Target duration.
- Optional existing series and episode metadata.

Output:

- `DramaticBeatList` with the five required beat types.

Gate:

- Use existing `AgencyOrchestrator` with `llm_agency_expert_review` runtime config.
- The stage context includes the beat list, emotional curve, reversal claim, and tag constraints.
- Gate status `blocked` or `failed` stops the pipeline.

### Stage 2: Scene Outlines

Input:

- Approved Stage 1 beat list.
- Source prompt, tags, duration, and context.

Output:

- `SceneOutlineList`.

Gate:

- Use existing `AgencyOrchestrator` with visual-storyteller-oriented context.
- The stage context includes scene visuals, feasibility notes, character continuity, and beat coverage.
- Gate status `blocked` or `failed` stops the pipeline.

### Stage 3: Visual Shots

Input:

- Approved Stage 1 beat list.
- Approved Stage 2 scene outlines.
- Source prompt, tags, duration, and style constraints.

Output:

- `VisualShotList`.
- Derived `storyboard_json.frames` compatible with current video production services.

No expert gate is required after Stage 3 in this spec because the downstream image and video production pipeline already has image, video, and compose gates. Stage 3 still validates strict schema and prompt quality before persistence.

## Retry And Resume

`PipelineRun.layers_json` will hold a `script_generation` object:

```json
{
  "current_stage": "dramatic_beats",
  "human_intervention_required": false,
  "stages": {
    "dramatic_beats": {
      "status": "completed",
      "attempts": 1,
      "input_hash": "sha256-prefix",
      "output": {},
      "gate_trace": {},
      "error": null
    }
  }
}
```

Stage states:

- `pending`
- `running`
- `completed`
- `failed`
- `blocked`

Retry behavior:

- Each stage gets at most two automatic retries after the first failed attempt.
- A completed stage with the same input hash is reused during resume.
- A changed input hash invalidates that stage and downstream stages.
- Exhausted retries set `human_intervention_required` and raise `ScriptGenerationError`.

## Prompt Templates

Templates will live under `server/app/prompts/templates/`:

- `script_stage1_dramatic_beats.md`
- `script_stage2_scene_outlines.md`
- `script_stage3_visual_shots.md`

Each template has:

- A system section requiring strict JSON only.
- A user section with variables for source prompt, tags, previous stage outputs, duration, and constraints.
- A JSON schema section that describes the only valid response shape.

The model must not return Markdown fences, commentary, explanations, or analysis.

## Emotion Amplifier

`DynamicPromptBuilder` injects constraints before each model call.

Beat constraints:

- `HOOK`
  - The first three seconds must show a visible conflict such as a cup smash, kneeling, slap, public humiliation, or identity contrast.
  - Dialogue must be under 15 Chinese characters.
  - Tone must be extreme.
- `CLIMAX`
  - Must complete an identity reversal.
  - Antagonist must show shock or fear visually.
  - Protagonist camera angle should use low-angle upward framing.

Tag constraints:

- `歪嘴战神`
  - Suppressed protagonist status, visible contempt from others, then precise power reveal.
- `都市逆袭`
  - Modern hierarchy pressure, public stakes, money/status contrast, direct reversal.
- `主母黑化`
  - Domestic power order, betrayal, emotional cold turn, controlled retaliation.

Unknown tags are carried through as creative context without invented hard rules.

## Error Handling

Errors are explicit and persisted:

- Model config missing.
- Model timeout.
- Invalid JSON.
- Pydantic validation failure.
- Expert gate blocked.
- Expert gate failed.
- Persistence failure.

`ScriptGenerationError` is thrown only after state has been written to `PipelineRun.layers_json`, so a human can inspect and resume.

Secrets such as API keys must never be written into prompts, traces, snapshots, errors, or docs.

## Compatibility Snapshot

After Stage 3 succeeds:

- `Episode.script_json` receives a compact structured snapshot of beats, scenes, shots, tags, source prompt, and trace IDs.
- `Episode.storyboard_json` receives frames compatible with existing video generation code:
  - `frame_id`
  - `image_prompt`
  - `video_prompt`
  - `narration`
  - `duration`
  - `action`
  - `emotion`
  - `shot_type`

This allows later integration with `one_sentence_video_service.py` without replacing it in this implementation slice.

## Implementation Boundaries

In scope:

- Pydantic V2 script models.
- SQLAlchemy structured persistence models.
- Async pipeline core.
- Persistent resume and retry state.
- Expert gates through existing agency review infrastructure.
- Dynamic prompt builder and strict JSON templates.
- Unit tests for models, prompt building, retry/resume behavior, gate blocking, and snapshots.

Out of scope for this slice:

- Replacing the one-sentence video endpoint.
- Changing Pixelle composition behavior.
- Building new frontend screens.
- Persisting or committing any user-provided API key.

## Test Plan

Add focused tests:

- `server/tests/test_script_models.py`
  - Validates required beats, shot duration, shot number, and narration emotion markers.
- `server/tests/test_script_prompt_builder.py`
  - Confirms tag and beat constraints are injected.
  - Confirms templates demand strict JSON only.
- `server/tests/test_script_pipeline.py`
  - Confirms stages run sequentially.
  - Confirms Gate 1 blocks Stage 2.
  - Confirms Gate 2 blocks Stage 3.
  - Confirms retry limit is two automatic retries.
  - Confirms resume skips completed stages with the same input hash.
  - Confirms failed retries set `human_intervention_required`.
- A targeted import compatibility test to prove `from app.models import TaskType` still works after package migration.

Verification commands:

- `pytest server/tests/test_script_models.py`
- `pytest server/tests/test_script_prompt_builder.py`
- `pytest server/tests/test_script_pipeline.py`
- `pytest server/tests/test_models.py server/tests/test_accounts_api.py`

## Acceptance Criteria

The implementation is complete when:

- `server/app/models/script.py` exists and exposes the script Pydantic V2 models.
- `server/app/services/script_pipeline.py` exists and implements the async three-stage pipeline.
- `server/app/prompts/templates/` contains strict JSON Markdown templates for all three stages.
- Scripts are persisted in structured SQLAlchemy tables, not as one text blob.
- `PipelineRun.layers_json` can resume and retry stage execution.
- Stage 2 cannot run before Stage 1 validation and Gate 1 success.
- Stage 3 cannot run before Stage 2 validation and Gate 2 success.
- A stage failure after retry exhaustion raises `ScriptGenerationError` and marks human intervention required.
- Existing `app.models` imports remain compatible.
- New focused tests pass.

