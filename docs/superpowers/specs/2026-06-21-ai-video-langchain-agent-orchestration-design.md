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

1. All AI video text generation, structured planning, storyboard generation, and expert review calls go through a LangChain runtime.
2. Existing image/video provider services remain the production execution layer and are exposed to agents as tools where needed.
3. The existing production state machine, cost reservation, asset persistence, audit events, and route response shapes stay intact.

This chooses the smallest design that satisfies "LLM + tool + multi-agent orchestration" without turning provider task execution into an opaque agent loop.

## Alternatives Considered

### A. Recommended: LangChain LLM and tools, keep provider execution services

Replace direct LLM calls with LangChain agents and tool calls. Provider renderers, queues, cost accounting, and persistence remain deterministic services.

Tradeoff: Agents orchestrate decisions, not every low-level provider operation. This keeps production behavior testable.

### B. Full provider-in-agent loop

Wrap image generation, video generation, provider submit/query, persistence, and approval actions as tools and let the agent decide the full sequence.

Tradeoff: More "agentic", but harder to audit, more expensive to test, and risks bypassing existing production gates.

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
- Request existing image/video production actions through current service boundaries when a workflow needs provider work.
- Record agency invocation, audit event, token usage, and model snapshot through existing agency persistence.

Provider submit/query functions remain service-owned. Tools call them; agents do not own provider lifecycle state.

## Multi-Agent Flow

Keep the existing stage DAG as the first orchestration contract:

- `story_planning`: narrative and Douyin strategy reviewers, story generator lead.
- `style_lock`: prompt and editing reviewers, visual storyteller lead, style QA.
- `storyboard`: visual, editing, strategy reviewers, narrative lead, storyboard QA.
- `image_stage`, `image_review`, `video_stage`, `video_review`, `compose_preflight`, `compose`: existing agency stages.

Each expert becomes a LangChain agent with a stage-specific system prompt and a restricted tool set. The orchestrator runs reviewers first, passes reviewer outputs to the lead, then runs QA where configured. Existing idempotency keys and persistence still decide whether an invocation should resume or execute.

## Replacement Map

- `AgencySkillRuntime.invoke()` becomes a LangChain agent invocation path.
- `story_generator_expert.generate_story_plan_with_expert()` uses a story-planning agent with structured output.
- `ScriptGenerationPipeline.default_script_model_client()` uses a script-stage agent or shared LangChain structured-output runner.
- `director_router.generate_auto_storyboard()` uses a storyboard agent.
- `style_lock.auto_generate_series_assets()` and `ensure_series_assets()` use asset-planning tools and structured-output agents instead of `ai_generator.generate_custom()`.

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
- Agency runtime tests proving reviewer, lead, and QA order still works with fake LangChain agents.
- Story planning, style lock, storyboard, and script pipeline tests proving outputs still populate existing DB fields and AI text artifacts.
- Inventory test proving AI video modules no longer call `ai_generator.generate_custom()` or direct `httpx` chat completion clients.
- Existing focused tests for series planning, script pipeline, director planning, agency orchestration, and production start flow still pass.

## Out Of Scope

- No frontend redesign.
- No rewrite of image/video provider clients.
- No migration of unrelated content, account, or device AI features.
- No LangSmith dependency requirement; tracing can be added later if needed.

## Spec Self-Review

- All requirements are explicit.
- The design satisfies the original scope by replacing AI video LLM application calls, not just agency review.
- Provider execution is deliberately kept outside the agent loop to preserve state-machine and cost-accounting behavior.
- The implementation can be split into testable slices without changing route contracts.
