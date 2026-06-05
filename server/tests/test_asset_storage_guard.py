from pathlib import Path

import pytest

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.services.asset_storage_guard import persist_provider_asset
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError


def _asset(db, url="https://cdn.test/image.png"):
    series = Series(title="Storage", logline="Storage", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="image_review_pending", current_stage="image_review")
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-1",
        asset_type="image",
        stage="image_generation",
        url=url,
        source_url=url,
        status="generated",
        copy_status="registered",
    )
    db.add(asset)
    db.commit()
    return asset


def test_storage_guard_rejects_file_url(db, tmp_path):
    asset = _asset(db, url="file:///etc/passwd")

    with pytest.raises(ProductionRepairableError) as exc_info:
        persist_provider_asset(db, asset.id, output_root=tmp_path)

    assert exc_info.value.code == ProductionErrorCode.ASSET_STORAGE_FAILED
    db.refresh(asset)
    assert asset.copy_status == "storage_failed"
    assert asset.status == "storage_failed"


@pytest.mark.parametrize("url", ["https://localhost/private.png", "https://127.0.0.1/private.png"])
def test_storage_guard_rejects_local_host_urls(db, tmp_path, url):
    asset = _asset(db, url=url)

    with pytest.raises(ProductionRepairableError) as exc_info:
        persist_provider_asset(db, asset.id, output_root=tmp_path)

    assert exc_info.value.code == ProductionErrorCode.ASSET_STORAGE_FAILED
    db.refresh(asset)
    assert asset.copy_status == "storage_failed"
    assert asset.status == "storage_failed"


def test_storage_guard_persists_existing_pixelle_output_inside_root(db, tmp_path):
    source = tmp_path / "pixelle" / "image.png"
    source.parent.mkdir()
    source.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    asset = _asset(db, url="")
    asset.local_path = str(source)
    db.commit()

    persisted = persist_provider_asset(db, asset.id, output_root=tmp_path, pixelle_output_root=tmp_path / "pixelle")

    assert persisted.copy_status == "persisted"
    assert persisted.status == "review_pending"
    assert persisted.storage_path
    assert persisted.local_path
    assert persisted.url == persisted.storage_path
    assert persisted.checksum
    assert persisted.size_bytes == len(b"\x89PNG\r\n\x1a\nfake")
    assert Path(persisted.storage_path).exists()


def test_storage_guard_downloads_when_local_path_is_remote_url(db, tmp_path, monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"\xff\xd8\xfffake"

    captured = {}

    def fake_stream(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr("app.services.asset_storage_guard.httpx.stream", fake_stream)
    asset = _asset(db, url="https://cdn.test/provider-image.jpg")
    asset.local_path = "https://cdn.test/provider-image.jpg?X-Tos-Signature=test"
    db.commit()

    persisted = persist_provider_asset(db, asset.id, output_root=tmp_path, pixelle_output_root=tmp_path / "pixelle")

    assert captured["url"] == "https://cdn.test/provider-image.jpg"
    assert persisted.copy_status == "persisted"
    assert persisted.status == "review_pending"
    assert Path(persisted.storage_path).exists()


def test_storage_guard_rejects_pixelle_path_outside_root(db, tmp_path):
    outside = tmp_path.parent / "outside-image.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    asset = _asset(db, url="")
    asset.local_path = str(outside)
    db.commit()

    with pytest.raises(ProductionRepairableError) as exc_info:
        persist_provider_asset(db, asset.id, output_root=tmp_path, pixelle_output_root=tmp_path / "pixelle")

    assert exc_info.value.code == ProductionErrorCode.ASSET_STORAGE_FAILED
    db.refresh(asset)
    assert asset.copy_status == "storage_failed"
    assert asset.status == "storage_failed"
