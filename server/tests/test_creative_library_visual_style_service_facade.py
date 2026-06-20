import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-visual-style-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-visual-style-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library/visual_style_inference_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/visual_style_inference_service.py"
REFERENCE_ASSET_PATH = REPO_ROOT / "server/app/domains/creative_library/reference_asset_service.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"


def test_visual_style_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.visual_style_inference_service",
        "app.services.visual_style_inference_service",
        "infer_visual_style_from_story",
        "DEFAULT_NEGATIVE",
    ]:
        assert term in spec
        assert term in plan


def test_visual_style_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_visual_style_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def infer_visual_style_from_story" not in text
    assert "DEFAULT_NEGATIVE =" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_visual_style_module_is_domain_module():
    legacy = importlib.import_module("app.services.visual_style_inference_service")
    domain = importlib.import_module("app.domains.creative_library.visual_style_inference_service")
    assert legacy is domain
    assert legacy.infer_visual_style_from_story is domain.infer_visual_style_from_story
    assert legacy.DEFAULT_NEGATIVE == domain.DEFAULT_NEGATIVE


def test_services_parent_package_visual_style_attribute_is_domain_module():
    from app.services import visual_style_inference_service as parent_import

    domain = importlib.import_module("app.domains.creative_library.visual_style_inference_service")
    assert parent_import is domain


def test_reference_asset_service_imports_domain_visual_style_service():
    text = REFERENCE_ASSET_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.visual_style_inference_service" in text
    assert "app.services.visual_style_inference_service" not in text


def test_creative_library_docs_register_visual_style_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "visual_style_inference_service.py",
        "infer_visual_style_from_story",
        "app.services.visual_style_inference_service",
        "app.domains.creative_library.visual_style_inference_service",
    ]:
        assert term in readme


def test_legacy_visual_style_behavior_stays_available():
    legacy = importlib.import_module("app.services.visual_style_inference_service")
    style = legacy.infer_visual_style_from_story("现实生活 普通中老年 控糖")
    assert style["medium"] == "photorealistic_live_action"
    assert "photorealistic live-action" in style["prompt"]
    assert "no anime" in style["negative_prompt"]


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
