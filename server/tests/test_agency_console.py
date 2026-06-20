"""Agency Console transparency endpoint tests."""
import json

import pytest
from unittest.mock import AsyncMock
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient
from app.deps import verify_admin_token
from app.main import app
from app.db_models import AgencyCreativePatch, AgencyExpertInvocation, AIModel, Episode, Series, PipelineRun, VideoProductionRun
from app.services.agency_runtime import AgencyRuntimeResult
from app.services.agency_orchestrator import STAGE_DAG
from app.services.crypto import encrypt
from app.services.video_agency_team import build_video_agency_team


SOURCE = {
    "source_repo": "https://github.com/jnMetaCode/agency-agents-zh",
    "source_commit": "13b8800f6f666e8e10ac64f67f1194d2baeefbe0",
    "source_path": "specialized/prompt-engineer.md",
    "source_sha256": "a" * 64,
}


def _expert_review_model(db):
    model = AIModel(
        name="Agency Console Expert Review",
        model_type="llm",
        provider="openai-compatible",
        base_url="https://llm.test/v1",
        api_key=encrypt("expert-key"),
        model_name="expert-review-model",
        enabled=True,
        config_json={
            "scene_key": "llm_agency_expert_review",
            "protocol": "openai_chat_completions",
        },
    )
    db.add(model)
    db.commit()
    return model


async def _agency_pass(self, **kwargs):
    return AgencyRuntimeResult(
        result_status="passed",
        output_summary={
            "decision": f"{kwargs['stage']} passed",
            "findings": [],
            "recommendations": ["继续下一阶段"],
            "required_changes": [],
            "scorecard": {
                "overall_score": 95,
                "pass_threshold": 80,
                "verdict": "pass",
                "dimensions": [{"key": "quality", "score": 95, "threshold": 80}],
                "repair_intent": "none",
                "confidence": 0.9,
            },
        },
        evidence=[],
        token_usage={},
        model_config_snapshot={"provider": "test"},
    )


def _agency_invocation(db, series_id, **overrides):
    data = {
        "idempotency_key": f"console-{series_id}-{overrides.get('stage', 'storyboard')}-{overrides.get('expert_id', 'visual_storyteller')}",
        "series_id": series_id,
        "stage": "storyboard",
        "expert_id": "visual_storyteller",
        "role": "reviewer",
        "execution_status": "completed",
        "result_status": "passed",
        "input_summary_json": {"frame_count": 2},
        "output_summary_json": {"decision": "pass", "summary": "Ready for production."},
        "evidence_json": [{"message": "clear story"}],
        "duration_ms": 35,
        **SOURCE,
    }
    data.update(overrides)
    row = AgencyExpertInvocation(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_agency_console_returns_pending_steps_without_style_lock(db):
    client = TestClient(app)
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="pending"))
    db.commit()

    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["style_lock"]["locked"] is False
    assert data["agency_trace_status"] == "missing"
    assert len(data["expert_team"]) == 15
    assert "reality_checker" not in [item["expert_id"] for item in data["expert_team"]]
    stage_graph = data["stage_graph"]
    assert [node["stage"] for node in stage_graph] == list(STAGE_DAG)
    assert {node["stage"]: node["label"] for node in stage_graph} == {
        "story_planning": "故事规划",
        "style_lock": "\u98ce\u683c\u9501\u5b9a",
        "storyboard": "\u5206\u955c\u811a\u672c",
        "image_stage": "\u56fe\u50cf\u751f\u6210",
        "image_review": "图像审查",
        "video_stage": "\u89c6\u9891\u751f\u6210",
        "video_review": "视频审查",
        "compose_preflight": "合成预检",
        "compose": "\u5408\u6210\u4ea4\u4ed8",
    }
    for node in stage_graph:
        expected_stage = STAGE_DAG[node["stage"]]
        assert node["reviewers"] == expected_stage["reviewers"]
        assert node["lead"] == expected_stage["lead"]
        assert node["qa"] == expected_stage["qa"]
    assert data["expert_invocations"] == []
    assert data["decision_log"] == []
    assert data["agency_team_status"]["core_role_count"] == 7
    assert data["agency_team_status"]["support_role_count"] == 1
    assert data["agency_team_status"]["quality_role_count"] == 7
    agency_team_json = json.dumps(data["agency_team"], ensure_ascii=False)
    assert "Short Video Editing Coach" not in agency_team_json
    assert "Control pacing" not in agency_team_json
    assert "Keep every frame" not in agency_team_json
    assert len(data["agency_team"]["core_roles"]) == 7
    assert data["agency_team"]["core_roles"][0]["id"] == "story_generator"
    assert len(data["agency_team"]["support_roles"]) == 1
    assert data["agency_team"]["support_roles"][0]["id"] == "video_optimization_specialist"
    assert len(data["agency_team"]["quality_roles"]) == 7
    assert "compose_quality_reviewer" in [role["id"] for role in data["agency_team"]["quality_roles"]]
    assert data["production_steps"][0]["id"] == "input"
    assert any(step["id"] == "style_lock" and step["status"] == "pending" for step in data["production_steps"])


def test_agency_console_surfaces_style_lock_trace_error_in_decision_log(db):
    client = TestClient(app)
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "agency_trace": {
                    "stage_status": "completed",
                    "error_code": "STYLE_LOCK_REVIEW_TIMEOUT",
                    "error_message": "Style lock expert review exceeded 30 seconds.",
                },
            },
        },
    )
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="pending"))
    db.commit()

    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["agency_trace_status"] == "blocked"
    assert len(data["decision_log"]) == 1
    entry = data["decision_log"][0]
    assert entry["stage"] == "style_lock"
    assert entry["expert_id"] == "style_lock_quality_reviewer"
    assert entry["result_status"] == "blocked"
    assert "风格锁" in entry["decision"]
    assert entry["required_changes"] == ["检查外部视频服务状态后从失败层重试"]
    assert "STYLE_LOCK_REVIEW_TIMEOUT" in entry["evidence"]
    assert entry["next_action"] == "检查外部视频服务状态后从失败层重试"


def test_agency_console_includes_creative_patch_summary(db):
    client = TestClient(app)
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
    )
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    patch = AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="shot-001",
        title="强化前三秒",
        reason="钩子太弱。",
        before_json={"image_prompt": "原提示"},
        after_json={"image_prompt": "强钩子提示"},
        status="proposed",
        priority="high",
    )
    db.add(patch)
    db.commit()

    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["creative_patch_summary"]["total"] == 1
    assert data["creative_patch_summary"]["blocking"] == 1
    assert data["creative_patches"] == [{
        "id": patch.id,
        "stage": "storyboard",
        "expert_id": "prompt_engineer",
        "patch_type": "storyboard_patch",
        "target_type": "storyboard_frame",
        "target_id": "shot-001",
        "title": "强化前三秒",
        "status": "proposed",
        "priority": "high",
        "created_at": patch.created_at.isoformat(),
    }]


def test_agency_console_rejects_non_admin_role(db):
    client = TestClient(app)
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.commit()
    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        resp = client.get(f"/api/series/{series.id}/agency-console")
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_pipeline_layers_store_transparency_summaries(db, test_db, monkeypatch):
    from app.routers import pipeline

    TestSession = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    monkeypatch.setattr(pipeline, "SessionLocal", TestSession)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)
    _expert_review_model(db)

    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "agency_team": build_video_agency_team(),
                "visual_style": {"prompt": "cyber-noir"},
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        status="pending",
        storyboard_json={
            "frames": [{
                "narration": "Lin enters.",
                "image_prompt": "Lin in cyber-noir clinic.",
                "duration": 5,
                "audio_mode": "tts",
                "reference_urls": ["https://cdn.test/ref.png"],
            }]
        },
    )
    db.add(episode)
    db.flush()
    run = PipelineRun(series_id=series.id, episode_id=episode.id, mode="fully_automatic", status="running")
    db.add(run)
    db.commit()

    async def fake_pixelle_request(method, path, db=None, **kwargs):
        if path == "/api/image/generate":
            return {"images": ["https://cdn.test/generated.png"]}
        if path == "/api/content/narration":
            return {"narration": "Lin enters."}
        if path == "/api/content/title":
            return {"title": "Pilot"}
        if path == "/api/content/image-prompt":
            return {"image_prompt": "Lin in cyber-noir clinic."}
        if path == "/api/video/generate/async":
            return {"task_id": "task-1"}
        if path == "/api/video/task/task-1":
            return {"status": "completed", "progress": 100, "video_path": "frame.mp4", "duration": 5}
        if path == "/api/postproduction/execute":
            return {"video_path": "final.mp4", "duration": 5}
        raise AssertionError(path)

    monkeypatch.setattr(pipeline, "_pixelle_request", fake_pixelle_request)
    monkeypatch.setattr(pipeline.asyncio, "sleep", AsyncMock())

    await pipeline._run_all_layers(run.id)

    db.expire_all()
    saved = db.query(PipelineRun).filter(PipelineRun.id == run.id).one()
    layer_4 = saved.layers_json["4"]
    assert "agency_roles" in layer_4
    assert "quality_gates" in layer_4
    assert layer_4["status"] == "completed"
    assert layer_4["output_summary"]["video_path"] == "frame.mp4"


def test_agency_console_includes_latest_run_steps_and_video(db):
    from app.db_models import GeneratedVideo

    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "agency_team": build_video_agency_team(),
                "missing_assets": [],
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        status="done",
        video_url="final.mp4",
        storyboard_json={"frames": [{"duration": 5}], "total_duration": 5},
    )
    db.add(episode)
    db.flush()
    run = PipelineRun(
        series_id=series.id,
        episode_id=episode.id,
        status="completed",
        current_layer=5,
        layers_json={
            "5": {
                "status": "completed",
                "agency_roles": ["short_video_editing_coach"],
                "quality_gates": ["Final video is written back."],
                "input_summary": {"frame_count": 1},
                "output_summary": {"video_path": "final.mp4", "duration": 5},
                "result": {"video_path": "final.mp4", "duration": 5},
            }
        },
    )
    db.add(run)
    db.flush()
    db.add(GeneratedVideo(keyword=series.title, pixelle_task_id=run.id, video_path="final.mp4", status="completed"))
    db.commit()

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_run"]["id"] == run.id
    assert data["generated_video"]["video_path"] == "final.mp4"
    assert data["agency_trace_status"] == "legacy_summary"
    post = next(step for step in data["production_steps"] if step["id"] == "layer_5_postproduction")
    assert post["status"] == "completed"
    assert post["output_summary"]["video_path"] == "final.mp4"


def test_agency_console_includes_complete_invocation_trace(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    run = PipelineRun(series_id=series.id, episode_id=episode.id, status="completed")
    db.add(run)
    db.flush()
    invocation = _agency_invocation(db, series.id, pipeline_run_id=run.id)

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["agency_trace_status"] == "complete"
    assert data["expert_invocations"][0]["id"] == invocation.id
    assert data["decision_log"][0]["decision"] == "pass"
    storyboard = next(node for node in data["stage_graph"] if node["stage"] == "storyboard")
    assert storyboard["status"] == "completed"
    assert storyboard["invocation_ids"] == [invocation.id]


def test_agency_console_keeps_legacy_reality_checker_only_in_history(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    legacy = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-legacy-reality",
        stage="storyboard",
        expert_id="reality_checker",
        role="qa",
        output_summary_json={"decision": "legacy decision"},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert "reality_checker" not in [item["expert_id"] for item in data["expert_team"]]
    assert "reality_checker" not in [item["expert_id"] for item in data["expert_invocations"]]
    for node in data["stage_graph"]:
        assert "reality_checker" not in node["reviewers"]
        assert node["lead"] != "reality_checker"
        assert "reality_checker" not in node["qa"]
    assert legacy.id in [item["id"] for item in data["decision_log"]]
    log_item = next(item for item in data["decision_log"] if item["id"] == legacy.id)
    assert log_item["legacy"] is True
    assert log_item["display_scope"] == "historical_audit"


def test_agency_console_exposes_quality_reviewer_decision_evidence_and_next_action(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    invocation = _agency_invocation(
        db,
        series.id,
        stage="image_review",
        expert_id="image_review_quality_reviewer",
        role="qa",
        result_status="blocked",
        output_summary_json={
            "decision": "blocked",
            "findings": ["角色长相漂移"],
            "required_changes": ["重新生成角色参考图"],
            "next_action": "进入改图或重绘",
        },
        evidence_json=[{"frame_id": "shot-001", "reason": "face drift"}],
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    item = next(row for row in data["expert_invocations"] if row["id"] == invocation.id)
    assert item["decision"] == "blocked"
    assert item["findings"] == ["角色长相漂移"]
    assert item["required_changes"] == ["重新生成角色参考图"]
    assert item["evidence"] == ["shot-001: face drift"]
    assert item["next_action"] == "进入改图或重绘"
    log_item = next(row for row in data["decision_log"] if row["id"] == invocation.id)
    assert log_item["display_scope"] == "current_team"
    assert log_item["evidence"] == ["shot-001: face drift"]


def test_agency_console_maps_runtime_recommendations_to_next_action(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    invocation = _agency_invocation(
        db,
        series.id,
        stage="storyboard",
        expert_id="storyboard_quality_reviewer",
        role="qa",
        output_summary_json={
            "decision": "warn",
            "findings": [],
            "recommendations": ["补全下一段结束帧", "回到自动分镜修订"],
            "required_changes": [],
        },
        evidence_json=[],
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    item = next(row for row in data["expert_invocations"] if row["id"] == invocation.id)
    assert item["next_action"] == "补全下一段结束帧；回到自动分镜修订"
    log_item = next(row for row in data["decision_log"] if row["id"] == invocation.id)
    assert log_item["next_action"] == "补全下一段结束帧；回到自动分镜修订"


def test_agency_console_redacts_secret_values_from_user_facing_errors(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    _agency_invocation(
        db,
        series.id,
        stage="storyboard",
        expert_id="storyboard_quality_reviewer",
        role="qa",
        execution_status="failed",
        result_status="failed",
        error_code="EXPERT_MODEL_AUTH_FAILED",
        error_message="Authorization: Bearer secret-token",
        output_summary_json={"decision": "Authorization: Bearer secret-token"},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    text = resp.text
    assert "secret-token" not in text
    assert "Bearer" not in text
    assert "模型服务授权失败" in text or "专家审查失败" in text


def test_agency_console_uses_latest_video_production_run_invocations(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    pipeline_run = PipelineRun(series_id=series.id, episode_id=episode.id, status="completed")
    db.add(pipeline_run)
    db.flush()
    pipeline_invocation = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-pipeline",
        pipeline_run_id=pipeline_run.id,
        output_summary_json={"decision": "old pipeline decision"},
    )
    video_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="running",
        current_stage="image_stage",
    )
    db.add(video_run)
    db.flush()
    video_invocation = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-video",
        run_id=video_run.id,
        stage="image_stage",
        expert_id="image_prompt_engineer",
        role="lead",
        output_summary_json={"decision": "new video decision"},
    )
    db.commit()

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_run"]["type"] == "video_production"
    assert data["latest_run"]["id"] == video_run.id
    assert [item["id"] for item in data["expert_invocations"]] == [video_invocation.id]
    assert pipeline_invocation.id not in [item["id"] for item in data["expert_invocations"]]
    assert data["decision_log"][0]["decision"] == "new video decision"


def test_agency_console_keeps_current_front_stage_quality_invocations_with_latest_run(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    style_qa = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-style-qa-current",
        stage="style_lock",
        expert_id="style_lock_quality_reviewer",
        role="qa",
        output_summary_json={"decision": "style quality passed"},
    )
    storyboard_qa = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-storyboard-qa-current",
        stage="storyboard",
        expert_id="storyboard_quality_reviewer",
        role="qa",
        output_summary_json={"decision": "storyboard quality passed"},
    )
    series.story_bible_json = {
        "style_lock": {
            "locked": True,
            "version": 1,
            "agency_trace": {
                "stage": "style_lock",
                "stage_status": "complete",
                "invocation_ids": [style_qa.id],
            },
        }
    }
    episode.storyboard_json = {
        "frames": [{"frame_id": "frame-001", "duration": 5}],
        "agency_trace": {
            "stage": "storyboard",
            "stage_status": "complete",
            "invocation_ids": [storyboard_qa.id],
        },
    }
    video_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="running",
        current_stage="image_stage",
    )
    db.add(video_run)
    db.flush()
    video_invocation = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-video-stage-current",
        run_id=video_run.id,
        stage="image_stage",
        expert_id="image_prompt_engineer",
        role="lead",
        output_summary_json={"decision": "image stage passed"},
    )
    db.commit()

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    invocation_ids = [item["id"] for item in data["expert_invocations"]]
    assert style_qa.id in invocation_ids
    assert storyboard_qa.id in invocation_ids
    assert video_invocation.id in invocation_ids
    style_lock = next(node for node in data["stage_graph"] if node["stage"] == "style_lock")
    storyboard = next(node for node in data["stage_graph"] if node["stage"] == "storyboard")
    image_stage = next(node for node in data["stage_graph"] if node["stage"] == "image_stage")
    assert style_lock["invocation_ids"] == [style_qa.id]
    assert storyboard["invocation_ids"] == [storyboard_qa.id]
    assert image_stage["invocation_ids"] == [video_invocation.id]
    decision_log = {item["id"]: item["decision"] for item in data["decision_log"]}
    assert decision_log[style_qa.id] == "style quality passed"
    assert decision_log[storyboard_qa.id] == "storyboard quality passed"
    assert decision_log[video_invocation.id] == "image stage passed"


def test_agency_console_marks_failed_invocation_trace(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    _agency_invocation(
        db,
        series.id,
        execution_status="failed",
        result_status="failed",
        error_code="invalid_json",
        error_message="Invalid JSON",
        output_summary_json={},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["agency_trace_status"] == "failed"
    assert data["decision_log"][0]["decision"] == "Invalid JSON"
    storyboard = next(node for node in data["stage_graph"] if node["stage"] == "storyboard")
    assert storyboard["status"] == "failed"


def test_agency_console_hides_obsolete_and_duplicate_style_lock_invocations(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    obsolete = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-obsolete",
        stage="style_lock",
        expert_id="software_architect",
        role="lead",
        execution_status="failed",
        result_status="failed",
        error_code="EXPERT_MODEL_CONFIG_MISSING",
        output_summary_json={},
    )
    older_current = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-style-older",
        stage="style_lock",
        expert_id="image_prompt_engineer",
        role="reviewer",
        execution_status="failed",
        result_status="failed",
        error_code="EXPERT_MODEL_CONFIG_MISSING",
        output_summary_json={},
    )
    latest_current = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-style-latest",
        stage="style_lock",
        expert_id="image_prompt_engineer",
        role="reviewer",
        execution_status="completed",
        result_status="passed",
        output_summary_json={"decision": "latest style lock is usable"},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    invocation_ids = [item["id"] for item in data["expert_invocations"]]
    assert invocation_ids == [latest_current.id]
    assert obsolete.id not in invocation_ids
    assert older_current.id not in invocation_ids
    assert data["agency_trace_status"] == "complete"
    style_lock = next(node for node in data["stage_graph"] if node["stage"] == "style_lock")
    assert style_lock["invocation_ids"] == [latest_current.id]


def test_agency_console_prefers_current_style_lock_trace_over_stale_invocations(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 2,
                "agency_trace": {
                    "stage": "style_lock",
                    "stage_status": "blocked",
                    "invocation_ids": [],
                    "invocations": [],
                    "error_code": "EXPERT_MODEL_CONFIG_MISSING",
                    "error_message": "Agency expert runtime model requires api_key.",
                },
            }
        },
    )
    db.add(series)
    db.flush()
    stale = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-stale-style",
        stage="style_lock",
        expert_id="image_prompt_engineer",
        role="reviewer",
        execution_status="failed",
        result_status="failed",
        error_code="EXPERT_MODEL_CONFIG_MISSING",
        output_summary_json={},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["agency_trace_status"] == "blocked"
    assert data["expert_invocations"] == []
    style_lock = next(node for node in data["stage_graph"] if node["stage"] == "style_lock")
    assert style_lock["invocation_ids"] == []
    assert stale.id not in [item["id"] for item in data["expert_invocations"]]


def test_agency_console_marks_blocked_invocation_trace(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    _agency_invocation(
        db,
        series.id,
        result_status="blocked",
        output_summary_json={"decision": "Needs human repair"},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["agency_trace_status"] == "blocked"
    storyboard = next(node for node in data["stage_graph"] if node["stage"] == "storyboard")
    assert storyboard["status"] == "blocked"


def test_agency_console_marks_layer_only_blocked_trace(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    run = PipelineRun(
        series_id=series.id,
        episode_id=episode.id,
        status="blocked",
        layers_json={
            "1": {
                "status": "blocked",
                "agency_roles": ["narrative_designer"],
                "agency_trace": {
                    "stage": "storyboard",
                    "stage_status": "blocked",
                    "invocation_ids": [],
                    "error_code": "EXPERT_MODEL_CONFIG_MISSING",
                    "error_message": "missing expert model",
                },
            }
        },
    )
    db.add(run)
    db.commit()

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["agency_trace_status"] == "blocked"


@pytest.mark.asyncio
async def test_pipeline_failed_layer_gets_user_facing_recovery_summary(db, test_db, monkeypatch):
    from app.routers import pipeline

    TestSession = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    monkeypatch.setattr(pipeline, "SessionLocal", TestSession)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)
    _expert_review_model(db)

    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "agency_team": build_video_agency_team(),
                "visual_style": {"prompt": "cyber-noir"},
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        status="pending",
        storyboard_json={
            "frames": [{
                "narration": "Lin enters.",
                "image_prompt": "Lin in cyber-noir clinic.",
                "duration": 5,
                "audio_mode": "tts",
                "reference_urls": ["https://cdn.test/ref.png"],
            }]
        },
    )
    db.add(episode)
    db.flush()
    run = PipelineRun(series_id=series.id, episode_id=episode.id, mode="fully_automatic", status="running")
    db.add(run)
    db.commit()

    async def fake_pixelle_request(method, path, db=None, **kwargs):
        if path == "/api/image/generate":
            return {"images": ["https://cdn.test/generated.png"]}
        if path == "/api/content/narration":
            return {"narration": "Lin enters."}
        if path == "/api/content/title":
            return {"title": "Pilot"}
        if path == "/api/content/image-prompt":
            return {"image_prompt": "Lin in cyber-noir clinic."}
        if path == "/api/video/generate/async":
            raise RuntimeError("video provider timeout")
        raise AssertionError(path)

    monkeypatch.setattr(pipeline, "_pixelle_request", fake_pixelle_request)

    await pipeline._run_all_layers(run.id)

    db.expire_all()
    saved = db.query(PipelineRun).filter(PipelineRun.id == run.id).one()
    assert saved.status == "failed"
    assert "4" not in saved.layers_json or saved.layers_json.get("4", {}).get("status") != "completed"
