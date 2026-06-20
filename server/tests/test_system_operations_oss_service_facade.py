import asyncio
import importlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-oss-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-oss-service-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/system_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/system_operations/oss_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/oss_service.py"


def test_oss_service_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.system_operations.oss_service",
        "app.services.oss_service",
        "upload_to_oss",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_operations.oss_service" in readme
    assert "app.services.oss_service" in readme
    assert "upload_to_oss" in readme


def test_oss_service_domain_file_owns_upload_helper():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "async def upload_to_oss" in text
    assert "provider == \"local\"" in text


def test_legacy_oss_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_operations import oss_service" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "async def upload_to_oss" not in text
    assert "boto3.client" not in text
    assert "oss2.Bucket" not in text


def test_legacy_oss_service_module_is_domain_module():
    for name in ("app.services.oss_service", "app.domains.system_operations.oss_service"):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.oss_service")
    domain = importlib.import_module("app.domains.system_operations.oss_service")

    assert legacy is domain
    assert legacy.upload_to_oss is domain.upload_to_oss


def test_oss_service_local_provider_returns_file_url(tmp_path):
    local_file = tmp_path / "asset.png"
    local_file.write_bytes(b"asset")

    domain = importlib.import_module("app.domains.system_operations.oss_service")
    result = asyncio.run(domain.upload_to_oss(str(local_file), provider="local"))

    assert result == f"file://{local_file.resolve()}"


def test_oss_service_missing_file_raises_file_not_found(tmp_path):
    domain = importlib.import_module("app.domains.system_operations.oss_service")

    with pytest.raises(FileNotFoundError):
        asyncio.run(domain.upload_to_oss(str(tmp_path / "missing.png"), provider="local"))
