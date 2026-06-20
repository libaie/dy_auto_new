import asyncio

import pytest

from app.db.models import AgencyExpertInvocation, Series
from app.domains.agency_operations import agency_orchestrator
from app.domains.agency_operations.agency_manifest import AgencyManifestError
from app.domains.agency_operations.agency_manifest import EXPERT_IDS, list_experts, load_manifest
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator, STAGE_DAG
from app.domains.agency_operations.agency_runtime import AgencyRuntimeError
from app.domains.agency_operations.video_agency_team import build_video_agency_team


class RuntimeResult:
    def __init__(self, result_status="passed", expert_id="expert"):
        score = 40 if result_status in {"blocked", "failed"} else 90
        verdict = "fail" if result_status in {"blocked", "failed"} else "pass"
        self.result_status = result_status
        self.output_summary = {
            "decision": result_status,
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
        self.evidence = [{"expert_id": expert_id}]
        self.token_usage = {"total_tokens": 10}
        self.model_config_snapshot = {"provider": "mock", "model": "mock"}


def _series(db):
    series = Series(title="Test series", logline="City doctor case", genre="drama")
    db.add(series)
    db.commit()
    return series


def _runtime_config():
    return {"provider": "mock", "model": "mock", "api_key": "secret", "config": {}}


def test_stage_dag_has_expected_video_production_topology():
    assert STAGE_DAG == {
        "story_planning": {
            "reviewers": ["narrative_designer", "douyin_strategist"],
            "lead": "story_generator",
            "qa": [],
        },
        "style_lock": {
            "reviewers": ["image_prompt_engineer", "short_video_editing_coach"],
            "lead": "visual_storyteller",
            "qa": ["style_lock_quality_reviewer"],
        },
        "storyboard": {
            "reviewers": ["visual_storyteller", "short_video_editing_coach", "douyin_strategist"],
            "lead": "narrative_designer",
            "qa": ["storyboard_quality_reviewer"],
        },
        "image_stage": {
            "reviewers": ["visual_storyteller", "prompt_engineer"],
            "lead": "image_prompt_engineer",
            "qa": ["image_stage_quality_reviewer"],
        },
        "image_review": {
            "reviewers": ["image_prompt_engineer"],
            "lead": "visual_storyteller",
            "qa": ["image_review_quality_reviewer"],
        },
        "video_stage": {
            "reviewers": ["prompt_engineer", "visual_storyteller"],
            "lead": "short_video_editing_coach",
            "qa": ["video_stage_quality_reviewer"],
        },
        "video_review": {
            "reviewers": ["video_optimization_specialist"],
            "lead": "short_video_editing_coach",
            "qa": ["video_review_quality_reviewer"],
        },
        "compose_preflight": {
            "reviewers": ["douyin_strategist", "video_optimization_specialist"],
            "lead": "short_video_editing_coach",
            "qa": [],
        },
        "compose": {
            "reviewers": ["douyin_strategist", "video_optimization_specialist"],
            "lead": "short_video_editing_coach",
            "qa": ["compose_quality_reviewer"],
        },
    }


def test_each_stage_has_exactly_one_stage_specific_quality_reviewer():
    expected_qa = {
        "style_lock": "style_lock_quality_reviewer",
        "storyboard": "storyboard_quality_reviewer",
        "image_stage": "image_stage_quality_reviewer",
        "image_review": "image_review_quality_reviewer",
        "video_stage": "video_stage_quality_reviewer",
        "video_review": "video_review_quality_reviewer",
        "compose": "compose_quality_reviewer",
    }

    for stage, config in STAGE_DAG.items():
        if stage in {"story_planning", "compose_preflight"}:
            assert config["qa"] == []
            continue
        assert config["qa"] == [expected_qa[stage]]


def test_stage_dag_never_assigns_legacy_reality_checker():
    for roles in STAGE_DAG.values():
        assigned = [*roles["reviewers"], roles["lead"], *roles["qa"]]
        assert "reality_checker" not in assigned


@pytest.mark.asyncio
async def test_story_planning_review_uses_story_team_without_debate_roles(db):
    series = _series(db)

    async def fake_runtime(**kwargs):
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime)
    result = await orchestrator.run_story_planning_review(
        db,
        series_id=series.id,
        stage_context={"episode_cards": [{"episode_number": 1, "hook": "开场反转"}]},
        runtime_config=_runtime_config(),
    )

    invocations = (
        db.query(AgencyExpertInvocation)
        .filter(AgencyExpertInvocation.series_id == series.id)
        .order_by(AgencyExpertInvocation.created_at.asc(), AgencyExpertInvocation.id.asc())
        .all()
    )

    assert result["stage"] == "story_planning"
    assert result["stage_status"] == "completed"
    assert [(item.stage, item.role, item.expert_id) for item in invocations] == [
        ("story_planning", "reviewer", "narrative_designer"),
        ("story_planning", "reviewer", "douyin_strategist"),
        ("story_planning", "lead", "story_generator"),
    ]


@pytest.mark.asyncio
async def test_storyboard_stage_creates_reviewer_lead_and_qa_invocations(db):
    series = _series(db)

    async def fake_runtime(**kwargs):
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    result = await orchestrator.run_storyboard_review(
        db,
        series_id=series.id,
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config=_runtime_config(),
    )

    invocations = (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.stage == "storyboard",
        )
        .all()
    )
    roles = [item.role for item in invocations]
    assert roles.count("reviewer") == len(STAGE_DAG["storyboard"]["reviewers"])
    assert roles.count("lead") == 1
    assert roles.count("qa") == len(STAGE_DAG["storyboard"]["qa"])
    assert result["stage_status"] == "completed"
    assert len(result["invocation_ids"]) == len(invocations)


@pytest.mark.asyncio
async def test_stage_appends_two_round_debate_by_default(db):
    series = _series(db)
    calls = []

    async def fake_runtime(**kwargs):
        calls.append((kwargs["role"], kwargs["expert_id"]))
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime)
    result = await orchestrator.run_storyboard_review(
        db,
        series_id=series.id,
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config=_runtime_config(),
    )

    assert result["stage_status"] == "completed"
    assert result["debate"]["status"] == "consensus_pass"
    assert result["debate"]["rounds"] == 2
    assert calls[-4:] == [
        ("crit", "visual_storyteller"),
        ("def", "video_stage_quality_reviewer"),
        ("crit", "visual_storyteller"),
        ("def", "video_stage_quality_reviewer"),
    ]


@pytest.mark.asyncio
async def test_manifest_failure_blocks_stage_before_creating_invocations(db, monkeypatch):
    series = _series(db)
    runtime_calls = []

    def broken_manifest():
        raise AgencyManifestError("agency manifest hash mismatch: storyboard-quality-reviewer.md")

    async def fake_runtime(**kwargs):
        runtime_calls.append(kwargs)
        return RuntimeResult(expert_id=kwargs["expert_id"])

    monkeypatch.setattr(agency_orchestrator, "verify_manifest", broken_manifest, raising=False)

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    result = await orchestrator.run_storyboard_review(
        db,
        series_id=series.id,
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config=_runtime_config(),
    )

    assert result == {
        "stage": "storyboard",
        "stage_status": "blocked",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "AGENCY_MANIFEST_INVALID",
        "error_message": "Agency expert manifest is invalid. Please refresh embedded expert assets.",
    }
    assert runtime_calls == []
    assert db.query(AgencyExpertInvocation).filter(AgencyExpertInvocation.series_id == series.id).count() == 0


@pytest.mark.asyncio
async def test_reviewers_run_with_bounded_concurrency_before_lead_and_qa(db):
    series = _series(db)
    active_reviewers = 0
    max_active_reviewers = 0
    call_order = []
    runtime_db_by_role = {"reviewer": [], "lead": [], "qa": []}

    async def fake_runtime(**kwargs):
        nonlocal active_reviewers, max_active_reviewers
        role = kwargs["role"]
        call_order.append((role, kwargs["expert_id"]))
        runtime_db_by_role[role].append(kwargs["db"])
        if role == "reviewer":
            active_reviewers += 1
            max_active_reviewers = max(max_active_reviewers, active_reviewers)
            await asyncio.sleep(0.01)
            active_reviewers -= 1
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, reviewer_concurrency=2, enable_debate=False)
    result = await orchestrator.run_style_lock_review(
        db,
        series_id=series.id,
        stage_context={"style_lock": {"characters": []}},
        runtime_config=_runtime_config(),
    )

    assert max_active_reviewers == 2
    assert [role for role, _expert_id in call_order[:2]] == ["reviewer", "reviewer"]
    assert [role for role, _expert_id in call_order[2:]] == ["lead", "qa"]
    assert runtime_db_by_role["reviewer"] == [None, None]
    assert runtime_db_by_role["lead"] == [None]
    assert runtime_db_by_role["qa"] == [None]
    assert result["stage_status"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runtime_status_by_role", "expected_stage_status"),
    [
        ({}, "completed"),
        ({"reviewer": "blocked"}, "blocked"),
        ({"lead": "blocked"}, "blocked"),
        ({"qa": "blocked"}, "blocked"),
        ({"reviewer": "failed"}, "failed"),
        ({"lead": "failed"}, "failed"),
        ({"qa": "failed"}, "failed"),
        ({"reviewer": "warn"}, "warning"),
        ({"lead": "warn"}, "warning"),
        ({"qa": "warn"}, "warning"),
    ],
)
async def test_stage_status_mapping_for_terminal_outcomes(db, runtime_status_by_role, expected_stage_status):
    series = _series(db)

    async def fake_runtime(**kwargs):
        status = runtime_status_by_role.get(kwargs["role"], "passed")
        return RuntimeResult(result_status=status, expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    if "qa" in runtime_status_by_role:
        result = await orchestrator.run_storyboard_review(
            db,
            series_id=series.id,
            stage_context={"frames": [{"frame_id": "shot-001"}]},
            runtime_config=_runtime_config(),
        )
    else:
        result = await orchestrator.run_style_lock_review(
            db,
            series_id=series.id,
            stage_context={"style_lock": {"characters": []}},
            runtime_config=_runtime_config(),
        )

    assert result["stage_status"] == expected_stage_status


@pytest.mark.asyncio
async def test_stage_status_precedence_uses_all_invocations(db):
    series = _series(db)
    statuses_by_expert = {
        "visual_storyteller": "failed",
        "short_video_editing_coach": "warn",
        "douyin_strategist": "passed",
        "narrative_designer": "passed",
        "storyboard_quality_reviewer": "blocked",
    }

    async def fake_runtime(**kwargs):
        status = statuses_by_expert[kwargs["expert_id"]]
        return RuntimeResult(result_status=status, expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    result = await orchestrator.run_storyboard_review(
        db,
        series_id=series.id,
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config=_runtime_config(),
    )

    assert result["stage_status"] == "blocked"


@pytest.mark.asyncio
async def test_non_json_serializable_context_fails_before_creating_invocations(db):
    series = _series(db)

    async def fake_runtime(**kwargs):
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    with pytest.raises(ValueError, match="stage_context must be JSON-serializable"):
        await orchestrator.run_style_lock_review(
            db,
            series_id=series.id,
            stage_context={"style_lock": object()},
            runtime_config=_runtime_config(),
        )

    assert db.query(AgencyExpertInvocation).count() == 0


@pytest.mark.asyncio
async def test_missing_openai_runtime_config_blocks_without_creating_invocations(db):
    series = _series(db)
    calls = {"count": 0}

    async def fake_runtime(**kwargs):
        calls["count"] += 1
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    result = await orchestrator.run_style_lock_review(
        db,
        series_id=series.id,
        stage_context={"style_lock": {"characters": []}},
        runtime_config={
            "provider": "openai-compatible",
            "model": "",
            "base_url": "",
            "api_key": "sk-secret-token",
            "config": {"protocol": "openai_chat_completions"},
        },
    )

    assert result["stage_status"] == "blocked"
    assert result["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    assert result["invocation_ids"] == []
    assert result["invocations"] == []
    assert calls["count"] == 0
    assert db.query(AgencyExpertInvocation).count() == 0
    assert "sk-secret-token" not in str(result)


@pytest.mark.asyncio
async def test_idempotency_key_includes_scope_role_expert_and_context_hash(db):
    series = _series(db)

    async def fake_runtime(**kwargs):
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    await orchestrator.run_style_lock_review(
        db,
        series_id=series.id,
        production_segment_id="segment-123",
        stage_context={"b": 2, "a": 1},
        runtime_config=_runtime_config(),
    )
    first = (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.stage == "style_lock",
            AgencyExpertInvocation.role == "reviewer",
            AgencyExpertInvocation.expert_id == "image_prompt_engineer",
        )
        .one()
    )

    await orchestrator.run_style_lock_review(
        db,
        series_id=series.id,
        production_segment_id="segment-456",
        stage_context={"a": 1, "b": 2},
        runtime_config=_runtime_config(),
    )
    second = (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.stage == "style_lock",
            AgencyExpertInvocation.role == "reviewer",
            AgencyExpertInvocation.expert_id == "image_prompt_engineer",
            AgencyExpertInvocation.production_segment_id == "segment-456",
        )
        .one()
    )

    first_parts = first.idempotency_key.split(":")
    second_parts = second.idempotency_key.split(":")
    assert first_parts[:6] == ["agency", series.id, "segment-123", "style_lock", "reviewer", "image_prompt_engineer"]
    assert second_parts[:6] == ["agency", series.id, "segment-456", "style_lock", "reviewer", "image_prompt_engineer"]
    assert len(first_parts[6]) == 24
    assert second_parts[6] == first_parts[6]


def test_stage_dag_excludes_platform_and_model_governance_roles():
    excluded = {"ai_engineer", "software_architect", "product_manager", "model_qa_specialist"}

    for roles in STAGE_DAG.values():
        assigned_experts = [*roles["reviewers"], roles["lead"], *roles["qa"]]
        assert excluded.isdisjoint(assigned_experts)


@pytest.mark.asyncio
async def test_completed_terminal_rerun_does_not_call_runtime_again(db):
    series = _series(db)
    calls = {"count": 0}

    async def fake_runtime(**kwargs):
        calls["count"] += 1
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    kwargs = {
        "series_id": series.id,
        "stage_context": {"frames": [{"frame_id": "shot-001"}]},
        "runtime_config": _runtime_config(),
    }
    first = await orchestrator.run_storyboard_review(db, **kwargs)
    call_count_after_first_run = calls["count"]
    second = await orchestrator.run_storyboard_review(db, **kwargs)

    assert call_count_after_first_run == len(first["invocation_ids"])
    assert calls["count"] == call_count_after_first_run
    assert second["invocation_ids"] == first["invocation_ids"]
    assert db.query(AgencyExpertInvocation).count() == call_count_after_first_run


@pytest.mark.asyncio
async def test_failed_terminal_rerun_does_not_call_runtime_again(db):
    series = _series(db)
    calls = {"count": 0}

    async def fake_runtime(**kwargs):
        calls["count"] += 1
        if kwargs["role"] == "lead":
            raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "bad expert output")
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    kwargs = {
        "series_id": series.id,
        "stage_context": {"style_lock": {"characters": []}},
        "runtime_config": _runtime_config(),
    }
    first = await orchestrator.run_style_lock_review(db, **kwargs)
    call_count_after_first_run = calls["count"]
    second = await orchestrator.run_style_lock_review(db, **kwargs)

    assert first["stage_status"] == "failed"
    assert call_count_after_first_run == len(first["invocation_ids"])
    assert calls["count"] == call_count_after_first_run
    assert second["invocation_ids"] == first["invocation_ids"]


@pytest.mark.asyncio
async def test_retryable_failed_invocation_reruns_runtime(db):
    series = _series(db)
    calls = {"lead": 0, "total": 0}

    async def fake_runtime(**kwargs):
        calls["total"] += 1
        if kwargs["role"] == "lead":
            calls["lead"] += 1
            if calls["lead"] == 1:
                raise AgencyRuntimeError("EXPERT_MODEL_TIMEOUT", "model timed out")
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    kwargs = {
        "series_id": series.id,
        "stage_context": {"style_lock": {"characters": []}},
        "runtime_config": _runtime_config(),
    }
    first = await orchestrator.run_style_lock_review(db, **kwargs)
    second = await orchestrator.run_style_lock_review(db, **kwargs)

    lead = (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.stage == "style_lock",
            AgencyExpertInvocation.role == "lead",
        )
        .one()
    )
    assert first["stage_status"] == "failed"
    assert second["stage_status"] == "completed"
    assert calls["lead"] == 2
    assert lead.execution_status == "completed"
    assert lead.result_status == "passed"
    assert lead.error_code is None
    assert lead.attempt == 2


@pytest.mark.asyncio
async def test_runtime_error_finalizes_failed_invocation_with_error_code(db):
    series = _series(db)

    async def fake_runtime(**kwargs):
        if kwargs["role"] == "lead":
            raise AgencyRuntimeError("EXPERT_MODEL_TIMEOUT", "model timed out")
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    result = await orchestrator.run_style_lock_review(
        db,
        series_id=series.id,
        stage_context={"style_lock": {"characters": []}},
        runtime_config=_runtime_config(),
    )

    failed = (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.stage == "style_lock",
            AgencyExpertInvocation.role == "lead",
        )
        .one()
    )
    assert result["stage_status"] == "failed"
    assert failed.execution_status == "failed"
    assert failed.result_status == "failed"
    assert failed.error_code == "EXPERT_MODEL_TIMEOUT"
    assert failed.error_message == "model timed out"


@pytest.mark.asyncio
async def test_unexpected_runtime_error_finalizes_failed_invocation_with_error_code(db):
    series = _series(db)

    async def fake_runtime(**kwargs):
        if kwargs["role"] == "lead":
            raise ValueError("bad runtime result")
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
    result = await orchestrator.run_style_lock_review(
        db,
        series_id=series.id,
        stage_context={"style_lock": {"characters": []}},
        runtime_config=_runtime_config(),
    )

    failed = (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.stage == "style_lock",
            AgencyExpertInvocation.role == "lead",
        )
        .one()
    )
    assert result["stage_status"] == "failed"
    assert failed.execution_status == "failed"
    assert failed.result_status == "failed"
    assert failed.error_code == "EXPERT_RUNTIME_UNEXPECTED"
    assert failed.error_message == "bad runtime result"


def test_video_agency_team_source_metadata_matches_manifest_for_all_roles():
    manifest = load_manifest()
    manifest_by_id = {expert.expert_id: expert for expert in list_experts()}
    team = build_video_agency_team()
    roles = team["core_roles"] + team["support_roles"] + team["quality_roles"]

    assert {role["id"] for role in roles} == set(manifest_by_id)
    for role in roles:
        expert = manifest_by_id[role["id"]]
        assert role["source_path"] == expert.source_path
        assert role["source_commit"] == manifest.source_commit
        assert role["source_sha256"] == expert.sha256
    assert manifest_by_id["prompt_engineer"].source_path == "specialized/prompt-engineer.md"
    prompt_role = next(role for role in roles if role["id"] == "prompt_engineer")
    assert prompt_role["source_path"] == "specialized/prompt-engineer.md"
    assert prompt_role["source_role"] != "ai-prompt-engineer"


def test_video_agency_team_contains_current_quality_roles_without_legacy():
    team = build_video_agency_team()
    roles = team["core_roles"] + team["support_roles"] + team["quality_roles"]
    role_ids = [role["id"] for role in roles]

    assert "reality_checker" not in role_ids
    assert role_ids == list(EXPERT_IDS)
    assert len(team["core_roles"]) == 7
    assert len(team["support_roles"]) == 1
    assert len(team["quality_roles"]) == 7
    assert team["version"] >= "2026-06-02"
    assert team["support_roles"][0]["id"] == "video_optimization_specialist"
    assert team["core_roles"][0]["id"] == "story_generator"
    assert any(role["id"] == "compose_quality_reviewer" for role in team["quality_roles"])


def test_agency_context_includes_quality_role_briefs_for_stage_prompts():
    from app.domains.agency_operations.video_agency_team import build_agency_context

    context = build_agency_context({"style_lock": {"locked": True}})
    role_brief_ids = [item["id"] for item in context["role_brief"]]

    assert "style_lock_quality_reviewer" in role_brief_ids
    assert "compose_quality_reviewer" in role_brief_ids
    quality_brief = next(item for item in context["role_brief"] if item["id"] == "style_lock_quality_reviewer")
    assert "mission" in quality_brief
    assert quality_brief["directives"]


def test_longest_quality_reviewer_idempotency_key_fits_database_column():
    key = "agency:{series}:{scope}:{stage}:{role}:{expert}:{hash}".format(
        series="s" * 36,
        scope="p" * 36,
        stage="image_review",
        role="qa",
        expert="image_review_quality_reviewer",
        hash="h" * 24,
    )

    assert len(key) <= 160


def test_video_agency_team_phase_metadata_matches_manifest_and_stage_dag():
    manifest_by_id = {expert.expert_id: expert for expert in list_experts()}
    team = build_video_agency_team()
    roles = team["core_roles"] + team["support_roles"] + team["quality_roles"]

    assert {role["id"] for role in roles} == set(manifest_by_id)
    for role in roles:
        assert role["phase"] == manifest_by_id[role["id"]].phases
    assert set(team["quality_gates"]) == set(STAGE_DAG)


def test_stage_dag_assigned_experts_are_listed_in_manifest_phases():
    manifest_by_id = {expert.expert_id: expert for expert in list_experts()}

    for stage, roles in STAGE_DAG.items():
        assigned_experts = [*roles["reviewers"], roles["lead"], *roles["qa"]]
        for expert_id in assigned_experts:
            assert stage in manifest_by_id[expert_id].phases
