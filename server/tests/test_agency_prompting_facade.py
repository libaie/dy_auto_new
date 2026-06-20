import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-prompting-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-prompting-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_prompting.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_prompting.py"


def test_agency_prompting_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_prompting",
        "app.services.agency_prompting",
        "build_expert_prompt",
        "creative_patches",
        "scorecard",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_prompting.py" in readme
    assert "app.domains.agency_operations.agency_prompting" in readme
    assert "app.services.agency_prompting" in readme


def test_agency_prompting_domain_file_owns_prompt_builder():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "class ExpertPrompt" in text
    assert "def build_expert_prompt" in text
    assert "creative_patches" in text
    assert "scorecard" in text


def test_legacy_agency_prompting_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_prompting" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def build_expert_prompt" not in text
    assert "class ExpertPrompt" not in text


def test_legacy_agency_prompting_module_aliases_domain():
    for name in (
        "app.services.agency_prompting",
        "app.domains.agency_operations.agency_prompting",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_prompting")
    domain = importlib.import_module("app.domains.agency_operations.agency_prompting")

    assert sys.modules["app.services.agency_prompting"] is domain
    assert legacy.ExpertPrompt is domain.ExpertPrompt
    assert legacy.build_expert_prompt is domain.build_expert_prompt


def test_agency_prompting_preserves_multimodal_content_parts():
    domain = importlib.import_module("app.domains.agency_operations.agency_prompting")

    prompt = domain.build_expert_prompt(
        expert_id="image_review_quality_reviewer",
        expert_markdown="do not leak me",
        stage="image_review",
        role="qa",
        stage_context={
            "asset_review": {
                "media_inputs": [
                    {"type": "image_url", "url": "https://cdn.test/shot.png"},
                    {"type": "video_url", "url": "https://cdn.test/shot.mp4"},
                ]
            }
        },
        output_schema={"type": "object", "properties": {"scorecard": {"type": "object"}}},
    )

    assert "do not leak me" not in prompt.system_prompt
    assert "creative_patches" in prompt.system_prompt
    assert "scorecard" in prompt.system_prompt
    assert isinstance(prompt.user_prompt, list)
    assert prompt.user_prompt[0]["type"] == "text"
    assert prompt.user_prompt[1] == {"type": "image_url", "image_url": {"url": "https://cdn.test/shot.png"}}
    assert prompt.user_prompt[2] == {"type": "video_url", "video_url": {"url": "https://cdn.test/shot.mp4"}}
