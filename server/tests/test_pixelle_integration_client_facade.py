import importlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-pixelle-client-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-pixelle-client-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_client.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/pixelle_client.py"
IMAGE_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_creation_router.py"
PIPELINE_ROUTER_PATH = REPO_ROOT / "server/app/domains/script_pipeline/pipeline_router.py"
README_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/README.md"


def test_pixelle_client_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.pixelle_integration.pixelle_client",
        "app.services.pixelle_client",
        "_pixelle_request",
        "close_client",
    ]:
        assert term in spec
        assert term in plan


def test_pixelle_client_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_pixelle_client_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "async def _pixelle_request" not in text
    assert "async def close_client" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_pixelle_client_module_is_domain_module():
    legacy = importlib.import_module("app.services.pixelle_client")
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_client")
    assert legacy is domain
    assert legacy._pixelle_request is domain._pixelle_request
    assert legacy._get_base_url is domain._get_base_url
    assert legacy.close_client is domain.close_client


def test_services_parent_package_pixelle_client_attribute_is_domain_module():
    from app.services import pixelle_client as parent_import

    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_client")
    assert parent_import is domain


def test_clean_domain_callers_import_domain_pixelle_client():
    for path in [IMAGE_ROUTER_PATH, PIPELINE_ROUTER_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.pixelle_integration.pixelle_client" in text
        assert "app.services.pixelle_client" not in text


def test_pixelle_integration_docs_register_pixelle_client_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.pixelle_integration.pixelle_client",
        "app.services.pixelle_client",
        "_pixelle_request",
        "approved compatibility imports",
    ]:
        assert term in readme


@pytest.mark.asyncio
async def test_pixelle_request_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.pixelle_client")
    legacy._base_url = ""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"ok": True})
    resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=resp)

    with patch("app.services.pixelle_client._get_client", return_value=mock_client):
        result = await legacy._pixelle_request("GET", "/health")

    assert result == {"ok": True}
    assert mock_client.request.call_count == 1
    legacy._base_url = ""


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
