import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-script-pipeline-storyboard-timing-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-script-pipeline-storyboard-timing-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/script_pipeline/storyboard_timing.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/storyboard_timing.py"
SERVICE_PATH = REPO_ROOT / "server/app/domains/script_pipeline/script_pipeline_service.py"
README_PATH = REPO_ROOT / "server/app/domains/script_pipeline/README.md"


def test_storyboard_timing_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.script_pipeline.storyboard_timing",
        "app.services.storyboard_timing",
        "annotate_storyboard_with_timing",
        "build_detailed_video_prompt",
    ]:
        assert term in spec
        assert term in plan


def test_storyboard_timing_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_storyboard_timing_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.script_pipeline" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def annotate_storyboard_with_timing" not in text
    assert "DEFAULT_TIMED_SHOT_SECONDS =" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_storyboard_timing_module_is_domain_module():
    legacy = importlib.import_module("app.services.storyboard_timing")
    domain = importlib.import_module("app.domains.script_pipeline.storyboard_timing")
    assert legacy is domain
    assert legacy.annotate_storyboard_with_timing is domain.annotate_storyboard_with_timing
    assert legacy.build_detailed_video_prompt is domain.build_detailed_video_prompt


def test_services_parent_package_storyboard_timing_attribute_is_domain_module():
    from app.services import storyboard_timing as parent_import

    domain = importlib.import_module("app.domains.script_pipeline.storyboard_timing")
    assert parent_import is domain


def test_script_pipeline_service_imports_domain_storyboard_timing():
    text = SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.script_pipeline.storyboard_timing" in text
    assert "app.services.storyboard_timing" not in text


def test_script_pipeline_docs_register_storyboard_timing_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "storyboard_timing.py",
        "annotate_storyboard_with_timing",
        "app.services.storyboard_timing",
        "app.domains.script_pipeline.storyboard_timing",
    ]:
        assert term in readme


def test_legacy_storyboard_timing_behavior_stays_available():
    legacy = importlib.import_module("app.services.storyboard_timing")
    storyboard = legacy.annotate_storyboard_with_timing({
        "frames": [
            {"duration": 1.5, "narration": "hello"},
            {"duration": 0, "image_prompt": "frame"},
        ]
    })
    assert storyboard["frame_count"] == 2
    assert storyboard["total_duration"] == 3.5
    assert storyboard["frames"][0]["time_range"] == "0-1.5秒"
    assert storyboard["frames"][1]["duration"] == legacy.DEFAULT_TIMED_SHOT_SECONDS


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
