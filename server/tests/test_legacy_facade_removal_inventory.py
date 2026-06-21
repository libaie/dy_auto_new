import importlib
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = REPO_ROOT / "server"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def test_legacy_facade_files_are_removed():
    assert not (REPO_ROOT / "server/app/services").exists()
    assert not (REPO_ROOT / "server/app/routers").exists()
    assert not (REPO_ROOT / "server/app/db_models.py").exists()


def test_legacy_facade_modules_are_not_importable():
    importlib.invalidate_caches()

    assert importlib.util.find_spec("app.services") is None
    assert importlib.util.find_spec("app.routers") is None
    assert importlib.util.find_spec("app.db_models") is None
