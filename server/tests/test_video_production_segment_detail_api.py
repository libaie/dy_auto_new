from fastapi.testclient import TestClient

from app.main import app
from tests.video_production_control_plane_helpers import linked_segment_context


def test_segment_detail_returns_latest_assets_and_actions(db):
    ctx = linked_segment_context(db)
    segment = ctx["segment"]
    client = TestClient(app)

    resp = client.get(f"/api/video-production/segments/{segment.id}/detail")

    assert resp.status_code == 200
    detail = resp.json()
    assert detail["segment"]["id"] == segment.id
    assert detail["latest_assets"]["image"]["is_latest"] is True
    assert detail["latest_assets"]["image"]["source_version"] == segment.version
    assert "retry" in detail["allowed_actions"]
