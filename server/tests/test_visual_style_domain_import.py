import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-visual-style-domain-import-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-visual-style-domain-import-plan.md"
STYLE_LOCK_PATH = REPO_ROOT / "server/app/domains/ai_video_series/style_lock.py"


def test_visual_style_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.visual_style_inference_service",
        "app.services.visual_style_inference_service",
        "style_lock",
    ]:
        assert term in spec
        assert term in plan


def test_style_lock_imports_visual_style_from_domain_path():
    text = STYLE_LOCK_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.visual_style_inference_service" in text
    assert "app.services.visual_style_inference_service" not in text


def test_legacy_visual_style_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.visual_style_inference_service")
    domain = importlib.import_module("app.domains.creative_library.visual_style_inference_service")
    assert legacy is domain
    assert legacy.infer_visual_style_from_story is domain.infer_visual_style_from_story
    assert legacy.DEFAULT_NEGATIVE == domain.DEFAULT_NEGATIVE
