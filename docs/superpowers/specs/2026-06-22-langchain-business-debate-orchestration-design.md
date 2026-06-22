# LangChain Business Debate Orchestration Design

Status: auto-approved by user instruction.

## Goal

Refine the AI video multi-agent debate flow so each production stage is judged by the right business experts, not by one generic critic/defender pair.

The project already has LangChain-backed agency expert calls and provider tools. This design upgrades the existing `agency.debate.v1` audit into a stage-aware `agency.debate.v2` flow while preserving current routes, database tables, provider execution, repair jobs, and trace merging behavior.

## Current Behavior

- `AgencyOrchestrator` runs a fixed stage DAG: reviewers, lead, optional QA, then optional debate.
- `agency_debate_audit.py` runs two rounds of debate for most production stages.
- Debate currently always uses `visual_storyteller` as critic and `video_stage_quality_reviewer` as defender.
- `story_planning` is not debated.
- Debate blocks downstream production unless the second round reaches `consensus_pass`.
- `AgencySkillRuntime` already invokes experts through `LangChainAgentRunner` with restricted tools.
- Provider image/video/compose submit and query operations already have separate LangChain tools, and those tools preserve existing budget, idempotency, provider, persistence, and audit boundaries.

## Requirements

1. Add a stage-specific debate policy for every `STAGE_DAG` stage, including `story_planning`.
2. Keep debate inside the existing `AgencyOrchestrator` and `AgencySkillRuntime` path so every debate turn remains a persisted LangChain-backed expert invocation.
3. Keep provider submit/query tools out of debate turns. Debate agents may judge context and outputs, but paid provider writes remain in the provider-stage agent path.
4. Run two adversarial rounds, then a final arbiter turn.
5. Final stage blocking is decided by the arbiter scorecard and invocation status.
6. Persist a backward-compatible trace shape with a new `schema_version: agency.debate.v2`.
7. Continue recording `agency_debate_repair_intent` and existing auto-repair jobs when a debate blocks.
8. Preserve existing public route payloads and database schema.

## Selected Approach

Use a policy table in the agency operations domain:

- `critic`: the expert whose job is to find business-stage failure modes.
- `defender`: the expert whose job is to defend or repair the stage output.
- `arbiter`: the final quality expert whose scorecard decides pass/block.
- `focus`: short business checklist injected into debate context.

This keeps the implementation small and inspectable. The policy table can be unit tested against `STAGE_DAG`, and the debate runner only needs to replace hard-coded role constants with policy lookup plus one arbiter invocation.

## Stage Policy Matrix

| Stage | Critic | Defender | Arbiter | Focus |
| --- | --- | --- | --- | --- |
| `story_planning` | `narrative_designer` | `story_generator` | `douyin_strategist` | Season arc, episode differentiation, continuity ledger, locked character/scene usage |
| `style_lock` | `visual_storyteller` | `image_prompt_engineer` | `style_lock_quality_reviewer` | Character rules, scene rules, reference readiness, visual inheritance |
| `storyboard` | `visual_storyteller` | `narrative_designer` | `storyboard_quality_reviewer` | Executable frames, character/scene anchors, continuity, shot timing |
| `image_stage` | `visual_storyteller` | `image_prompt_engineer` | `image_stage_quality_reviewer` | Prompt completeness, reference images, provider constraints, style drift risk |
| `image_review` | `image_prompt_engineer` | `visual_storyteller` | `image_review_quality_reviewer` | Result identity, scene consistency, image usability for video |
| `video_stage` | `visual_storyteller` | `short_video_editing_coach` | `video_stage_quality_reviewer` | Segment duration, motion intent, first-frame inheritance, continuity |
| `video_review` | `video_optimization_specialist` | `short_video_editing_coach` | `video_review_quality_reviewer` | Identity drift, motion stability, shot intent, compose readiness |
| `compose_preflight` | `douyin_strategist` | `video_optimization_specialist` | `compose_quality_reviewer` | Episode completeness, pacing, platform fit, missing assets |
| `compose` | `douyin_strategist` | `short_video_editing_coach` | `compose_quality_reviewer` | Final delivery, rhythm, audio/subtitle readiness, publishing fit |

## Debate Flow

1. The existing stage reviewers, lead, and QA run first.
2. If `enable_debate=True` and a policy exists for the stage, debate starts.
3. Round 1 critic receives stage context, policy focus, and no opponent summary.
4. Round 1 defender receives the critic summary.
5. Round 2 critic receives the defender summary.
6. Round 2 defender receives the second critic summary.
7. Arbiter receives both second-round summaries and the policy focus.
8. If arbiter status is `failed`/`blocked`, missing scorecard, or scorecard verdict blocks, the stage becomes `blocked`.
9. Otherwise the debate status is `consensus_pass` and the stage remains `completed`.

The original critic/defender disagreement is still recorded, but the arbiter becomes the final business decision. This avoids blocking production merely because two valid experts use different wording while still making missing scorecards fail closed.

## Trace Contract

`trace["debate"]` keeps v1 fields and adds v2 fields:

```json
{
  "schema_version": "agency.debate.v2",
  "stage": "storyboard",
  "policy_id": "storyboard.v1",
  "status": "consensus_pass",
  "rounds": 2,
  "critic_expert_id": "visual_storyteller",
  "defender_expert_id": "narrative_designer",
  "arbiter_expert_id": "storyboard_quality_reviewer",
  "critic_invocation_ids": ["..."],
  "defender_invocation_ids": ["..."],
  "arbiter_invocation_id": "...",
  "critic_scorecard": {},
  "defender_scorecard": {},
  "arbiter_scorecard": {},
  "missing_scorecards": [],
  "final_verdict": "pass",
  "repair_intent": "none",
  "downgrade_reason": ""
}
```

Existing UI and API readers that only check `stage_status`, `invocation_ids`, `invocations`, `debate.status`, `final_verdict`, or `repair_intent` continue to work.

## Error Handling

- Missing debate policy is a configuration error in tests, not a runtime fallback.
- Missing or malformed arbiter scorecard blocks the stage.
- Runtime `failed` or `blocked` for any arbiter invocation blocks the stage.
- Critic/defender missing scorecards are recorded and included in `downgrade_reason`, but final blocking is based on arbiter result.
- Repair intent mapping continues to use the existing stage-based helper.

## Testing

- Policy unit test: every `STAGE_DAG` stage has a debate policy and every policy expert id exists in the manifest.
- Debate audit unit test: stage-specific critic, defender, and arbiter experts are invoked in order.
- Debate audit unit test: arbiter pass completes the stage even when critic/defender disagree.
- Debate audit unit test: missing arbiter scorecard blocks the stage and records repair intent.
- Existing provider-stage LangChain tool tests remain the source of truth for paid provider submit/query behavior.
- Run targeted agency debate tests, Chinese comment checker, and backend compile check.

## Non-Goals

- No new database table.
- No frontend redesign.
- No LangGraph or separate long-running multi-agent runtime.
- No provider client rewrite.
- No paid provider submit/query tools inside debate turns.

## Spec Self-Review

- No placeholders remain.
- The design extends the existing v1 debate contract instead of replacing it.
- The scope is one implementation slice: stage policy table, debate runner update, and tests.
- The LangChain boundary is explicit: debate uses the existing expert LangChain path; provider write tools stay in provider-stage orchestration.
