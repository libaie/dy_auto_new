import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-crypto-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-crypto-domain-plan.md"
DOMAIN_CRYPTO_PATH = REPO_ROOT / "server/app/domains/system_configuration/crypto.py"
LEGACY_CRYPTO_PATH = REPO_ROOT / "server/app/services/crypto.py"
README_PATH = REPO_ROOT / "server/app/domains/system_configuration/README.md"
DOMAIN_IMPORT_PATHS = [
    REPO_ROOT / "server/app/domains/model_configuration/ai_models_router.py",
    REPO_ROOT / "server/app/domains/model_configuration/model_registry.py",
    REPO_ROOT / "server/app/domains/model_configuration/runtime_model_config.py",
    REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_router.py",
    REPO_ROOT / "server/app/domains/quality_audit/audit_router.py",
]


def test_crypto_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.system_configuration.crypto",
        "app.services.crypto",
        "encrypt",
        "decrypt",
        "SENSITIVE_KEYS",
    ]:
        assert term in spec
        assert term in plan


def test_crypto_implementation_lives_in_system_configuration_domain():
    domain_text = DOMAIN_CRYPTO_PATH.read_text(encoding="utf-8")
    assert "def encrypt" in domain_text
    assert "def decrypt" in domain_text
    assert "SENSITIVE_KEYS" in domain_text

    legacy_text = LEGACY_CRYPTO_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_configuration" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def encrypt" not in legacy_text
    assert "SENSITIVE_KEYS" not in legacy_text


def test_legacy_crypto_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.system_configuration.crypto")
    legacy = importlib.import_module("app.services.crypto")
    assert legacy is domain
    assert legacy.encrypt is domain.encrypt
    assert legacy.decrypt is domain.decrypt
    token = legacy.encrypt("secret-value")
    assert legacy.decrypt(token) == "secret-value"


def test_domain_modules_import_crypto_from_domain_path():
    for path in DOMAIN_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.system_configuration.crypto" in text
        assert "app.services.crypto" not in text


def test_system_configuration_readme_registers_crypto_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_configuration.crypto" in text
    assert "app.services.crypto" in text
