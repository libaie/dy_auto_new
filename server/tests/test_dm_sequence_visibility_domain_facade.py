import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-dm-sequence-visibility-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-dm-sequence-visibility-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/content_collection/dm_sequence_visibility.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/dm_sequence_visibility.py"
MUTATIONS_PATH = REPO_ROOT / "server/app/domains/content_collection/mutations.py"
DEVICE_POLLING_PATH = REPO_ROOT / "server/app/domains/device_operations/polling.py"
README_PATH = REPO_ROOT / "server/app/domains/content_collection/README.md"


def test_dm_sequence_visibility_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.dm_sequence_visibility",
        "app.services.dm_sequence_visibility",
        "get_device_visible_dm_sequences",
    ]:
        assert term in spec
        assert term in plan


def test_dm_sequence_visibility_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_dm_sequence_visibility_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_device_visible_dm_sequences" not in text
    assert "Task.status.in_" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_dm_sequence_visibility_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.dm_sequence_visibility")
        domain = importlib.import_module("app.domains.content_collection.dm_sequence_visibility")
    except ModuleNotFoundError as exc:
        pytest.fail(f"dm sequence visibility domain import failed: {exc}")

    assert legacy is domain
    assert legacy.get_device_visible_dm_sequences is domain.get_device_visible_dm_sequences
    assert legacy._extract_sequence_id is domain._extract_sequence_id
    assert legacy._task_sequence_ids_for_device is domain._task_sequence_ids_for_device


def test_services_parent_package_dm_sequence_visibility_attribute_is_domain_module():
    from app.services import dm_sequence_visibility as parent_import

    domain = importlib.import_module("app.domains.content_collection.dm_sequence_visibility")

    assert parent_import is domain
    assert parent_import.get_device_visible_dm_sequences is domain.get_device_visible_dm_sequences


def test_content_collection_mutations_imports_domain_visibility_only():
    text = MUTATIONS_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection.dm_sequence_visibility" in text
    assert "app.services.dm_sequence_visibility" not in text


def test_device_polling_imports_domain_visibility_directly():
    text = DEVICE_POLLING_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection.dm_sequence_visibility" in text
    assert "app.services.dm_sequence_visibility" not in text


def test_content_collection_docs_register_dm_sequence_visibility_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.dm_sequence_visibility",
        "app.services.dm_sequence_visibility",
        "get_device_visible_dm_sequences",
        'rg -n "app\\.services\\.dm_sequence_visibility" server/app -g "*.py"',
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
