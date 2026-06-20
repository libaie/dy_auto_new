import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-pixelle-execution-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-pixelle-execution-service-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_execution_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/pixelle_execution_service.py"


def test_pixelle_execution_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.pixelle_integration.pixelle_execution_service",
        "app.services.pixelle_execution_service",
        "build_video_stage_frame",
        "input_image_url",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "pixelle_execution_service.py" in readme
    assert "app.domains.pixelle_integration.pixelle_execution_service" in readme
    assert "app.services.pixelle_execution_service" in readme


def test_pixelle_execution_domain_file_owns_payload_mapper():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def build_video_stage_frame" in text
    assert '"input_image_url"' in text
    assert "app.domains.video_production.production_status" in text
    assert "app.services.production_status" not in text


def test_legacy_pixelle_execution_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration import pixelle_execution_service" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def build_video_stage_frame" not in text
    assert "reference_roles_json" not in text


def test_legacy_pixelle_execution_service_module_is_domain_module():
    for name in (
        "app.services.pixelle_execution_service",
        "app.domains.pixelle_integration.pixelle_execution_service",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.pixelle_execution_service")
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_execution_service")

    assert legacy is domain
    assert legacy.build_video_stage_frame is domain.build_video_stage_frame


def test_pixelle_execution_frame_keeps_input_image_url_behavior():
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_execution_service")

    frame = domain.build_video_stage_frame(
        {
            "id": "segment-id",
            "continuity_mode": "narrative_cut",
            "input_image_url": "https://cdn.test/input.png",
        },
        approved_image_url="https://cdn.test/approved.png",
    )

    assert frame["approved_image_url"] == "https://cdn.test/approved.png"
    assert frame["input_image_url"] == "https://cdn.test/input.png"
