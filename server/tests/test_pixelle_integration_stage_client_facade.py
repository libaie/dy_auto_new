import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-pixelle-stage-client-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-pixelle-stage-client-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_stage_client.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/pixelle_stage_client.py"
README_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/README.md"


def test_pixelle_stage_client_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.pixelle_integration.pixelle_stage_client",
        "app.services.pixelle_stage_client",
        "submit_image_batch",
        "submit_compose",
    ]:
        assert term in spec
        assert term in plan


def test_pixelle_stage_client_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_pixelle_stage_client_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "async def submit_image_batch" not in text
    assert "async def submit_compose" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_pixelle_stage_client_module_is_domain_module():
    legacy = importlib.import_module("app.services.pixelle_stage_client")
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_stage_client")
    assert legacy is domain
    assert legacy.submit_image_batch is domain.submit_image_batch
    assert legacy.submit_compose is domain.submit_compose


def test_services_parent_package_pixelle_stage_client_attribute_is_domain_module():
    from app.services import pixelle_stage_client as parent_import

    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_stage_client")
    assert parent_import is domain


def test_domain_stage_client_imports_domain_pixelle_client():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration.pixelle_client" in text
    assert "app.services.pixelle_client" not in text


def test_pixelle_integration_docs_register_pixelle_stage_client_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "pixelle_stage_client.py",
        "app.services.pixelle_stage_client",
        "submit_image_batch",
        "approved compatibility imports",
    ]:
        assert term in readme


@pytest.mark.asyncio
async def test_stage_client_stays_legacy_monkeypatch_compatible(monkeypatch):
    legacy = importlib.import_module("app.services.pixelle_stage_client")
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-1"}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await legacy.submit_image_batch(
        db=None,
        run_id="run-1",
        episode_id="episode-1",
        frames=[{"frame_id": "frame-1"}],
        model_config={"provider": "mock"},
    )

    assert result["stage_task_id"] == "stage-1"
    assert calls == [
        (
            "POST",
            "/api/stages/images/batch",
            {
                "external_run_id": "run-1",
                "episode_id": "episode-1",
                "frames": [{"frame_id": "frame-1"}],
                "model_config": {"provider": "mock"},
                "template_config": {},
            },
        )
    ]


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
