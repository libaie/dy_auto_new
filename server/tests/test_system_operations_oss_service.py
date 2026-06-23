import pytest

from app.domains.system_operations.oss_service import upload_to_oss


@pytest.mark.asyncio
async def test_upload_to_oss_local_provider_returns_file_url(tmp_path):
    asset = tmp_path / "asset.mp4"
    asset.write_text("video", encoding="utf-8")

    url = await upload_to_oss(str(asset), provider="local")

    assert url == f"file://{asset.resolve()}"


@pytest.mark.asyncio
async def test_upload_to_oss_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        await upload_to_oss(str(tmp_path / "missing.mp4"), provider="local")
