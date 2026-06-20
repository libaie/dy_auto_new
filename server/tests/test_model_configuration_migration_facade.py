import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-model-migration-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-model-migration-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/model_configuration/migration.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/migration.py"
README_PATH = REPO_ROOT / "server/app/domains/model_configuration/README.md"


def test_model_migration_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.migration",
        "app.services.migration",
        "migrate_legacy_settings",
        "_normalize_model_name",
        "_find_existing",
    ]:
        assert term in spec
        assert term in plan


def test_model_migration_implementation_lives_in_model_configuration_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def migrate_legacy_settings" in domain_text
    assert "def _normalize_model_name" in domain_text
    assert "def _find_existing" in domain_text
    assert "app.domains.system_configuration.crypto" in domain_text
    assert "app.services.crypto" not in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def migrate_legacy_settings" not in legacy_text


def test_legacy_model_migration_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.model_configuration.migration")
    legacy = importlib.import_module("app.services.migration")
    assert legacy is domain
    assert legacy.migrate_legacy_settings is domain.migrate_legacy_settings
    assert legacy._normalize_model_name is domain._normalize_model_name
    assert legacy._find_existing is domain._find_existing


def test_model_configuration_readme_registers_migration_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration.migration" in text
    assert "app.services.migration" in text
