import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-selection-preview-hash-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-selection-preview-hash-domain-plan.md"
DOMAIN_HELPER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_selection_preview_hash.py"
LEGACY_HELPER_PATH = REPO_ROOT / "server/app/services/image_selection_preview_hash.py"
DOMAIN_SELECTION_PREVIEW_PATH = REPO_ROOT / "server/app/domains/image_generation/image_selection_preview_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_selection_preview_hash_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_selection_preview_hash",
        "app.services.image_selection_preview_hash",
        "selection_preview_hash_inputs",
        "selection_preview_request_hash",
    ]:
        assert term in spec
        assert term in plan


def test_image_selection_preview_hash_domain_file_exists():
    assert DOMAIN_HELPER_PATH.exists()


def test_legacy_image_selection_preview_hash_is_thin_facade():
    text = LEGACY_HELPER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def selection_preview_hash_inputs" not in text
    assert "def selection_preview_request_hash" not in text
    assert "json.dumps" not in text
    assert _line_count(LEGACY_HELPER_PATH) <= 20


def test_legacy_image_selection_preview_hash_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_selection_preview_hash")
        domain = importlib.import_module("app.domains.image_generation.image_selection_preview_hash")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image selection preview hash domain import failed: {exc}")

    assert legacy is domain
    assert legacy.selection_preview_hash_inputs is domain.selection_preview_hash_inputs
    assert legacy.selection_preview_request_hash is domain.selection_preview_request_hash


def test_selection_preview_imports_hash_domain_path():
    text = DOMAIN_SELECTION_PREVIEW_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_selection_preview_hash" in text
    assert "app.services.image_selection_preview_hash" not in text


def test_image_generation_readme_registers_selection_preview_hash_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_selection_preview_hash" in text
    assert "app.domains.image_generation.image_selection_preview_hash" in text
    assert 'rg "app\\.services\\.image_selection_preview_hash" server/app server/tests' in text
    assert "selection_preview_hash_inputs" in text
    assert "selection_preview_request_hash" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
