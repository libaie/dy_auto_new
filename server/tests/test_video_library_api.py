from fastapi.testclient import TestClient
import pytest

from app.database import get_db
from app.db.models import GeneratedVideo
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    session.rollback()
    gen.close()


def test_list_videos_filters_by_keyword_and_status(client, db):
    _create_video(db, "video-lib-1", keyword="cat", status="completed", title="Cat")
    _create_video(db, "video-lib-2", keyword="cat", status="failed", title="Cat Failed")
    _create_video(db, "video-lib-3", keyword="dog", status="completed", title="Dog")

    response = client.get("/api/videos", params={"keyword": "cat", "status": "completed"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "video-lib-1"
    assert payload["items"][0]["keyword"] == "cat"
    assert payload["items"][0]["status"] == "completed"


def test_get_video_returns_404_for_missing_video(client):
    response = client.get("/api/videos/missing-video")

    assert response.status_code == 404
    assert response.json()["detail"] == "视频不存在"


def test_download_video_requires_admin_token_or_query_token(client, db, tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"video")
    _create_video(db, "video-lib-download", video_path=str(path), status="completed")

    response = client.get("/api/videos/video-lib-download/download")

    assert response.status_code == 401
    assert response.json()["detail"] == "请先登录"


def test_delete_video_removes_database_row_and_local_file(client, db, tmp_path):
    path = tmp_path / "delete-me.mp4"
    path.write_bytes(b"video")
    _create_video(db, "video-lib-delete", video_path=str(path), status="completed")

    response = client.delete("/api/videos/video-lib-delete")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "id": "video-lib-delete"}
    assert db.query(GeneratedVideo).filter(GeneratedVideo.id == "video-lib-delete").first() is None
    assert not path.exists()


def _create_video(
    db,
    video_id,
    *,
    keyword="keyword",
    title="Title",
    status="pending",
    video_path=None,
):
    video = GeneratedVideo(
        id=video_id,
        keyword=keyword,
        title=title,
        status=status,
        video_path=video_path,
    )
    db.add(video)
    db.commit()
    return video
