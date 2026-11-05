"""Script service tests."""
import pytest
import io
from pathlib import Path
from app.services.script_service import script_service
from tests.script_package_fixture import script_package


def test_get_version_returns_string():
    version = script_service.get_version()
    assert isinstance(version, str)
    assert len(version) > 0


def test_get_version_increments(tmp_path, monkeypatch):
    """Version increments when script zip is uploaded."""
    monkeypatch.setattr(script_service, "_script_dir", tmp_path / "scripts")
    monkeypatch.setattr(script_service, "_version_file", tmp_path / "version.txt")
    v1 = script_service.get_version()
    script_service.upload_script(io.BytesIO(script_package()))
    v2 = script_service.get_version()
    assert v2 != v1


def test_download_script_returns_bytes(tmp_path, monkeypatch):
    """After upload, download returns valid content."""
    monkeypatch.setattr(script_service, "_script_dir", tmp_path / "scripts")
    monkeypatch.setattr(script_service, "_version_file", tmp_path / "scripts" / "version.txt")
    content = script_package()
    script_service.upload_script(io.BytesIO(content))
    result = script_service.download_script()
    assert result is not None
    assert len(result) > 0
    assert result == content


def test_download_script_no_version_returns_none(tmp_path, monkeypatch):
    """When no script has been uploaded, download returns None."""
    svc = type(script_service)(tmp_path / "empty", tmp_path / "empty" / "version.txt")
    result = svc.download_script()
    assert result is None
