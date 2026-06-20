import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-quality-audit-gate-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-quality-audit-gate-domain-plan.md"
DOMAIN_GATE_PATH = REPO_ROOT / "server/app/domains/quality_audit/audit_gate.py"
LEGACY_GATE_PATH = REPO_ROOT / "server/app/services/audit_gate.py"
AUDIT_ROUTER_PATH = REPO_ROOT / "server/app/domains/quality_audit/audit_router.py"
README_PATH = REPO_ROOT / "server/app/domains/quality_audit/README.md"
QUALITY_AUDIT_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-quality-audit-domain-design.md"


def test_quality_audit_gate_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.quality_audit.audit_gate",
        "app.services.audit_gate",
        "classify_audit_gate",
        "approve_threshold",
    ]:
        assert term in spec
        assert term in plan


def test_quality_audit_gate_domain_file_exists():
    assert DOMAIN_GATE_PATH.exists()


def test_legacy_quality_audit_gate_is_thin_facade():
    text = LEGACY_GATE_PATH.read_text(encoding="utf-8")

    assert "app.domains.quality_audit" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def classify_audit_gate" not in text
    assert _line_count(LEGACY_GATE_PATH) <= 20


def test_legacy_quality_audit_gate_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.audit_gate")
        domain = importlib.import_module("app.domains.quality_audit.audit_gate")
    except ModuleNotFoundError as exc:
        pytest.fail(f"quality audit gate domain import failed: {exc}")

    assert legacy is domain
    assert legacy.classify_audit_gate is domain.classify_audit_gate


def test_quality_audit_router_imports_domain_gate():
    text = AUDIT_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.quality_audit.audit_gate" in text
    assert "app.services.audit_gate" not in text


def test_quality_audit_docs_register_gate_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    design = QUALITY_AUDIT_SPEC_PATH.read_text(encoding="utf-8")

    for text in [readme, design]:
        assert "app.domains.quality_audit.audit_gate" in text
        assert "classify_audit_gate" in text
        assert "app.services.audit_gate" in text

    assert 'rg "app\\.services\\.audit_gate" server/app server/tests' in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
