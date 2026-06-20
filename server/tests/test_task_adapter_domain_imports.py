import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-task-adapter-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-task-adapter-domain-imports-plan.md"
ADAPTERS_PATH = REPO_ROOT / "server/app/domains/task_operations/adapters.py"


def test_task_adapter_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.account_operations.channel_service",
        "app.domains.content_collection.content_service",
        "app.services.channel_service",
        "app.services.content_service",
        "app.services.task_service",
    ]:
        assert term in spec
        assert term in plan


def test_task_adapters_import_moved_helpers_from_domain_paths():
    text = ADAPTERS_PATH.read_text(encoding="utf-8")
    assert "app.domains.account_operations.channel_service" in text
    assert "app.domains.content_collection.content_service" in text
    assert "app.services.channel_service" not in text
    assert "app.services.content_service" not in text
    assert "app.services.task_service" in text


def test_legacy_channel_and_content_facades_resolve_to_domain_modules():
    channel_legacy = importlib.import_module("app.services.channel_service")
    channel_domain = importlib.import_module("app.domains.account_operations.channel_service")
    content_legacy = importlib.import_module("app.services.content_service")
    content_domain = importlib.import_module("app.domains.content_collection.content_service")
    assert channel_legacy is channel_domain
    assert channel_legacy.channel_service is channel_domain.channel_service
    assert content_legacy is content_domain
    assert content_legacy.content_service is content_domain.content_service
