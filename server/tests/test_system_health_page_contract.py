import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import AIModel, SystemSetting
from app.main import app


client = TestClient(app)


def test_system_health_exposes_migration_provider_and_smoke_status():
    response = client.get("/api/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] in {"ok", "warning", "blocked"}
    assert set(body) == {
        "ok",
        "status",
        "migration",
        "provider_capability",
        "latest_paid_smoke",
    }
    assert set(body["migration"]) == {
        "status",
        "missing_tables",
        "missing_columns",
        "repair_actions",
    }
    assert set(body["provider_capability"]) == {
        "status",
        "checked_model_count",
        "paid_ready_count",
        "paid_ready",
        "blocked_for_real_provider",
        "worker_runtime",
        "scene_readiness",
        "repair_actions",
    }
    assert set(body["provider_capability"]["worker_runtime"]) == {
        "status",
        "env",
        "value",
        "repair_actions",
    }
    assert set(body["provider_capability"]["scene_readiness"]) == {
        "image_generation",
        "video_rendering",
        "video_composition",
    }
    assert body["latest_paid_smoke"] is None


def test_system_health_ok_means_health_check_succeeded_when_status_blocked(monkeypatch):
    import app.domains.system_operations.system_health_router as system_health

    monkeypatch.setattr(system_health, "_migration_health", lambda db: {
        "status": "blocked",
        "missing_tables": ["provider_stage_tasks"],
        "missing_columns": [],
        "repair_actions": ["Run migrations."],
    })
    monkeypatch.setattr(system_health, "_provider_capability_health", lambda db: {
        "status": "warning",
        "blocked_for_real_provider": [],
    })

    response = client.get("/api/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "blocked"


def test_provider_capability_health_blocks_without_single_worker_env(db, monkeypatch):
    import app.domains.system_operations.system_health_router as system_health

    monkeypatch.delenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", raising=False)

    result = system_health._provider_capability_health(db)

    assert result["status"] == "blocked"
    assert result["worker_runtime"]["status"] == "blocked"
    assert result["worker_runtime"]["env"] == "DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT"
    assert result["repair_actions"]


def test_provider_capability_health_requires_paid_ready_model_per_runtime_scene(db, monkeypatch):
    import app.domains.system_operations.system_health_router as system_health

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    for scene_key in ("image_generation", "video_rendering"):
        db.add(AIModel(
            name=f"{scene_key}-model",
            model_type="video",
            provider="seedance",
            base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
            api_key="encrypted-placeholder",
            model_name=f"{scene_key}-model-name",
            config_json={
                "scene_key": scene_key,
                "real_paid_allowed": True,
                "supports_external_task_id": True,
                "supports_task_query": True,
                "returns_asset_url": True,
                "returns_usage": True,
                "estimated_cost": 0.01,
                "supports_text_to_image": scene_key == "image_generation",
                "supports_image_to_video": scene_key == "video_rendering",
            },
            enabled=True,
        ))
    db.commit()

    result = system_health._provider_capability_health(db)

    assert result["status"] == "blocked"
    assert result["worker_runtime"]["status"] == "ok"
    assert result["scene_readiness"]["image_generation"]["status"] == "ok"
    assert result["scene_readiness"]["video_rendering"]["status"] == "ok"
    assert result["scene_readiness"]["video_composition"]["status"] == "blocked"


def test_provider_capability_health_accepts_pixelle_settings_for_video_composition(db, monkeypatch):
    import app.domains.system_operations.system_health_router as system_health

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    db.add_all([
        SystemSetting(key="pixelle_video_url", value="http://pixelle:8500"),
        SystemSetting(key="pixelle_api_key", value="stage-secret"),
    ])
    for scene_key, capability_key in (
        ("image_generation", "supports_text_to_image"),
        ("video_rendering", "supports_image_to_video"),
        ("video_composition", "supports_video_composition"),
    ):
        db.add(AIModel(
            name=f"{scene_key}-model",
            model_type="video",
            provider="pixelle" if scene_key == "video_composition" else "seedance",
            base_url="   " if scene_key == "video_composition" else "https://ark.cn-beijing.volces.com/api/plan/v3",
            api_key="   " if scene_key == "video_composition" else "encrypted-placeholder",
            model_name=f"{scene_key}-model-name",
            config_json={
                "scene_key": scene_key,
                "real_paid_allowed": True,
                "supports_external_task_id": True,
                "supports_task_query": True,
                "returns_asset_url": True,
                "returns_usage": True,
                "estimated_cost": 0.01,
                capability_key: True,
            },
            enabled=True,
        ))
    db.commit()

    result = system_health._provider_capability_health(db)

    assert result["status"] == "ok"
    assert result["scene_readiness"]["video_composition"]["status"] == "ok"
    assert result["scene_readiness"]["video_composition"]["blocked"] == []

def _paid_capability(**overrides):
    capability = {
        "real_paid_allowed": True,
        "supports_external_task_id": True,
        "supports_task_query": True,
        "returns_asset_url": True,
        "returns_usage": True,
        "supports_video_composition": True,
    }
    capability.update(overrides)
    return capability


def test_provider_capability_health_treats_whitespace_connection_values_as_missing():
    import app.domains.system_operations.system_health_router as system_health

    model = AIModel(
        provider="pixelle",
        base_url="   ",
        api_key="   ",
        model_name="   ",
        config_json={"estimated_cost": 0.01},
    )

    missing = system_health._missing_real_provider_requirements(
        model,
        _paid_capability(),
        scene_key="video_composition",
        settings={"pixelle_video_url": "   ", "pixelle_api_key": "   "},
    )

    assert {"api_key", "base_url", "model_name"} <= set(missing)


def test_provider_capability_health_does_not_apply_pixelle_settings_to_other_providers():
    import app.domains.system_operations.system_health_router as system_health

    model = AIModel(
        provider="seedance",
        base_url="",
        api_key="",
        model_name="seedance-compose",
        config_json={"estimated_cost": 0.01},
    )

    missing = system_health._missing_real_provider_requirements(
        model,
        _paid_capability(),
        scene_key="video_composition",
        settings={"pixelle_video_url": "http://pixelle:8500", "pixelle_api_key": "stage-secret"},
    )

    assert "api_key" in missing
    assert "base_url" in missing

def test_system_health_reports_missing_required_boundary_column(monkeypatch):
    import app.domains.system_operations.system_health_router as system_health

    monkeypatch.setattr(
        system_health,
        "_required_schema",
        lambda: {"video_production_assets": ["definitely_missing_boundary_column"]},
    )

    response = client.get("/api/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["migration"]["status"] == "blocked"
    assert body["migration"]["missing_columns"] == [
        "video_production_assets.definitely_missing_boundary_column"
    ]


def test_provider_capability_health_handles_ai_model_query_failure():
    import app.domains.system_operations.system_health_router as system_health

    class BrokenDB:
        def query(self, *_args, **_kwargs):
            raise SQLAlchemyError("ai_models unavailable")

    result = system_health._provider_capability_health(BrokenDB())

    assert result["status"] == "blocked"
    assert result["checked_model_count"] == 0
    assert result["paid_ready_count"] == 0
    assert result["paid_ready"] == []
    assert result["blocked_for_real_provider"] == []
    assert result["repair_actions"] == [
        "Check ai_models table availability and migration state."
    ]
    assert "ai_models unavailable" in result["error"]


def test_provider_capability_ignores_malformed_config_json():
    import app.domains.system_operations.system_health_router as system_health

    capability = system_health._capability_for_model(
        SimpleNamespace(config_json="not-a-dict")
    )

    assert capability["real_paid_allowed"] is False
    assert capability["supports_external_task_id"] is False
    assert capability["supports_task_query"] is False
    assert capability["returns_asset_url"] is False
    assert capability["returns_usage"] is False


def test_real_provider_smoke_script_emits_dry_report_json():
    script = Path(__file__).resolve().parents[1] / "scripts" / "smoke_real_provider_video.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run-id",
            "test-run",
            "--max-duration",
            "5",
            "--budget-limit",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body == {
        "ok": True,
        "mode": "dry_report",
        "run_id": "test-run",
        "max_duration": 5,
        "budget_limit": 1.0,
        "provider_task_id": None,
        "asset_persistence": "not_run",
        "review_status": "not_run",
    }
