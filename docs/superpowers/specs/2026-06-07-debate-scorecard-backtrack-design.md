# Debate Scorecard Backtrack Design

Status: auto-approved by user instruction on 2026-06-07.

## Goal

Add an adversarial review layer to the existing agency quality gates so image/video production reviews return a structured scorecard, run a two-role debate, and stop infinite retries by backtracking after repeated failures.

## Existing Behavior

- `AgencyOrchestrator` runs reviewers, a lead, and QA for each stage.
- Stage status is derived from expert `result_status`: `blocked` wins, then `failed`, then `warn`, otherwise `completed`.
- `warn` is currently visible in traces but does not block provider submission.
- `blocked` and `failed` block provider stages through `video_production_service._guard_provider_stage`.
- Expert output is persisted in `AgencyExpertInvocation.output_summary_json` and converted into repair tasks by `agency_repair_classifier`.
- Repair jobs already use `agency_auto_repair:<type>` via `agency_repair_orchestrator`.

## Requirements

1. Define a stable JSON scorecard schema for review output.
2. Preserve scorecards in runtime output and invocation records.
3. Run a two-round adversarial debate for every `AgencyOrchestrator` review stage:
   - `visual_storyteller` is the critic.
   - `video_stage_quality_reviewer` is the defender.
   - Each role returns a scorecard in both rounds.
   - If the second round still disagrees, downgrade to a blocked review.
4. On debate failure or unresolved disagreement, emit a repair intent:
   - Image-stage failures prefer prompt tuning or inpainting.
   - Video-stage failures prefer backtracking to image regeneration or inpainting.
5. If the same latest image/video target receives 3 consecutive failed/rejected review records, stop retrying the same step and backtrack one node:
   - `video_segment` failure -> enqueue image repair/regeneration for the same segment.
   - `image` failure -> enqueue storyboard prompt tuning for the same segment/frame.
6. Do not introduce a new database table for this iteration; use existing JSON fields and repair job/events.

## Scorecard JSON Contract

Expert output may include:

```json
{
  "scorecard": {
    "schema_version": "agency.scorecard.v1",
    "overall_score": 82,
    "pass_threshold": 80,
    "verdict": "pass",
    "dimensions": [
      {
        "key": "story_continuity",
        "label": "叙事连续性",
        "score": 86,
        "threshold": 80,
        "weight": 0.25,
        "finding": "镜头动作与上一段衔接清楚",
        "evidence": ["frame-001"],
        "recommendation": ""
      }
    ],
    "repair_intent": "none",
    "confidence": 0.86
  }
}
```

Allowed verdicts: `pass`, `warn`, `fail`, `block`.

Allowed repair intents: `none`, `prompt_tune`, `inpainting`, `regenerate_image`, `regenerate_video`, `backtrack_storyboard`.

## Debate Trace Contract

Agency traces may include:

```json
{
  "debate": {
    "schema_version": "agency.debate.v1",
    "stage": "video_stage",
    "status": "unresolved",
    "rounds": 2,
    "critic_invocation_ids": ["..."],
    "defender_invocation_ids": ["..."],
    "final_verdict": "block",
    "repair_intent": "regenerate_image",
    "downgrade_reason": "双方第二轮未就视频质量达成一致"
  }
}
```

The debate trace is appended to the existing agency trace. If `final_verdict` is `fail` or `block`, the stage trace is downgraded to `blocked`, so downstream provider submission is blocked. Blocked debates also record `agency_debate_repair_intent`; when a production plan exists, they create idempotent `agency_auto_repair:*` jobs through existing repair-stage types. When those jobs target a production segment, the repair executor appends an auditable micro-tuning prompt and moves the segment back to image generation.

## Backtrack Policy

The policy counts latest-version review records for the same target:

- Count statuses: `rejected`, `failed`, `blocked`, `needs_human`.
- Scope: same `run_id`, same `target_type/target_id` when available, otherwise same `asset_id`; latest asset review only.
- Threshold: 3.

Backtrack actions:

- `video_segment` -> enqueue `agency_auto_repair:video_segment_failed` targeting the production segment, with metadata `backtrack_to=image_generation`.
- `image` -> enqueue `agency_auto_repair:image_generation_failed` targeting the production segment/frame, with metadata `backtrack_to=storyboard`.

This reuses existing manual/auto repair policy gates. If auto execution is not authorized, the system records manual-required repair events instead of silently retrying.

## Non-Goals

- No new frontend screen in this iteration.
- No direct provider-specific inpainting API call unless an existing repair executor supports it.
- No schema migration; existing JSON columns are sufficient.

## Verification

- Unit tests for scorecard normalization and debate agreement/disagreement.
- Runtime test that scorecards are accepted and preserved.
- Video production test that three review failures enqueue a backtrack repair job.
- Targeted pytest suite for agency runtime, debate, and video review gates.
