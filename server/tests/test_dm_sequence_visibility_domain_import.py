import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-dm-sequence-visibility-domain-import-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-dm-sequence-visibility-domain-import-plan.md"
POLLING_PATH = REPO_ROOT / "server/app/domains/device_operations/polling.py"


def test_dm_sequence_visibility_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.dm_sequence_visibility",
        "app.services.dm_sequence_visibility",
        "device_operations.polling",
    ]:
        assert term in spec
        assert term in plan


def test_device_polling_imports_dm_sequence_visibility_from_domain_path():
    text = POLLING_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.dm_sequence_visibility" in text
    assert "app.services.dm_sequence_visibility" not in text


def test_legacy_dm_sequence_visibility_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.dm_sequence_visibility")
    domain = importlib.import_module("app.domains.content_collection.dm_sequence_visibility")
    assert legacy is domain
    assert legacy.get_device_visible_dm_sequences is domain.get_device_visible_dm_sequences
