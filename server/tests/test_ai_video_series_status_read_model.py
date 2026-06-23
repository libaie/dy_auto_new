import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import app
from app.db.models.ai_video_series import (
    AITextArtifact,
    Episode,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    Series,
    VideoProductionRun,
)
from app.domains.ai_video_series.status_read_model import build_episode_status_matrix


def _series_with_episode(db):
    series = Series(title="Status Matrix", logline="Truth", genre="drama", total_episodes=1)
    episode = Episode(series=series, episode_number=1, title="Pilot", status="pending")
    db.add_all([series, episode])
    db.flush()
    return series, episode


def test_episode_without_artifacts_or_run_is_not_started(db):
    series, episode = _series_with_episode(db)
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "not_started"
    assert matrix[episode.id]["has_episode_script"] is False
    assert matrix[episode.id]["has_storyboard"] is False
    assert matrix[episode.id]["active_run_id"] is None
    assert matrix[episode.id]["blocking_code"] == "NO_ACTIVE_RUN"


def test_episode_with_script_and_storyboard_is_ready_for_production(db):
    series, episode = _series_with_episode(db)
    db.add_all([
        AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_script",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"script": "approved"},
        ),
        AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="storyboard",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"frames": [{"frame_id": "f1"}]},
        ),
    ])
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "ready_for_production"
    assert matrix[episode.id]["has_episode_script"] is True
    assert matrix[episode.id]["has_storyboard"] is True
    assert matrix[episode.id]["blocking_code"] is None


@pytest.mark.parametrize("run_status", ["running", "image_batch_running"])
def test_running_run_without_active_job_is_blocked_with_named_code(db, run_status):
    series, episode = _series_with_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status=run_status,
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "blocked"
    assert matrix[episode.id]["active_run_id"] == run.id
    assert matrix[episode.id]["blocking_code"] == "RUNNING_WITHOUT_ACTIVE_JOB"


def test_series_detail_payload_includes_nested_production_status(db):
    series, episode = _series_with_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_batch_running",
        current_stage="image_generation",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    response = TestClient(app).get(f"/api/series/{series.id}")

    assert response.status_code == 200
    episode_payload = response.json()["episodes"][0]
    assert episode_payload["active_video_run_id"] == run.id
    assert episode_payload["video_run_status"] == "image_batch_running"
    assert episode_payload["production_status"]["active_run_id"] == run.id
    assert episode_payload["production_status"]["latest_run_status"] == "image_batch_running"
    assert episode_payload["production_status"]["production_status"] == "blocked"
    assert episode_payload["production_status"]["blocking_code"] == "RUNNING_WITHOUT_ACTIVE_JOB"


def test_running_run_with_active_job_is_producing(db):
    series, episode = _series_with_episode(db)
    plan = ProductionPlan(series_id=series.id, status="running")
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.flush()
    db.add(ProductionJob(
        plan_id=plan.id,
        target_type="episode",
        target_id=episode.id,
        stage="image_generation",
        status="running",
        idempotency_key=f"{run.id}:image_generation",
    ))
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "producing"
    assert matrix[episode.id]["active_run_id"] == run.id
    assert matrix[episode.id]["active_job_count"] == 1
    assert matrix[episode.id]["blocking_code"] is None


def test_status_payload_includes_batched_audit_evidence(db):
    series, episode = _series_with_episode(db)
    plan = ProductionPlan(series_id=series.id, status="running")
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
    db.add(production_episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.flush()
    db.add_all([
        ProductionAuditEvent(
            event_type="run.created",
            run_id=run.id,
            production_plan_id=plan.id,
            payload_json={"source": "run"},
        ),
        ProductionAuditEvent(
            event_type="image.job.created",
            production_plan_id=plan.id,
            production_episode_id=production_episode.id,
            payload_json={"source": "plan"},
        ),
    ])
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["audit_event_count"] == 2
    assert matrix[episode.id]["latest_audit_event_type"] in {"run.created", "image.job.created"}


def test_same_plan_jobs_and_audits_do_not_bleed_between_episodes(db):
    series = Series(title="Status Matrix", logline="Truth", genre="drama", total_episodes=2)
    episode_one = Episode(series=series, episode_number=1, title="One", status="pending")
    episode_two = Episode(series=series, episode_number=2, title="Two", status="pending")
    db.add_all([series, episode_one, episode_two])
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running")
    db.add(plan)
    db.flush()
    production_episode_one = ProductionEpisode(plan_id=plan.id, episode_id=episode_one.id)
    production_episode_two = ProductionEpisode(plan_id=plan.id, episode_id=episode_two.id)
    db.add_all([production_episode_one, production_episode_two])
    db.flush()
    run_one = VideoProductionRun(
        series_id=series.id,
        episode_id=episode_one.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode_one.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    run_two = VideoProductionRun(
        series_id=series.id,
        episode_id=episode_two.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode_two.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add_all([run_one, run_two])
    db.flush()
    db.add_all([
        ProductionJob(
            plan_id=plan.id,
            target_type="episode",
            target_id=episode_one.id,
            stage="image_generation",
            status="running",
            idempotency_key=f"{run_one.id}:image_generation",
        ),
        ProductionAuditEvent(
            event_type="episode.one.job.created",
            production_plan_id=plan.id,
            production_episode_id=production_episode_one.id,
            payload_json={"episode": 1},
        ),
    ])
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode_one.id]["production_status"] == "producing"
    assert matrix[episode_one.id]["active_job_count"] == 1
    assert matrix[episode_one.id]["audit_event_count"] == 1
    assert matrix[episode_two.id]["production_status"] == "blocked"
    assert matrix[episode_two.id]["active_job_count"] == 0
    assert matrix[episode_two.id]["audit_event_count"] == 0
    assert matrix[episode_two.id]["blocking_code"] == "RUNNING_WITHOUT_ACTIVE_JOB"


def test_completed_run_is_completed(db):
    series, episode = _series_with_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="completed",
        current_stage="completed",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "completed"
    assert matrix[episode.id]["active_run_id"] == run.id
    assert matrix[episode.id]["blocking_code"] is None


@pytest.mark.parametrize(
    ("run_status", "expected_production_status"),
    [
        ("image_approved", "ready_for_video"),
        ("video_segments_approved", "ready_for_compose"),
        ("draft", "ready_for_image"),
        ("storyboard_ready", "ready_for_image"),
    ],
)
def test_ready_gate_run_statuses_are_not_blocked(db, run_status, expected_production_status):
    series, episode = _series_with_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status=run_status,
        current_stage=run_status,
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == expected_production_status
    assert matrix[episode.id]["latest_run_status"] == run_status
    assert matrix[episode.id]["active_run_id"] == run.id
    assert matrix[episode.id]["blocking_code"] is None


@pytest.mark.parametrize(
    ("run_status", "blocking_code"),
    [
        ("failed", "RUN_FAILED"),
        ("blocked", "RUN_BLOCKED"),
        ("reference_generation_blocked", "REFERENCE_GENERATION_BLOCKED"),
        ("image_review_pending", "RUN_REQUIRES_REVIEW"),
        ("mystery_state", "RUN_STATE_UNCLASSIFIED"),
    ],
)
def test_non_active_existing_run_never_falls_back_to_ready_or_not_started(db, run_status, blocking_code):
    series, episode = _series_with_episode(db)
    db.add_all([
        AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_script",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"script": "approved"},
        ),
        AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="storyboard",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"frames": [{"frame_id": "f1"}]},
        ),
        VideoProductionRun(
            series_id=series.id,
            episode_id=episode.id,
            status=run_status,
            current_stage=run_status,
            run_type="real_short_e2e",
        ),
    ])
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "blocked"
    assert matrix[episode.id]["latest_run_status"] == run_status
    assert matrix[episode.id]["blocking_code"] == blocking_code


def test_final_review_pending_blocks_even_with_active_job(db):
    series, episode = _series_with_episode(db)
    plan = ProductionPlan(series_id=series.id, status="running")
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        status="final_review_pending",
        current_stage="final_review",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.flush()
    db.add(ProductionJob(
        plan_id=plan.id,
        target_type="episode",
        target_id=episode.id,
        stage="final_review",
        status="running",
        idempotency_key=f"{run.id}:final_review",
    ))
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "blocked"
    assert matrix[episode.id]["active_job_count"] == 1
    assert matrix[episode.id]["blocking_code"] == "RUN_REQUIRES_REVIEW"


def test_status_matrix_loads_evidence_in_batches(db):
    series = Series(title="Batch Status", logline="Batch", genre="drama", total_episodes=10)
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running")
    db.add(plan)
    db.flush()
    for index in range(10):
        episode = Episode(series_id=series.id, episode_number=index + 1, title=f"Episode {index + 1}")
        db.add(episode)
        db.flush()
        production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
        db.add(production_episode)
        db.flush()
        run = VideoProductionRun(
            series_id=series.id,
            episode_id=episode.id,
            production_plan_id=plan.id,
            production_episode_id=production_episode.id,
            status="running",
            current_stage="image_batch_running",
            run_type="real_short_e2e",
        )
        db.add(run)
        db.flush()
        db.add(ProductionJob(
            plan_id=plan.id,
            target_type="episode",
            target_id=episode.id,
            stage="image_generation",
            status="running",
            idempotency_key=f"{run.id}:image_generation",
        ))
    db.commit()

    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        matrix = build_episode_status_matrix(db, series.id)
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)

    assert len(matrix) == 10
    assert all(item["production_status"] == "producing" for item in matrix.values())
    assert len(statements) <= 8
