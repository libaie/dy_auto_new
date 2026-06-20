import pytest

from app.domains.agency_operations import agency_manifest
from app.domains.agency_operations.agency_manifest import (
    AgencyManifest,
    EXPERT_IDS,
    AgencyManifestError,
    get_expert,
    list_experts,
    read_expert_markdown,
    verify_manifest,
)
from scripts.import_agency_agents_zh import DATA_ROOT, _safe_data_path


def test_manifest_contains_exact_video_expert_team():
    experts = list_experts()
    assert [expert.expert_id for expert in experts] == [
        "story_generator",
        "narrative_designer",
        "visual_storyteller",
        "image_prompt_engineer",
        "prompt_engineer",
        "short_video_editing_coach",
        "douyin_strategist",
        "video_optimization_specialist",
        "style_lock_quality_reviewer",
        "storyboard_quality_reviewer",
        "image_stage_quality_reviewer",
        "image_review_quality_reviewer",
        "video_stage_quality_reviewer",
        "video_review_quality_reviewer",
        "compose_quality_reviewer",
    ]
    assert set(EXPERT_IDS) == {expert.expert_id for expert in experts}
    assert "reality_checker" not in set(EXPERT_IDS)


def test_manifest_quality_experts_have_stage_metadata():
    quality_experts = [expert for expert in list_experts() if expert.role_type == "quality"]

    assert [expert.expert_id for expert in quality_experts] == [
        "style_lock_quality_reviewer",
        "storyboard_quality_reviewer",
        "image_stage_quality_reviewer",
        "image_review_quality_reviewer",
        "video_stage_quality_reviewer",
        "video_review_quality_reviewer",
        "compose_quality_reviewer",
    ]
    for expert in quality_experts:
        assert expert.phases == [expert.expert_id.removesuffix("_quality_reviewer").replace("stage", "stage")]


def test_legacy_reality_checker_is_read_only_and_not_current_manifest():
    assert hasattr(agency_manifest, "get_legacy_expert")
    assert hasattr(agency_manifest, "read_legacy_expert_markdown")
    expert = agency_manifest.get_legacy_expert("reality_checker")
    markdown = agency_manifest.read_legacy_expert_markdown("reality_checker")

    assert expert.expert_id == "reality_checker"
    assert expert.role_type == "legacy"
    assert expert.phases == []
    assert "reality_checker" not in [item.expert_id for item in list_experts()]
    assert len(markdown) > 500


def test_manifest_hashes_match_vendored_markdown():
    report = verify_manifest()
    assert report["ok"] is True
    assert report["checked_count"] == 15
    assert report["errors"] == []


def test_vendored_expert_directory_contains_only_current_manifest_markdown():
    expected_paths = {(DATA_ROOT / expert.source_path).resolve() for expert in list_experts()}
    expected_paths.add((DATA_ROOT / "testing/testing-reality-checker.md").resolve())
    expected_paths.add((DATA_ROOT / "README.md").resolve())
    actual_paths = {path.resolve() for path in DATA_ROOT.rglob("*.md")}

    assert actual_paths == expected_paths


def test_verify_manifest_rejects_hash_mismatch(monkeypatch):
    experts = []
    for expert in list_experts():
        if expert.expert_id == "prompt_engineer":
            expert = expert.model_copy(update={"sha256": "0" * 64})
        experts.append(expert)

    manifest = AgencyManifest(
        source_repo="test",
        source_commit="test",
        team_version="test",
        experts=experts,
    )
    monkeypatch.setattr(agency_manifest, "load_manifest", lambda: manifest)

    report = verify_manifest()

    assert report["ok"] is False
    assert report["errors"] == ["hash mismatch: specialized/prompt-engineer.md"]


def test_import_script_safe_data_path_rejects_escaping_paths():
    assert _safe_data_path("marketing/expert.md") == DATA_ROOT.resolve() / "marketing/expert.md"

    with pytest.raises(ValueError):
        _safe_data_path("../x.py")

    with pytest.raises(ValueError):
        _safe_data_path(str(DATA_ROOT.parent / "x.py"))


def test_read_expert_markdown_rejects_manifest_path_traversal(monkeypatch):
    experts = []
    for expert in list_experts():
        if expert.expert_id == "prompt_engineer":
            expert = expert.model_copy(update={"source_path": "../db_models.py"})
        experts.append(expert)

    manifest = AgencyManifest(
        source_repo="test",
        source_commit="test",
        team_version="test",
        experts=experts,
    )
    monkeypatch.setattr(agency_manifest, "load_manifest", lambda: manifest)

    with pytest.raises(AgencyManifestError):
        read_expert_markdown("prompt_engineer")


def test_read_expert_markdown_is_allowlisted():
    expert = get_expert("prompt_engineer")
    text = read_expert_markdown("prompt_engineer")
    assert expert.source_path == "specialized/prompt-engineer.md"
    assert len(text) > 500
    assert "prompt" in text.lower() or "提示" in text


def test_story_generator_expert_is_available_for_story_planning():
    expert = get_expert("story_generator")
    text = read_expert_markdown("story_generator")

    assert expert.name_zh == "故事生成专家"
    assert expert.role_type == "core"
    assert expert.source_path == "creative/story-generator.md"
    assert expert.phases == ["story_planning"]
    assert len(text) > 500
    assert "故事" in text
