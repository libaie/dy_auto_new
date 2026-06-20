import pytest
from sqlalchemy.exc import IntegrityError

from app.db_models import AgencyCreativePatch, AgencyExpertInvocation, Episode, ProductionAuditEvent, Series
from app.services.agency_persistence import (
    create_or_resume_invocation,
    finalize_invocation_and_audit,
)


SOURCE = {
    "repo": "jnMetaCode/agency-agents-zh",
    "commit": "13b8800",
    "path": "specialized/prompt-engineer.md",
    "sha256": "a" * 64,
}


def _series(db):
    series = Series(title="Test series", logline="One sentence", genre="drama")
    db.add(series)
    db.commit()
    return series


def test_create_or_resume_invocation_is_idempotent(db):
    series = _series(db)

    first = create_or_resume_invocation(
        db,
        idempotency_key="series-stage-expert-inputhash",
        series_id=series.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source=SOURCE,
        input_summary={"frame_count": 3},
    )
    second = create_or_resume_invocation(
        db,
        idempotency_key="series-stage-expert-inputhash",
        series_id=series.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source=SOURCE,
        input_summary={"frame_count": 999},
    )

    assert first.id == second.id
    assert db.query(AgencyExpertInvocation).count() == 1
    assert second.execution_status in {"queued", "running"}
    assert second.result_status == "pending"
    assert second.input_summary_json == {"frame_count": 3}


def test_create_or_resume_invocation_recovers_from_unique_key_race(db, monkeypatch):
    series = _series(db)
    calls = {"count": 0}
    real_commit = db.commit

    def commit_with_race():
        calls["count"] += 1
        if calls["count"] == 1:
            db.rollback()
            winner = AgencyExpertInvocation(
                idempotency_key="race-key",
                series_id=series.id,
                stage="storyboard",
                expert_id="prompt_engineer",
                role="reviewer",
                execution_status="running",
                result_status="pending",
                input_summary_json={"winner": True},
                source_repo=SOURCE["repo"],
                source_commit=SOURCE["commit"],
                source_path=SOURCE["path"],
                source_sha256=SOURCE["sha256"],
            )
            db.add(winner)
            real_commit()
            raise IntegrityError("insert", {}, Exception("unique race"))
        return real_commit()

    monkeypatch.setattr(db, "commit", commit_with_race)

    invocation = create_or_resume_invocation(
        db,
        idempotency_key="race-key",
        series_id=series.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source=SOURCE,
        input_summary={"winner": False},
    )

    assert db.query(AgencyExpertInvocation).count() == 1
    assert invocation.input_summary_json == {"winner": True}


def test_create_or_resume_invocation_reraises_unrelated_integrity_error(db, monkeypatch):
    series = _series(db)
    original_error = IntegrityError("insert", {}, Exception("not idempotency"))

    def commit_with_integrity_error():
        raise original_error

    monkeypatch.setattr(db, "commit", commit_with_integrity_error)

    with pytest.raises(IntegrityError) as exc_info:
        create_or_resume_invocation(
            db,
            idempotency_key="missing-after-integrity-error",
            series_id=series.id,
            stage="storyboard",
            expert_id="prompt_engineer",
            role="reviewer",
            source=SOURCE,
            input_summary={"frame_count": 3},
        )

    assert exc_info.value is original_error


def test_finalize_invocation_writes_audit_mirror_and_redacts_nested_payload(db):
    series = _series(db)
    invocation = create_or_resume_invocation(
        db,
        idempotency_key="finish-key",
        series_id=series.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source={**SOURCE, "sha256": "b" * 64},
        input_summary={"nested": {"api_key": "input-secret"}},
    )

    finalized = finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="passed",
        output_summary={
            "decision": "pass",
            "nested": {
                "authorization": "Bearer secret",
                "visible": "keep",
            },
        },
        evidence=[{"message": "storyboard structure is clear"}],
        token_usage={"total_tokens": 123},
        model_config_snapshot={"model": "doubao", "nested": {"token": "model-secret"}},
        duration_ms=42,
    )

    audit = db.query(ProductionAuditEvent).filter(
        ProductionAuditEvent.payload_json["agency_invocation_id"].as_string() == finalized.id
    ).one()
    assert finalized.execution_status == "completed"
    assert finalized.result_status == "passed"
    assert finalized.output_summary_json["decision"] == "pass"
    assert finalized.evidence_json == [{"message": "storyboard structure is clear"}]
    assert finalized.token_usage_json == {"total_tokens": 123}
    assert finalized.model_config_snapshot_json["nested"]["token"] == "model-secret"
    assert finalized.duration_ms == 42
    assert finalized.finished_at is not None
    assert audit.event_type == "agency.invocation.completed"
    assert audit.payload_json["output_summary"]["nested"]["authorization"] == "[REDACTED]"
    assert audit.payload_json["output_summary"]["nested"]["visible"] == "keep"
    assert audit.payload_json["model_config_snapshot"]["nested"]["token"] == "[REDACTED]"


def test_finalize_invocation_creates_creative_patch_rows(db):
    series = _series(db)
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "原"}]},
    )
    db.add(episode)
    db.commit()
    invocation = create_or_resume_invocation(
        db,
        idempotency_key="creative-patch-finalize",
        series_id=series.id,
        episode_id=episode.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source=SOURCE,
        input_summary={},
    )

    finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="warn",
        output_summary={
            "decision": "需要改稿",
            "creative_patches": [{
                "patch_type": "storyboard_patch",
                "target_type": "storyboard_frame",
                "target_id": "shot-001",
                "stage": "storyboard",
                "title": "强化钩子",
                "reason": "前三秒弱。",
                "before": {"image_prompt": "原"},
                "after": {"image_prompt": "新"},
                "apply_policy": "requires_human_approval",
            }],
        },
        evidence=[],
    )

    patch = db.query(AgencyCreativePatch).one()
    assert patch.source_invocation_id == invocation.id
    assert patch.status == "proposed"


def test_finalize_invocation_is_idempotent_for_terminal_invocation(db):
    series = _series(db)
    invocation = create_or_resume_invocation(
        db,
        idempotency_key="terminal-idempotency-key",
        series_id=series.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source=SOURCE,
        input_summary={},
    )

    first = finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="passed",
        output_summary={"decision": "first"},
        evidence=[{"message": "first evidence"}],
        token_usage={"total_tokens": 10},
        duration_ms=42,
    )
    second = finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="failed",
        output_summary={"decision": "second"},
        evidence=[{"message": "second evidence"}],
        token_usage={"total_tokens": 99},
        error_code="should_not_persist",
        duration_ms=99,
    )

    db.expire_all()
    stored = db.query(AgencyExpertInvocation).filter_by(id=invocation.id).one()
    audit_count = db.query(ProductionAuditEvent).filter_by(
        event_type="agency.invocation.completed",
    ).count()

    assert first.id == second.id == stored.id
    assert stored.execution_status == "completed"
    assert stored.result_status == "passed"
    assert stored.output_summary_json == {"decision": "first", "repair_tasks": []}
    assert stored.evidence_json == [{"message": "first evidence"}]
    assert stored.token_usage_json == {"total_tokens": 10}
    assert stored.error_code is None
    assert stored.duration_ms == 42
    assert audit_count == 1


def test_finalize_invocation_records_failure_and_repair_details(db):
    series = _series(db)
    invocation = create_or_resume_invocation(
        db,
        idempotency_key="failed-key",
        series_id=series.id,
        stage="video_review",
        expert_id="reality_checker",
        role="qa",
        source=SOURCE,
        input_summary={},
    )

    finalized = finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="failed",
        output_summary={"decision": "block"},
        evidence=[],
        error_code="bad_output",
        error_message="Invalid JSON",
        repair={
            "repair_action": "retry",
            "repair_route": "runtime",
            "repair_target_type": "invocation",
            "repair_target_ids": [invocation.id],
            "retry_scope": "same_input",
        },
    )

    assert finalized.execution_status == "failed"
    assert finalized.error_code == "bad_output"
    assert finalized.error_message == "Invalid JSON"
    assert finalized.repair_action == "retry"
    assert finalized.repair_route == "runtime"
    assert finalized.repair_target_type == "invocation"
    assert finalized.repair_target_ids_json == [invocation.id]
    assert finalized.retry_scope == "same_input"
