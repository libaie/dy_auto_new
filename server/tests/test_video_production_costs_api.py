from fastapi.testclient import TestClient

from app.main import app
from tests.video_production_control_plane_helpers import linked_segment_context


def test_run_costs_returns_known_or_unknown_estimate(db):
    ctx = linked_segment_context(db)
    run = ctx["run"]
    client = TestClient(app)

    resp = client.get(f"/api/video-production/runs/{run.id}/costs")

    assert resp.status_code == 200
    costs = resp.json()
    assert costs["actual_cost"] >= 0.02
    assert costs["estimate_status"] in {"known", "unknown"}
    assert costs["by_stage"][0]["stage"] == "image_generation"
