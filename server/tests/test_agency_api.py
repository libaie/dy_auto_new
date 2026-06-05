from fastapi.testclient import TestClient

from app.deps import verify_admin_token
from app.db_models import AgencyExpertInvocation, Episode, PipelineRun, Series, VideoProductionRun
from app.main import app


client = TestClient(app)

SOURCE = {
    "source_repo": "https://github.com/jnMetaCode/agency-agents-zh",
    "source_commit": "13b8800f6f666e8e10ac64f67f1194d2baeefbe0",
    "source_path": "specialized/prompt-engineer.md",
    "source_sha256": "a" * 64,
}


def _series(db):
    series = Series(title="City Healer", logline="A doctor solves urban mysteries.", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    return series, episode


def _invocation(db, series_id, **overrides):
    data = {
        "idempotency_key": f"agency-test-{series_id}-{overrides.get('expert_id', 'prompt_engineer')}",
        "series_id": series_id,
        "stage": "storyboard",
        "expert_id": "prompt_engineer",
        "role": "reviewer",
        "execution_status": "completed",
        "result_status": "passed",
        "input_summary_json": {"frame_count": 3},
        "output_summary_json": {"decision": "pass", "summary": "Storyboard is usable."},
        "evidence_json": [{"message": "clear arc"}],
        "model_config_snapshot_json": {"model": "test-model"},
        "token_usage_json": {"total_tokens": 123},
        "duration_ms": 42,
        **SOURCE,
    }
    data.update(overrides)
    row = AgencyExpertInvocation(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_list_agency_experts_returns_metadata_only():
    response = client.get("/api/agency/experts")

    assert response.status_code == 200
    data = response.json()
    assert len(data["experts"]) == 14
    assert "reality_checker" not in [expert["expert_id"] for expert in data["experts"]]
    assert "markdown" not in data["experts"][0]
    assert data["experts"][0]["source_commit"] == "13b8800f6f666e8e10ac64f67f1194d2baeefbe0"


def test_get_expert_detail_returns_markdown_text():
    response = client.get("/api/agency/experts/prompt_engineer")

    assert response.status_code == 200
    data = response.json()
    assert data["expert_id"] == "prompt_engineer"
    assert data["legacy"] is False
    assert data["source_path"] == "specialized/prompt-engineer.md"
    assert len(data["markdown"]) > 500


def test_get_legacy_reality_checker_expert_returns_read_only_payload():
    response = client.get("/api/agency/experts/reality_checker")

    assert response.status_code == 200
    data = response.json()
    assert data["expert_id"] == "reality_checker"
    assert data["name"] == "历史审计角色"
    assert data["role_type"] == "legacy"
    assert data["legacy"] is True
    assert data["phases"] == []
    assert "历史审计记录" in data["markdown"]
    assert "不参与当前编排" in data["markdown"]


def test_get_unknown_expert_still_returns_404():
    response = client.get("/api/agency/experts/unknown_quality_reviewer")

    assert response.status_code == 404
    assert "unknown" in response.json()["detail"].lower()


def test_invalid_expert_path_is_rejected():
    response = client.get("/api/agency/experts/..%2Fdb_models.py")

    assert response.status_code in {400, 404}


def test_list_invocations_filters_and_paginates(db):
    series, episode = _series(db)
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="running")
    db.add(run)
    db.flush()
    first = _invocation(db, series.id, run_id=run.id, stage="storyboard", result_status="passed")
    _invocation(
        db,
        series.id,
        idempotency_key=f"agency-test-{series.id}-image",
        run_id=run.id,
        stage="image_stage",
        expert_id="image_prompt_engineer",
        result_status="warn",
    )

    response = client.get(
        "/api/agency/invocations",
        params={"series_id": series.id, "run_id": run.id, "stage": "storyboard", "status": "passed", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["items"][0] == {
        "id": first.id,
        "stage": "storyboard",
        "expert_id": "prompt_engineer",
        "role": "reviewer",
        "execution_status": "completed",
        "result_status": "passed",
        "summary": "pass",
        "duration_ms": 42,
        "error_code": None,
    }


def test_list_invocations_filters_by_pipeline_run_id(db):
    series, episode = _series(db)
    run = PipelineRun(series_id=series.id, episode_id=episode.id, status="running")
    db.add(run)
    db.flush()
    row = _invocation(db, series.id, pipeline_run_id=run.id)

    response = client.get("/api/agency/invocations", params={"run_id": run.id})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == row.id


def test_list_invocations_rejects_non_admin_role(db):
    series, _episode = _series(db)
    _invocation(db, series.id)
    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        response = client.get("/api/agency/invocations")
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert response.status_code == 403


def test_get_invocation_detail_uses_public_field_names(db):
    series, _episode = _series(db)
    row = _invocation(db, series.id)

    response = client.get(f"/api/agency/invocations/{row.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == row.id
    assert data["input_summary"] == {"frame_count": 3}
    assert data["output_summary"]["decision"] == "pass"
    assert data["evidence"] == [{"message": "clear arc"}]
    assert data["model_config_snapshot"] == {"model": "test-model"}
    assert data["token_usage"] == {"total_tokens": 123}
    assert "input_summary_json" not in data
    assert "output_summary_json" not in data


def test_get_invocation_detail_rejects_non_admin_role(db):
    series, _episode = _series(db)
    row = _invocation(db, series.id)
    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        response = client.get(f"/api/agency/invocations/{row.id}")
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert response.status_code == 403


def test_get_invocation_detail_redacts_model_config_snapshot(db):
    series, _episode = _series(db)
    row = _invocation(
        db,
        series.id,
        model_config_snapshot_json={
            "model": "test-model",
            "api_key": "secret",
            "nested": {"authorization": "Bearer x"},
        },
    )

    response = client.get(f"/api/agency/invocations/{row.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["model_config_snapshot"] == {
        "model": "test-model",
        "api_key": "[REDACTED]",
        "nested": {"authorization": "[REDACTED]"},
    }


def test_get_invocation_detail_redacts_provider_secret_values(db):
    series, _episode = _series(db)
    row = _invocation(
        db,
        series.id,
        expert_id="storyboard_quality_reviewer",
        role="qa",
        execution_status="failed",
        result_status="failed",
        output_summary_json={"decision": "blocked"},
        model_config_snapshot_json={
            "api_key": "ark-secret-value",
            "headers": {"Authorization": "Bearer secret-token"},
            "provider_payload": {"prompt": "safe summary only"},
        },
        error_message="Provider authorization failed",
    )

    response = client.get(f"/api/agency/invocations/{row.id}")

    assert response.status_code == 200
    text = response.text
    assert "ark-secret-value" not in text
    assert "secret-token" not in text
    assert "Bearer" not in text
    assert response.json()["model_config_snapshot"]["api_key"] == "[REDACTED]"
