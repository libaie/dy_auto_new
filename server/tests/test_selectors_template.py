"""Default selector template coverage for device runtime selectors."""
from pathlib import Path

import yaml

from app.db_models import UISelector
from app.seed import seed_selectors
from app.services.selector_service import selector_service


REQUIRED_RUNTIME_SELECTORS = {
    "comment_off_btn",
    "dm_entry_btn",
    "dm_send_failed",
    "feed",
    "is_comment_end",
    "is_comment_view",
    "is_dm_view",
    "is_follow",
    "is_search_view",
    "is_shopping_cart",
    "is_user_view",
    "is_video_view",
    "off_video",
    "search_result_list",
    "search_video_list",
    "video_comment_btn",
    "video_comment_input",
}

PAGE_DETECT_SELECTORS = {
    "feed",
    "is_comment_view",
    "is_dm_view",
    "is_search_view",
    "is_user_view",
    "is_video_view",
    "search_result_list",
}

USER_PROFILE_SELECTORS = {
    "user_age",
    "user_douyin_id",
    "user_fans_count",
    "user_follow_count",
    "user_gender",
    "user_ip_location",
    "user_is_private",
    "user_likes_count",
    "user_works_count",
}


def _template_selectors_for_platform(platform_version):
    path = Path(__file__).resolve().parents[1] / "config" / "selectors.yaml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        selector["action_name"]: selector
        for selector in data["selectors"]
        if selector.get("platform_version", "default") == platform_version
        and selector.get("resolution_profile", "default") == "default"
    }


def _template_selectors():
    return _template_selectors_for_platform("default")


def test_default_selector_template_covers_device_runtime_references():
    selectors = _template_selectors()

    missing = sorted(REQUIRED_RUNTIME_SELECTORS - set(selectors))

    assert missing == []
    for name in REQUIRED_RUNTIME_SELECTORS:
        assert selectors[name].get("strategies"), f"{name} must define strategies"


def test_seed_selectors_preserves_page_detect_metadata(db):
    template = _template_selectors()

    seed_selectors(db)

    for name in sorted(PAGE_DETECT_SELECTORS):
        row = db.query(UISelector).filter(
            UISelector.action_name == name,
            UISelector.platform_version == "default",
            UISelector.resolution_profile == "default",
        ).first()
        assert row is not None
        assert row.purpose == template[name].get("purpose")
        assert row.strategy_logic == template[name].get("strategy_logic", "and")


def test_seed_selectors_bumps_revision_when_template_adds_selector(db):
    db.query(UISelector).filter(UISelector.action_name == "feed").delete()
    db.commit()
    before = selector_service.get_version(db)

    added, _ = seed_selectors(db)
    after = selector_service.get_version(db)

    assert added >= 1
    assert after > before


def test_seed_selectors_restores_douyin_38_7_profile(db):
    from app.db_models import Device

    seed_selectors(db)

    restored = {
        row.action_name: row
        for row in db.query(UISelector).filter(
            UISelector.platform_version == "38.7.0",
            UISelector.resolution_profile == "default",
        ).all()
    }

    for action_name in {
        "comment_author",
        "comment_list",
        "comment_submit",
        "comment_text",
        "comment_time",
        "follow_button",
        "is_comment_view",
        "is_user_view",
        "is_video_view",
        "like_button",
        "search_video_list",
        "sort_button",
        "sort_default",
        "sort_latest",
        "sort_most_liked",
        "video_comment_btn",
        "video_comment_input",
    }:
        assert action_name in restored

    assert restored["comment_text"].purpose == "extract"
    assert restored["comment_author"].purpose == "extract"
    assert restored["comment_time"].extract_field == "desc"
    assert restored["comment_time"].clean_mode == "regex"
    assert r"\d{4}-\d{1,2}-\d{1,2}" in restored["comment_time"].clean_pattern
    assert restored["sort_latest"].strategies[0]["template"] == "sort_latest_1779245666090.jpg"

    db.add(Device(
        id="dev-douyin-38-7",
        name="Douyin 38.7 test device",
        device_secret="douyin-38-7-secret",
        screen_resolution="1080x2340",
    ))
    db.commit()

    _, selectors = selector_service.get_all_selectors(db, device_id="dev-douyin-38-7")
    sort_candidates = [
        selector for selector in selectors
        if selector["action_name"] == "sort_latest"
    ]

    assert any(
        selector["platform_version"] == "38.7.0"
        and selector["strategies"][0].get("template") == "sort_latest_1779245666090.jpg"
        for selector in sort_candidates
    )


def test_douyin_38_7_user_profile_selectors_match_default_template():
    default_selectors = _template_selectors()
    douyin_38_7_selectors = _template_selectors_for_platform("38.7.0")
    copied_fields = {
        "strategies",
        "purpose",
        "strategy_logic",
        "extract_field",
        "clean_mode",
        "clean_pattern",
        "clean_prompt",
    }

    for action_name in sorted(USER_PROFILE_SELECTORS):
        assert action_name in default_selectors
        assert action_name in douyin_38_7_selectors
        for field in copied_fields:
            assert douyin_38_7_selectors[action_name].get(field) == default_selectors[action_name].get(field)
