# Bailian High-Quality Video Pipeline Design

## Context

The target state is a full dy_auto -> Pixelle-Video-dy pipeline that can generate high-quality video content end to end with strong expert involvement at every stage. The user approved using Bailian API keys for the model stack and explicitly requested script generation, expert review, and quality audit to use `qwen3.7-plus`.

Current local state:

- dy_auto runs as a FastAPI backend plus Vue frontend.
- Pixelle-Video-dy exists locally and exposes the stage API contract dy_auto calls:
  - `/api/stages/images/create`
  - `/api/stages/images/batch`
  - `/api/stages/videos/batch`
  - `/api/stages/compose`
  - `/api/stages/tasks/{stage_task_id}`
- dy_auto already has seeded model rows for Bailian/Qwen:
  - `Bailian Qwen Expert Review`
  - `Qwen Max`
  - `Qwen Image 2.0 Pro`
  - `Wan 2.7`
- Pixelle-Video-dy's current stage router explicitly supports `mock` and `seedance` for standalone image creation. Bailian `qwen-image` and `wan` are present in dy_auto model metadata, but they still need a real adapter smoke before being treated as fully proven media stages.

## Requirements

1. Configure secret material locally only. Do not commit API keys or print them in logs.
2. Use Bailian for all text-heavy quality stages:
   - script generation
   - expert review
   - quality audit
3. Prefer `qwen3.7-plus` for those stages. Before relying on it, verify the provided key and selected DashScope region can actually list or call that model.
4. Configure image and video model rows with the provided Bailian keys so they are ready for controlled smoke tests:
   - image: `qwen-image-2.0-pro`
   - video: `wan2.7-i2v`
5. Keep Pixelle bridge authentication separate from Bailian provider authentication.
6. Enable the paid-provider safety gate only when the runtime is deliberately single-worker:
   - `DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT=1`
7. Run real paid smoke tests only in a bounded way:
   - first LLM smoke
   - then Pixelle stage health
   - then a minimal media smoke
   - then a short video-flow smoke
8. Expert involvement must be visible in the production flow, not hidden as a background best-effort call.

## Approach

### Recommended Path

Use Bailian immediately for LLM, expert review, and audit stages, then validate media stages with paid smoke before making them the default execution path.

This avoids a false-green setup where the UI shows Bailian image/video models but Pixelle cannot yet execute the underlying DashScope media protocol. It also moves the highest-impact quality controls first: scripts, expert reviews, and audits.

### Alternatives Considered

1. Make Bailian image/video the default immediately.
   - Upside: fast path to the requested end state.
   - Downside: current Pixelle stage code does not clearly implement `qwen-image` standalone image creation. This can turn every real media task into a provider failure.

2. Keep all media on `seedance` and use Bailian only for LLM.
   - Upside: matches Pixelle's proven explicit stage branches.
   - Downside: does not satisfy the user's preference to use Bailian across phases where possible.

3. Implement/verify DashScope media adapters first, then switch defaults.
   - Upside: cleanest final architecture.
   - Downside: larger implementation task. It is appropriate after the configuration and smoke baseline is captured.

## Configuration Design

### Local Environment

Create ignored local environment files as needed:

- `server/.env`
- `D:/codex/Pixelle-Video-dy/.env` if Pixelle startup uses env loading, or process-level env for launch scripts.

Required local env values:

- `AI_PROVIDER=bailian` or equivalent OpenAI-compatible handling.
- `AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `AI_MODEL=qwen3.7-plus`
- `AI_API_KEY` set to the selected Bailian provider key as a local secret
- `DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT=1`
- `PIXELLE_VIDEO_URL=http://localhost:8500`
- `PIXELLE_API_KEY` set to a local dy_auto-to-Pixelle bridge secret, not a Bailian provider key
- `PIXELLE_CONFIG_PATH=D:/codex/Pixelle-Video-dy/config.yaml`

If `qwen3.7-plus` is not available for the provided key/region, the implementation must record the evidence and use the best available model from the key's actual model list. The fallback order is:

1. `qwen3.7-plus`
2. `qwen3.7-max`
3. `qwen3.6-plus`
4. `qwen-plus-latest`

### dy_auto Database

Update existing `ai_models` rows instead of creating duplicates.

For LLM quality stages:

- `Bailian Qwen Expert Review`
  - provider: `bailian`
  - base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - model: preferred verified model, nominally `qwen3.7-plus`
  - encrypted API key set
  - config: low temperature, high max tokens, expert-review scene key

- `Qwen Max` should be repurposed or renamed only if necessary. Prefer creating no duplicate row unless the unique `(model_type, provider, model_name)` constraint requires a separate explicit script-generation model.

For media stages:

- `Qwen Image 2.0 Pro`
  - encrypted API key set
  - keep `qwen-image-2.0-pro`
  - keep scene keys for image generation/editing

- `Wan 2.7`
  - encrypted API key set
  - keep `wan2.7-i2v`
  - keep `video_rendering`

For composition:

- Keep final composition on Pixelle local composition unless a verified Bailian composition provider exists. Composition is a local media assembly stage, not necessarily a generative model call.

### Pixelle Config

Write the LLM section and `ai_models.scenes` in `D:/codex/Pixelle-Video-dy/config.yaml` through dy_auto's Pixelle config bridge or a direct local config update.

Do not put the dy_auto bridge key into provider model configs. Do not put Bailian provider keys into Pixelle API middleware keys.

## Data Flow

1. User creates or starts a video production run in dy_auto.
2. dy_auto resolves the script/expert/audit LLM config to Bailian.
3. dy_auto records expert decisions and quality gates as production audit events or existing agency invocation records.
4. dy_auto submits media stage tasks to Pixelle using `PIXELLE_API_KEY` for service authentication.
5. Pixelle executes or dispatches media generation using the stage `model_config` provider credentials.
6. dy_auto syncs Pixelle stage task status, persists assets, then runs AI/human gates before advancing.
7. Final composition stays local/Pixelle until another paid composition provider is verified.

## Error Handling

- Missing or invalid Bailian key blocks the relevant stage with a repair action.
- Unsupported `qwen3.7-plus` for the selected region blocks the LLM switch until a supported fallback is selected.
- Pixelle 401/503 means bridge API key mismatch or missing Pixelle API key.
- Provider 429/quota errors must remain retryable and visible, not silently downgraded.
- Media adapter mismatch must be reported as "adapter unsupported" rather than "content failed".

## Verification Plan

1. Secret hygiene:
   - `git status --short`
   - confirm `.env` and SQLite runtime DB remain ignored
   - no raw key in tracked files

2. LLM availability:
   - call DashScope OpenAI-compatible `/models` or a minimal chat completion with the preferred model
   - verify selected model ID from actual response behavior

3. dy_auto config:
   - list model rows with `has_key=true` without printing keys
   - `/api/system/health` should show worker runtime OK after restart

4. Pixelle bridge:
   - start Pixelle API with the bridge key
   - dy_auto `/api/pixelle/test-connection` returns OK
   - a mock Pixelle stage task still completes

5. Paid media smoke:
   - start with the smallest paid media request supported by the verified adapter
   - capture provider task ID, status, asset URL, and cost settlement evidence
   - stop if adapter mismatch or quota error appears

6. Short end-to-end smoke:
   - create a short video-flow run
   - verify script generation, expert review, image/video stage, review gate, and final composition each leave evidence
   - verify final video asset is persisted and reviewable

## Open Risks

- `qwen3.7-plus` may be region-specific. Official docs show it in international pricing, while China-region compatibility docs currently emphasize `qwen3.6-plus` and `qwen3.7-max`.
- Pixelle-Video-dy's explicit stage adapter support for `qwen-image` and `wan` is not yet proven by code inspection. A short paid smoke is required before making those models the default media path.
- Real paid smoke can consume quota. It must remain bounded and stop on first provider/adapter failure.

## Acceptance Criteria

The goal is complete only when current evidence proves:

1. Bailian keys are configured locally and not committed.
2. Script generation, expert review, and quality audit resolve to the verified `qwen3.7-plus` target or a documented supported fallback.
3. Pixelle bridge connectivity works with a separate local bridge key.
4. Paid-provider safety gate is explicitly enabled for one worker.
5. At least one real paid media smoke succeeds or the precise adapter gap is identified and fixed.
6. A short end-to-end video production smoke produces a final persisted video asset.
7. Expert review/quality audit evidence is visible in the run history or audit events.
