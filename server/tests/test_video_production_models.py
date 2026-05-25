from app.db_models import (
    Episode,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)


def test_video_production_models_store_run_assets_and_reviews(db):
    series = Series(title="Stage Test", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()

    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_batch_running",
        current_stage="image_generation",
        storyboard_json={"frames": [{"frame_id": "frame-001"}]},
        model_trace_json={"image_generation": {"provider": "seedance"}},
    )
    db.add(run)
    db.flush()

    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/frame-001.png",
        version=1,
        status="review_pending",
        metadata_json={"width": 1080, "height": 1920},
    )
    db.add(asset)
    db.flush()

    review = VideoReviewRecord(
        asset_id=asset.id,
        run_id=run.id,
        review_type="ai",
        status="needs_human",
        score=0.42,
        issues_json=["identity mismatch"],
        model_trace_json={"provider": "audit-model"},
    )
    db.add(review)
    db.commit()

    saved = db.query(VideoProductionAsset).filter_by(frame_id="frame-001").one()
    assert saved.run_id == run.id
    assert saved.version == 1
    assert saved.status == "review_pending"
    assert db.query(VideoReviewRecord).filter_by(asset_id=saved.id).one().status == "needs_human"
