from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_legacy_facade_files_are_removed():
    assert not (REPO_ROOT / "server/app/services").exists()
    assert not (REPO_ROOT / "server/app/routers").exists()
    assert not (REPO_ROOT / "server/app/db_models.py").exists()
