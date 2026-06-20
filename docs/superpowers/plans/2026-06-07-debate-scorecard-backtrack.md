# Debate Scorecard Backtrack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured scorecards, two-role adversarial debate, and three-failure backtracking to agency review gates.

**Architecture:** Keep the change inside the existing agency runtime, invocation persistence, repair-task, and video review paths. Scorecards/debate traces are JSON contracts, while backtracking reuses `ProductionJob` repair jobs and `ProductionAuditEvent` records.

**Tech Stack:** FastAPI service layer, SQLAlchemy models with existing JSON columns, Pydantic contracts, pytest.

---

## File Structure

- Create `server/app/services/agency_scorecard_contracts.py`: scorecard normalization, verdict helpers, and Pydantic models.
- Create `server/app/services/agency_debate_audit.py`: two-round critic/defender debate orchestration over `AgencyOrchestrator`, including repair intent job/event creation.
- Create `server/app/services/agency_backtrack_policy.py`: count repeated review failures and enqueue upstream repair jobs.
- Modify `server/app/services/agency_repair_executor.py`: apply production-segment prompt micro-tuning for debate/backtrack repair jobs.
- Modify `server/app/services/agency_runtime.py`: include optional `scorecard` in schema parsing and output summary.
- Modify `server/app/services/agency_prompting.py`: tell experts to return scorecards for review/audit roles.
- Modify `server/app/services/agency_orchestrator.py`: append debate to every stage by default, with an opt-out for legacy unit tests.
- Modify `server/app/services/video_production_service.py`: rely on orchestrator debate traces for provider guards and call backtrack policy after failed AI/human reviews.
- Test `server/tests/test_agency_scorecard_contracts.py`.
- Test `server/tests/test_agency_debate_audit.py`.
- Test `server/tests/test_agency_runtime.py`.
- Test `server/tests/test_agency_backtrack_policy.py`.

## Task 1: Scorecard Contract

**Files:**
- Create: `server/app/services/agency_scorecard_contracts.py`
- Test: `server/tests/test_agency_scorecard_contracts.py`

- [x] **Step 1: Write failing scorecard tests**

```python
from app.services.agency_scorecard_contracts import normalize_scorecard, scorecard_blocks_stage


def test_normalize_scorecard_derives_weighted_overall_and_verdict():
    card = normalize_scorecard({
        "dimensions": [
            {"key": "story", "score": 90, "threshold": 80, "weight": 0.75},
            {"key": "motion", "score": 60, "threshold": 80, "weight": 0.25},
        ],
        "pass_threshold": 80,
    })

    assert card["schema_version"] == "agency.scorecard.v1"
    assert card["overall_score"] == 82.5
    assert card["verdict"] == "pass"
    assert card["repair_intent"] == "none"


def test_scorecard_blocks_stage_for_fail_or_under_threshold():
    fail = normalize_scorecard({"overall_score": 59, "pass_threshold": 80, "verdict": "fail"})
    block = normalize_scorecard({"overall_score": 79, "pass_threshold": 80})

    assert scorecard_blocks_stage(fail) is True
    assert scorecard_blocks_stage(block) is True
```

- [x] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_agency_scorecard_contracts.py -q`

Expected: import failure because the contract module does not exist.

- [x] **Step 3: Implement contract module**

Add `normalize_scorecard`, `scorecard_blocks_stage`, allowed verdict/repair constants, numeric clamping, and safe defaults.

- [x] **Step 4: Run GREEN**

Run: `python -m pytest server/tests/test_agency_scorecard_contracts.py -q`

Expected: both tests pass.

## Task 2: Runtime Scorecard Preservation

**Files:**
- Modify: `server/app/services/agency_runtime.py`
- Modify: `server/app/services/agency_prompting.py`
- Test: `server/tests/test_agency_runtime.py`

- [x] **Step 1: Write failing runtime test**

```python
@pytest.mark.asyncio
async def test_runtime_preserves_optional_scorecard():
    async def fake_client(system_prompt, user_prompt, config):
        assert '"scorecard"' in system_prompt
        return _valid_output(
            decision="通过",
            scorecard={
                "overall_score": 91,
                "pass_threshold": 80,
                "verdict": "pass",
                "dimensions": [{"key": "continuity", "score": 91}],
            },
        )

    runtime = AgencySkillRuntime(model_client=fake_client)
    result = await runtime.invoke(
        db=None,
        expert_id="image_review_quality_reviewer",
        stage="image_review",
        role="qa",
        stage_context={"frame_count": 1},
        runtime_config=_runtime_config(),
    )

    assert result.output_summary["scorecard"]["overall_score"] == 91
    assert result.output_summary["scorecard"]["schema_version"] == "agency.scorecard.v1"
```

- [x] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_agency_runtime.py::test_runtime_preserves_optional_scorecard -q`

Expected: assertion fails because `scorecard` is not in the output schema/summary.

- [x] **Step 3: Implement runtime preservation**

Import `normalize_scorecard`, add optional schema property, and copy normalized scorecard into `output_summary` when present.

- [x] **Step 4: Add prompt instruction**

Add one concise system rule requiring review roles to return `scorecard` with dimensions, thresholds, verdict, and repair intent.

- [x] **Step 5: Run GREEN**

Run: `python -m pytest server/tests/test_agency_runtime.py::test_runtime_preserves_optional_scorecard -q`

Expected: test passes.

## Task 3: Debate Audit

**Files:**
- Create: `server/app/services/agency_debate_audit.py`
- Modify: `server/app/services/agency_orchestrator.py`
- Modify: `server/app/services/video_production_service.py`
- Test: `server/tests/test_agency_debate_audit.py`

- [x] **Step 1: Write failing debate tests**

```python
import pytest

from app.db_models import Series
from app.services.agency_debate_audit import run_debate_audit


class DebateRuntimeResult:
    def __init__(self, status, score, verdict, expert_id):
        self.result_status = status
        self.output_summary = {
            "decision": verdict,
            "findings": [expert_id],
            "recommendations": [],
            "required_changes": [],
            "scorecard": {
                "overall_score": score,
                "pass_threshold": 80,
                "verdict": verdict,
                "dimensions": [{"key": "quality", "score": score}],
            },
        }
        self.evidence = []
        self.token_usage = {}
        self.model_config_snapshot = {"provider": "mock"}


@pytest.mark.asyncio
async def test_debate_blocks_when_second_round_still_disagrees(db):
    series = Series(title="Debate", logline="case", genre="drama")
    db.add(series)
    db.commit()

    async def fake_runtime(**kwargs):
        if kwargs["expert_id"] == "visual_storyteller":
            return DebateRuntimeResult("failed", 45, "fail", kwargs["expert_id"])
        return DebateRuntimeResult("passed", 92, "pass", kwargs["expert_id"])

    trace = await run_debate_audit(
        db,
        series_id=series.id,
        stage="video_stage",
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
        runtime_invoke=fake_runtime,
    )

    assert trace["stage_status"] == "blocked"
    assert trace["debate"]["status"] == "unresolved"
    assert trace["debate"]["repair_intent"] == "regenerate_image"
```

- [x] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_agency_debate_audit.py -q`

Expected: import failure because the debate module does not exist.

- [x] **Step 3: Implement debate module**

Call `AgencyOrchestrator._invoke_one` for two rounds using roles `debate_critic` and `debate_defender`. Load finalized invocation scorecards from `AgencyExpertInvocation.output_summary_json`, compare second-round verdicts, and return a trace with `stage_status`.

- [x] **Step 4: Wire provider guard**

In `AgencyOrchestrator._run_stage`, after the normal stage trace, call debate for every stage unless `enable_debate=False`. If debate returns `blocked` or `failed`, merge it into the trace and let existing provider gates block downstream submission.

- [x] **Step 5: Run GREEN**

Run: `python -m pytest server/tests/test_agency_debate_audit.py -q`

Expected: debate test passes.

## Task 4: Backtrack Policy

**Files:**
- Create: `server/app/services/agency_backtrack_policy.py`
- Modify: `server/app/services/video_production_service.py`
- Test: `server/tests/test_agency_backtrack_policy.py`

- [x] **Step 1: Write failing backtrack test**

```python
from app.db_models import Episode, ProductionAuditEvent, ProductionJob, ProductionPlan, ProductionSegment, ProductionShot, ProductionScene, ProductionEpisode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.agency_backtrack_policy import trigger_backtrack_if_needed


def test_third_video_failure_enqueues_backtrack_to_image_generation(db):
    series = Series(title="Backtrack", logline="case", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, storyboard_json={"frames": []})
    db.add(episode)
    plan = ProductionPlan(series_id=series.id, title="Plan", status="active")
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_number=1, title="E1")
    db.add(prod_episode)
    db.flush()
    scene = ProductionScene(production_episode_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(production_scene_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(shot_plan_id=shot.id, segment_id="seg-1", order_index=1)
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="video_review_pending",
        current_stage="video_review",
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type="video_segment",
        stage="video_generation",
        status="review_pending",
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        is_latest=True,
    )
    db.add(asset)
    db.flush()
    for status in ["needs_human", "rejected", "rejected"]:
        db.add(VideoReviewRecord(
            asset_id=asset.id,
            run_id=run.id,
            review_type="human",
            status=status,
            target_type="production_segment",
            target_id=segment.id,
            production_segment_id=segment.id,
            asset_version=asset.version,
            is_latest_asset_review=True,
        ))
    db.commit()

    result = trigger_backtrack_if_needed(db, run, asset, reason="视频连续失败")

    job = db.query(ProductionJob).one()
    event = db.query(ProductionAuditEvent).filter_by(event_type="agency_backtrack_triggered").one()
    assert result["triggered"] is True
    assert job.stage == "agency_auto_repair:video_segment_failed"
    assert job.target_id == segment.id
    assert event.payload_json["backtrack_to"] == "image_generation"
```

- [x] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_agency_backtrack_policy.py -q`

Expected: import failure because the backtrack module does not exist.

- [x] **Step 3: Implement backtrack policy**

Count failed latest review records, derive repair task by asset type, create one idempotent `ProductionJob`, and record `agency_backtrack_triggered`.

- [x] **Step 4: Wire review paths**

Call `trigger_backtrack_if_needed` after AI review records and human `reject_asset` records are written. Do not alter approval paths.

- [x] **Step 5: Run GREEN**

Run: `python -m pytest server/tests/test_agency_backtrack_policy.py -q`

Expected: test passes.

## Task 5: Targeted Verification

**Files:**
- All modified files above.

- [x] **Step 1: Run agency/runtime/backtrack tests**

Run: `python -m pytest server/tests/test_agency_scorecard_contracts.py server/tests/test_agency_runtime.py::test_runtime_preserves_optional_scorecard server/tests/test_agency_debate_audit.py server/tests/test_agency_backtrack_policy.py -q`

Expected: all pass.

- [x] **Step 2: Run regression slices**

Run: `python -m pytest server/tests/test_agency_orchestrator.py server/tests/test_agency_persistence.py server/tests/test_video_production_ai_audit_gate.py -q`

Expected: all pass.

## Self-Review

Spec coverage:
- Scorecard schema: Task 1 and Task 2.
- Dual-role debate: Task 3.
- Disagreement downgrade and repair intent: Task 3.
- Three-failure circuit breaker and backtrack: Task 4.
- Existing repair integration: Task 4.

Placeholder scan:
- No TBD/TODO placeholders are present.

Type consistency:
- `scorecard`, `debate`, `repair_intent`, and `agency_auto_repair:<type>` names are consistent across tasks.
