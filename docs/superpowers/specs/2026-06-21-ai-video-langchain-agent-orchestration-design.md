# AI Video LangChain Agent Orchestration Design

## Context

The AI video stack currently mixes several LLM entry points:

- `server/app/domains/ai_video_series/style_lock.py` calls `ai_generator.generate_custom()` for character and scene extraction.
- `server/app/domains/ai_video_series/story_generator_expert.py` calls an OpenAI-compatible chat endpoint with `httpx`.
- `server/app/domains/director_planning/director_router.py` calls `ai_generator.generate_custom()` for auto-storyboard generation.
- `server/app/domains/script_pipeline/script_pipeline_service.py` uses the agency runtime's direct model client for script-generation stages.
- `server/app/domains/agency_operations/agency_runtime.py` directly calls OpenAI-compatible chat completions for expert review.
- `server/app/domains/agency_operations/agency_orchestrator.py` already provides a staged multi-expert DAG, but it is not a LangChain agent/tool orchestration layer.

`server/requirements.txt` does not currently include LangChain packages.

## Decision

Use LangChain for the AI video LLM application layer:

1. All AI video text generation, structured planning, storyboard generation, image generation, video generation, provider submit/query, and expert review calls go through a LangChain runtime.
2. Stage-specific agents may directly call provider tools such as `submit_image_generation`, `query_image_task`, `submit_video_generation`, and `query_video_task`.
3. Provider tools must reuse existing service boundaries for budget checks, idempotency keys, task persistence, provider clients, status queries, audit events, and error mapping.
4. Existing route response shapes, database tables, production status fields, and public error behavior stay intact.

This chooses the user-approved B-1 design: agents orchestrate the full AI video production loop, while write-capable tools keep paid provider execution auditable and stateful through existing project services.

## Alternatives Considered

### A. LangChain LLM and tools, keep provider execution services outside the agent loop

Replace direct LLM calls with LangChain agents and tool calls. Provider renderers, queues, cost accounting, and persistence remain deterministic services.

Tradeoff: Easier to test, but it does not satisfy the chosen requirement that agents orchestrate image/video provider submit/query.

### B. Selected: agent-orchestrated provider loop through guarded tools

Wrap image generation, video generation, provider submit/query, persistence, and approval actions as tools and let stage agents decide the production sequence.

Tradeoff: More surface area and tests, but each paid/write-capable tool still uses existing budget, idempotency, persistence, provider client, query, and audit services. Agents can orchestrate provider work without bypassing production gates.

### C. Agency-only LangChain replacement

Replace only `agency_runtime.py` and keep script/story/style/director generation on the current clients.

Tradeoff: Smaller diff, but it does not satisfy replacing the AI video AI application layer.

## Architecture

Add a focused LangChain runtime under `server/app/domains/ai_video_series/langchain_runtime/`:

- `ai_video_langchain_models`: creates chat model instances from existing `runtime_model_config` output.
- `ai_video_langchain_tools`: exposes deterministic project capabilities as typed LangChain tools.
- `ai_video_langchain_agents`: builds named agents for story planning, style lock, storyboard generation, script layers, and stage review.
- `ai_video_langchain_orchestrator`: runs multi-agent stage workflows and maps results back into existing payloads.

This stays inside the AI video series domain because the first replacement targets series planning, style lock, storyboards, script generation, and agency review for video production. It must not become a generic platform framework.

## Tools

Use tools for deterministic capabilities that the model should not fake:

- Read series, episode, character, scene, style-lock, and previous artifact context.
- Validate and parse JSON into existing Pydantic/domain schemas.
- Write AI text artifacts through `AITextArtifactService`.
- Create or update generated character and scene assets through existing domain services.
- Submit image generation through current provider and production service boundaries.
- Query image generation provider tasks and persist completed image assets.
- Submit video generation through current provider and production service boundaries.
- Query video generation provider tasks and persist completed video assets.
- Persist production job, segment, run, and artifact state transitions through existing DB models.
- Record agency invocation, audit event, token usage, and model snapshot through existing agency persistence.

Agents may choose when to call provider submit/query tools, but the tools own the irreversible side effects: budget reservation, idempotency, provider API call, task id persistence, status mapping, asset persistence, and audit event creation. No AI video agent may call provider clients or `ai_generator.generate_custom()` directly.

## Provider Tool Contract

Write-capable provider tools must be narrow and explicit:

- Inputs include `series_id`, `episode_id`, target ids, prompt payload, provider scene key, and an idempotency key or enough data to derive one.
- Outputs include local job/asset ids, provider task id when available, normalized status, cost metadata when available, and audit event ids when recorded.
- Repeated calls with the same idempotency key return the existing local job/task state instead of submitting duplicate paid work.
- Query tools update local status and asset URLs by calling existing provider query services.
- Tool errors map to existing `AgencyRuntimeError` or production error codes and are persisted as failed invocations/audit events.
- Tools never accept arbitrary raw provider URLs or API keys from the agent prompt.

## Multi-Agent Flow

Keep the existing stage DAG as the first orchestration contract:

- `story_planning`: narrative and Douyin strategy reviewers, story generator lead.
- `style_lock`: prompt and editing reviewers, visual storyteller lead, style QA.
- `storyboard`: visual, editing, strategy reviewers, narrative lead, storyboard QA.
- `image_stage`, `image_review`, `video_stage`, `video_review`, `compose_preflight`, `compose`: existing agency stages.

Each expert becomes a LangChain agent with a stage-specific system prompt and a restricted tool set. The orchestrator runs reviewers first, passes reviewer outputs to the lead, then runs QA where configured. Existing idempotency keys and persistence still decide whether an invocation should resume or execute.

Provider stages use the same staged pattern:

- `image_stage`: image agent reads context, submits image jobs, queries provider tasks, persists successful assets, and returns normalized stage output.
- `image_review`: review agents inspect generated assets and may request bounded regeneration through provider tools.
- `video_stage`: video agent submits segment/video jobs, queries provider tasks, persists clips, and returns normalized stage output.
- `video_review`: review agents inspect video assets and may request bounded regeneration through provider tools.
- `compose_preflight` and `compose`: agents inspect readiness and call only existing compose/preflight service tools.

## Replacement Map

- `AgencySkillRuntime.invoke()` becomes a LangChain agent invocation path.
- `story_generator_expert.generate_story_plan_with_expert()` uses a story-planning agent with structured output.
- `ScriptGenerationPipeline.default_script_model_client()` uses a script-stage agent or shared LangChain structured-output runner.
- `director_router.generate_auto_storyboard()` uses a storyboard agent.
- `style_lock.auto_generate_series_assets()` and `ensure_series_assets()` use asset-planning tools and structured-output agents instead of `ai_generator.generate_custom()`.
- Image production stages call LangChain provider tools instead of route-local provider submit/poll helpers.
- Video production stages call LangChain provider tools instead of route-local provider submit/poll helpers.
- Provider task query/poll behavior is centralized in LangChain provider tools that delegate to existing provider services.

`model_configuration.ai_generator` can remain for non-AI-video features until their own migration exists, but AI video modules must stop calling it directly.

## Error Handling

Keep current public error behavior:

- Model config missing maps to existing runtime config errors or `AgencyRuntimeError` codes.
- Model timeout keeps current timeout traces where routes already use them.
- Invalid JSON maps to existing invalid-output errors.
- Tool failures are captured as failed invocations and audit events, not silent fallbacks.
- Secrets in runtime config and prompts remain redacted before persistence.

## Testing

Minimum verification for implementation:

- Unit tests for model-config-to-LangChain mapping using fake model objects.
- Tool tests for each write-capable tool, using existing services and DB fixtures.
- Provider tool tests proving image/video submit/query tools call existing services, preserve idempotency, persist task ids/status, and avoid duplicate paid submits.
- Agency runtime tests proving reviewer, lead, and QA order still works with fake LangChain agents.
- Provider-stage orchestration tests proving fake agents can submit, query, persist, review, and regenerate bounded image/video work.
- Story planning, style lock, storyboard, and script pipeline tests proving outputs still populate existing DB fields and AI text artifacts.
- Inventory test proving AI video orchestration modules no longer call `ai_generator.generate_custom()`, direct `httpx` chat completion clients, or scattered provider submit/query helpers outside the approved LangChain provider tool modules and existing provider service modules.
- Existing focused tests for series planning, script pipeline, director planning, agency orchestration, and production start flow still pass.

## Out Of Scope

- No frontend redesign.
- No rewrite of image/video provider clients; LangChain tools delegate to them.
- No migration of unrelated content, account, or device AI features.
- No LangSmith dependency requirement; tracing can be added later if needed.

## Spec Self-Review

- All requirements are explicit.
- The design satisfies the selected B-1 scope by replacing AI video LLM calls and letting agents orchestrate image/video provider submit/query through guarded tools.
- Provider execution enters the agent loop only through tools that preserve budget checks, idempotency, state persistence, provider clients, status queries, and audit behavior.
- The implementation can be split into testable slices without changing route contracts.
