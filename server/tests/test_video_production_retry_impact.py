from fastapi.testclient import TestClient

from app.db.models import ProductionJob, ProductionSegment, VideoProductionAsset, VideoProductionRun
from app.main import app
from tests.video_production_control_plane_helpers import linked_segment_context


def test_retry_impact_returns_local_scope(db):
    ctx = linked_segment_context(db)
    segment = ctx["segment"]
    client = TestClient(app)

    resp = client.get(f"/api/video-production/segments/{segment.id}/retry-impact")

    assert resp.status_code == 200
    impact = resp.json()
    assert impact["allowed"] is True
    assert impact["target_new_version"] == segment.version + 1
    assert impact["old_latest_assets"][0]["version"] == 1


def test_retry_segment_endpoint_demotes_latest_asset_and_creates_new_version(db):
    ctx = linked_segment_context(db)
    segment = ctx["segment"]
    client = TestClient(app)

    resp = client.post(f"/api/video-production/segments/{segment.id}/retry")

    assert resp.status_code == 200
    body = resp.json()
    assert body["segment"]["version"] == 2

    db.expire_all()
    old_segment = db.query(ProductionSegment).filter_by(id=segment.id).one()
    new_segment = db.query(ProductionSegment).filter_by(id=body["segment"]["id"]).one()
    old_asset = db.query(VideoProductionAsset).filter_by(id=ctx["asset"].id).one()
    run = db.query(VideoProductionRun).filter_by(id=ctx["run"].id).one()
    job = db.query(ProductionJob).filter_by(target_id=new_segment.id, stage="image_generation").one()
    assert old_segment.status == "superseded"
    assert new_segment.status == "retry_queued"
    assert old_asset.is_latest is False
    assert job.status == "queued"
    assert run.status == "image_batch_running"
    assert run.current_stage == "image_generation"


def test_retry_superseded_segment_is_not_required_by_image_gate(db):
    from app.domains.video_production.production_gate_evaluator import evaluate_stage_gate

    ctx = linked_segment_context(db)
    segment = ctx["segment"]
    run = ctx["run"]
    client = TestClient(app)

    resp = client.post(f"/api/video-production/segments/{segment.id}/retry")
    new_segment_id = resp.json()["segment"]["id"]
    db.expire_all()
    new_segment = db.query(ProductionSegment).filter_by(id=new_segment_id).one()
    new_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=ctx["episode"].id,
        frame_id=new_segment.id,
        asset_type="image",
        stage="image_generation",
        production_segment_id=new_segment.id,
        production_shot_id=ctx["shot"].id,
        target_type="production_segment",
        target_id=new_segment.id,
        version=1,
        is_latest=True,
        source_version=new_segment.version,
        status="approved",
        copy_status="persisted",
        checksum="retry-image",
        storage_path="output/retry-image.png",
        url="output/retry-image.png",
    )
    db.add(new_asset)
    db.commit()

    gate = evaluate_stage_gate(db, run.id, stage="image_generation")

    assert gate["ready"] is True
    assert gate["approved_count"] == 1
    assert gate["blocked_segment_ids"] == []


def test_retry_superseded_segment_is_not_used_for_video_payload(db):
    from app.domains.video_production.video_production_service import build_image_stage_frames_for_segments

    ctx = linked_segment_context(db)
    segment = ctx["segment"]
    run = ctx["run"]
    client = TestClient(app)

    resp = client.post(f"/api/video-production/segments/{segment.id}/retry")
    new_segment_id = resp.json()["segment"]["id"]
    db.expire_all()

    frames = build_image_stage_frames_for_segments(db, run)

    assert [frame["production_segment_id"] for frame in frames] == [new_segment_id]
