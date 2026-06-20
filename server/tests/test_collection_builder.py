from fastapi.testclient import TestClient

from app.db.models import Episode, Series, VideoCollection
from app.main import app
from app.domains.video_production.production_collection_service import create_collection_from_approved_episodes


client = TestClient(app)


def _series_with_episodes(db):
    series = Series(title="Collection Show", logline="Collection", genre="drama")
    db.add(series)
    db.flush()
    done_later = Episode(
        series_id=series.id,
        episode_number=3,
        status="done",
        video_url="https://cdn.test/ep3.mp4",
        duration_seconds=45,
    )
    pending = Episode(
        series_id=series.id,
        episode_number=2,
        status="pending",
        video_url="https://cdn.test/pending.mp4",
        duration_seconds=30,
    )
    blank_url = Episode(
        series_id=series.id,
        episode_number=4,
        status="done",
        video_url="  ",
        duration_seconds=20,
    )
    done = Episode(
        series_id=series.id,
        episode_number=1,
        status="done",
        video_url="https://cdn.test/ep1.mp4",
        duration_seconds=60,
    )
    db.add_all([done_later, pending, blank_url, done])
    db.commit()
    return series, done, pending, done_later


def test_collection_includes_only_done_episodes(db):
    series, done, _pending, done_later = _series_with_episodes(db)

    collection = create_collection_from_approved_episodes(db, series.id)

    assert collection.series_id == series.id
    assert collection.included_episode_ids == [done.id, done_later.id]
    assert collection.status == "draft"
    assert collection.duration_seconds == 105
    assert db.query(VideoCollection).count() == 1


def test_collection_rejects_missing_series(db):
    try:
        create_collection_from_approved_episodes(db, "missing-series")
    except ValueError as exc:
        assert "Series not found" in str(exc)
    else:
        raise AssertionError("Expected missing series error")


def test_collection_rejects_empty_deliverable_episode_set(db):
    series = Series(title="Empty Collection", logline="No videos", genre="drama")
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="pending", duration_seconds=30))
    db.commit()

    try:
        create_collection_from_approved_episodes(db, series.id)
    except ValueError as exc:
        assert "没有可打包剧集" in str(exc)
    else:
        raise AssertionError("Expected empty collection error")

    assert db.query(VideoCollection).count() == 0


def test_collection_endpoint_returns_collection_payload(db):
    series, done, _pending, done_later = _series_with_episodes(db)

    resp = client.post("/api/video-production/collections", json={"series_id": series.id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["collection"]["series_id"] == series.id
    assert body["collection"]["status"] == "draft"
    assert body["collection"]["included_episode_ids"] == [done.id, done_later.id]
    assert body["collection"]["duration_seconds"] == 105
    assert body["collection"]["video_url"] is None


def test_collection_endpoint_returns_400_for_missing_series(db):
    resp = client.post("/api/video-production/collections", json={"series_id": "missing-series"})

    assert resp.status_code == 400


def test_collection_endpoint_rejects_empty_collection(db):
    series = Series(title="Empty Collection", logline="No videos", genre="drama")
    db.add(series)
    db.commit()

    resp = client.post("/api/video-production/collections", json={"series_id": series.id})

    assert resp.status_code == 400
    assert "没有可打包剧集" in resp.json()["detail"]
