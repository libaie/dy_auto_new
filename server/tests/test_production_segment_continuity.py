from app.services.pixelle_execution_service import build_video_stage_frame


def test_build_video_stage_frame_adds_previous_end_frame_for_continuous_action():
    frame = build_video_stage_frame(
        {
            "id": "segment-db-id",
            "segment_id": "shot-001-seg-02",
            "continuity_mode": "continuous_action",
            "previous_end_frame_url": "https://cdn.test/previous-end.png",
            "reference_roles_json": [
                {"role": "style_anchor", "url": "https://cdn.test/style.png", "priority": 2},
                {"role": "character_anchor", "url": "https://cdn.test/character.png", "priority": 1},
            ],
            "duration_seconds": 6,
            "video_prompt": "The hero keeps walking forward.",
            "audio_mode": "seedance_native",
        },
        approved_image_url="https://cdn.test/approved.png",
    )

    assert frame["frame_id"] == "shot-001-seg-02"
    assert frame["production_segment_id"] == "segment-db-id"
    assert frame["continuity_mode"] == "continuous_action"
    assert frame["approved_image_url"] == "https://cdn.test/approved.png"
    assert frame["previous_end_frame_url"] == "https://cdn.test/previous-end.png"
    assert frame["reference_roles"][-1] == {
        "role": "previous_end_frame",
        "url": "https://cdn.test/previous-end.png",
        "priority": 3,
    }
    assert frame["reference_urls"] == [
        "https://cdn.test/character.png",
        "https://cdn.test/style.png",
        "https://cdn.test/previous-end.png",
    ]
    assert frame["duration"] == 6.0
    assert frame["video_prompt"] == "The hero keeps walking forward."
    assert frame["audio_mode"] == "seedance_native"
    assert frame["return_last_frame"] is True


def test_build_video_stage_frame_does_not_add_previous_end_frame_for_scene_change():
    frame = build_video_stage_frame(
        {
            "id": "segment-db-id",
            "segment_id": "shot-002-seg-01",
            "continuity_mode": "scene_change",
            "previous_end_frame_url": "https://cdn.test/previous-end.png",
            "reference_roles_json": [
                {"role": "scene_reference", "url": "https://cdn.test/scene.png", "priority": 1},
            ],
            "duration_seconds": 5,
            "video_prompt": "Cut to a new location.",
        },
        approved_image_url="https://cdn.test/approved.png",
    )

    assert frame["continuity_mode"] == "scene_change"
    assert frame["previous_end_frame_url"] == ""
    assert all(role["role"] != "previous_end_frame" for role in frame["reference_roles"])
    assert frame["reference_urls"] == ["https://cdn.test/scene.png"]


def test_build_video_stage_frame_does_not_fallback_to_previous_end_frame_only_roles_for_montage():
    frame = build_video_stage_frame(
        {
            "id": "segment-db-id",
            "segment_id": "shot-003-seg-01",
            "continuity_mode": "montage",
            "reference_roles_json": [
                {"role": "previous_end_frame", "url": "https://cdn.test/previous-end.png", "priority": 1},
            ],
            "reference_urls": ["https://cdn.test/previous-end.png"],
            "duration_seconds": 5,
            "video_prompt": "Quick memory montage.",
        },
        approved_image_url="https://cdn.test/approved.png",
    )

    assert frame["previous_end_frame_url"] == ""
    assert frame["reference_roles"] == []
    assert frame["reference_urls"] == []
