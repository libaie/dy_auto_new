import pytest

from app.db.models import AgencyExpertInvocation, ProductionAuditEvent, ProductionJob, ProductionPlan, Series
from app.domains.video_production.production_queue_service import mark_job_completed
from app.domains.agency_operations.agency_debate_audit import run_debate_audit


class DebateRuntimeResult:
    def __init__(self, status: str, score: float, verdict: str, expert_id: str):
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


class DebateRuntimeResultWithoutScorecard:
    def __init__(self, status: str, expert_id: str):
        self.result_status = status
        self.output_summary = {
            "decision": status,
            "findings": [expert_id],
            "recommendations": [],
            "required_changes": [],
        }
        self.evidence = []
        self.token_usage = {}
        self.model_config_snapshot = {"provider": "mock"}


@pytest.mark.asyncio
async def test_debate_blocks_when_second_round_still_disagrees(db):
    series = Series(title="Debate", logline="case", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.commit()

    calls = []

    async def fake_runtime(**kwargs):
        calls.append((kwargs["role"], kwargs["expert_id"]))
        if kwargs["role"] in {"crit", "arb"}:
            return DebateRuntimeResult("failed", 45, "fail", kwargs["expert_id"])
        return DebateRuntimeResult("passed", 92, "pass", kwargs["expert_id"])

    trace = await run_debate_audit(
        db,
        series_id=series.id,
        production_plan_id=plan.id,
        stage="video_stage",
        stage_context={"frames": [{"frame_id": "shot-001", "production_segment_id": "seg-1"}]},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
        runtime_invoke=fake_runtime,
    )

    assert trace["stage_status"] == "blocked"
    assert trace["debate"]["schema_version"] == "agency.debate.v2"
    assert trace["debate"]["status"] == "consensus_fail"
    assert trace["debate"]["critic_expert_id"] == "visual_storyteller"
    assert trace["debate"]["defender_expert_id"] == "short_video_editing_coach"
    assert trace["debate"]["arbiter_expert_id"] == "video_stage_quality_reviewer"
    assert trace["debate"]["arbiter_invocation_id"]
    assert trace["debate"]["repair_intent"] == "regenerate_image"
    assert calls == [
        ("crit", "visual_storyteller"),
        ("def", "short_video_editing_coach"),
        ("crit", "visual_storyteller"),
        ("def", "short_video_editing_coach"),
        ("arb", "video_stage_quality_reviewer"),
    ]
    assert db.query(AgencyExpertInvocation).filter_by(role="crit").count() == 2
    assert db.query(AgencyExpertInvocation).filter_by(role="def").count() == 2
    assert db.query(AgencyExpertInvocation).filter_by(role="arb").count() == 1
    job = db.query(ProductionJob).one()
    event = db.query(ProductionAuditEvent).filter_by(event_type="agency_debate_repair_intent").one()
    assert job.stage == "agency_auto_repair:video_segment_failed"
    assert job.target_id == "seg-1"
    assert event.payload_json["repair_intent"] == "regenerate_image"


@pytest.mark.asyncio
async def test_completed_debate_repair_job_does_not_dedupe_next_blocking_cycle(db):
    series = Series(title="Debate Repeat", logline="case", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.commit()

    async def fake_runtime(**kwargs):
        if kwargs["role"] in {"crit", "arb"}:
            return DebateRuntimeResult("failed", 45, "fail", kwargs["expert_id"])
        return DebateRuntimeResult("passed", 92, "pass", kwargs["expert_id"])

    kwargs = {
        "db": db,
        "series_id": series.id,
        "production_plan_id": plan.id,
        "stage": "video_stage",
        "stage_context": {"frames": [{"frame_id": "shot-001", "production_segment_id": "seg-1"}]},
        "runtime_config": {"provider": "mock", "model": "mock", "api_key": "x"},
        "runtime_invoke": fake_runtime,
    }
    first = await run_debate_audit(**kwargs)
    assert first["stage_status"] == "blocked"
    first_job = db.query(ProductionJob).one()
    mark_job_completed(db, first_job.id, allowed_statuses=("queued",))

    second = await run_debate_audit(**kwargs)

    jobs = db.query(ProductionJob).order_by(ProductionJob.created_at.asc()).all()
    assert second["stage_status"] == "blocked"
    assert len(jobs) == 2
    assert jobs[0].id != jobs[1].id


@pytest.mark.asyncio
async def test_debate_passes_when_second_round_reaches_consensus(db):
    series = Series(title="Debate Pass", logline="case", genre="drama")
    db.add(series)
    db.commit()
    calls = []

    async def fake_runtime(**kwargs):
        calls.append((kwargs["role"], kwargs["expert_id"]))
        return DebateRuntimeResult("passed", 91, "pass", kwargs["expert_id"])

    trace = await run_debate_audit(
        db,
        series_id=series.id,
        stage="image_review",
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
        runtime_invoke=fake_runtime,
    )

    assert trace["stage_status"] == "completed"
    assert trace["debate"]["schema_version"] == "agency.debate.v2"
    assert trace["debate"]["status"] == "consensus_pass"
    assert trace["debate"]["final_verdict"] == "pass"
    assert trace["debate"]["arbiter_scorecard"]["verdict"] == "pass"
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_debate_passes_when_arbiter_accepts_critic_defender_disagreement(db):
    series = Series(title="Debate Arbiter Pass", logline="case", genre="drama")
    db.add(series)
    db.commit()

    async def fake_runtime(**kwargs):
        if kwargs["role"] == "crit":
            return DebateRuntimeResult("failed", 45, "fail", kwargs["expert_id"])
        return DebateRuntimeResult("passed", 91, "pass", kwargs["expert_id"])

    trace = await run_debate_audit(
        db,
        series_id=series.id,
        stage="video_stage",
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
        runtime_invoke=fake_runtime,
    )

    assert trace["stage_status"] == "completed"
    assert trace["debate"]["status"] == "consensus_pass"
    assert trace["debate"]["critic_scorecard"]["verdict"] == "fail"
    assert trace["debate"]["defender_scorecard"]["verdict"] == "pass"
    assert trace["debate"]["arbiter_scorecard"]["verdict"] == "pass"
    assert trace["debate"]["repair_intent"] == "none"


@pytest.mark.asyncio
async def test_debate_blocks_when_runtime_passes_without_scorecard(db):
    series = Series(title="Debate Pass Legacy", logline="case", genre="drama")
    db.add(series)
    db.commit()

    async def fake_runtime(**kwargs):
        return DebateRuntimeResultWithoutScorecard("passed", kwargs["expert_id"])

    trace = await run_debate_audit(
        db,
        series_id=series.id,
        stage="style_lock",
        stage_context={"style_lock": {"locked": True}},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
        runtime_invoke=fake_runtime,
    )

    assert trace["stage_status"] == "blocked"
    assert trace["debate"]["status"] == "consensus_fail"
    assert trace["debate"]["final_verdict"] == "block"
    assert trace["debate"]["missing_scorecards"] == ["critic", "defender", "arbiter"]
    assert "scorecard" in trace["debate"]["downgrade_reason"]


@pytest.mark.asyncio
async def test_debate_blocks_when_arbiter_passes_without_scorecard(db):
    series = Series(title="Debate Missing Arbiter", logline="case", genre="drama")
    db.add(series)
    db.commit()

    async def fake_runtime(**kwargs):
        if kwargs["role"] == "arb":
            return DebateRuntimeResultWithoutScorecard("passed", kwargs["expert_id"])
        return DebateRuntimeResult("passed", 91, "pass", kwargs["expert_id"])

    trace = await run_debate_audit(
        db,
        series_id=series.id,
        stage="style_lock",
        stage_context={"style_lock": {"locked": True}},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
        runtime_invoke=fake_runtime,
    )

    assert trace["stage_status"] == "blocked"
    assert trace["debate"]["status"] == "consensus_fail"
    assert trace["debate"]["final_verdict"] == "block"
    assert trace["debate"]["missing_scorecards"] == ["arbiter"]
    assert "arbiter" in trace["debate"]["downgrade_reason"]
