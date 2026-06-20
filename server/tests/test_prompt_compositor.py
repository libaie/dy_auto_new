import pytest

from app.db_models import (
    Character,
    CharacterAnchor,
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Scene,
    SceneAnchor,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)


def _create_anchor_production_graph(db):
    series = Series(title="Anchor Show", logline="Identity continuity test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    character = Character(
        name="Hero",
        role_type="protagonist",
        gender="female",
        appearance_desc="Clear oval face and shoulder-length black hair.",
        outfit_desc="Tailored white coat.",
    )
    scene = Scene(
        name="Hotel Entrance",
        scene_type="outdoor",
        location_desc="Rainy luxury hotel entrance.",
        lighting="cold blue neon",
        mood="tense",
    )
    db.add_all([character, scene])
    db.flush()

    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
    )
    db.add(production_episode)
    db.flush()
    production_scene = ProductionScene(
        episode_plan_id=production_episode.id,
        scene_id=scene.id,
        order_index=1,
        status="ready",
    )
    db.add(production_scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=production_scene.id,
        shot_id="shot-001",
        order_index=1,
        status="ready",
        character_ids=[character.id],
        action="Hero raises the lantern and steps toward the revolving door.",
        emotion="determined",
        shot_type="medium",
        duration_seconds=5,
    )
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-001-seg-01",
        order_index=1,
        status="planned",
        duration_seconds=5,
        image_prompt="legacy image prompt",
        video_prompt="legacy video prompt",
        narration="The hotel lights flicker.",
        reference_roles_json=[],
    )
    db.add(segment)
    db.add(CharacterAnchor(
        character_id=character.id,
        name=character.name,
        reference_slot="avatar_front_url",
        base_prompt="Stable hero face, shoulder-length black hair, tailored white coat.",
        anchor_image_url="https://cdn.test/hero-anchor.png",
        seed=3001,
        ref_mode="controlnet_face",
        status="locked",
    ))
    db.add(SceneAnchor(
        scene_id=scene.id,
        scene_name=scene.name,
        reference_slot="reference_wideshot_url",
        environment_prompt="Rainy luxury hotel entrance, cold blue neon, tense mood.",
        anchor_image_url="https://cdn.test/scene-anchor.png",
        seed=9001,
        ref_mode="image_to_image",
        status="locked",
    ))
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="draft",
        current_stage="draft",
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.commit()
    return {
        "shot": shot,
        "segment": segment,
        "run": run,
    }


def test_compose_shot_prompt_uses_scene_character_action_order(db):
    from app.utils.prompt_compositor import AssetPromptCompositor

    graph = _create_anchor_production_graph(db)
    composed = AssetPromptCompositor(db).compose_shot_prompt(graph["shot"].id)

    scene_index = composed.prompt.index("Rainy luxury hotel entrance")
    character_index = composed.prompt.index("Stable hero face")
    action_index = composed.prompt.index("Hero raises the lantern")
    emotion_index = composed.prompt.index("determined")

    assert scene_index < character_index < action_index < emotion_index
    assert composed.seed == 3001
    assert composed.provider_options == {"seed": 3001}
    assert composed.reference_urls == [
        "https://cdn.test/hero-anchor.png",
        "https://cdn.test/scene-anchor.png",
    ]


def test_compose_shot_prompt_requires_input_image_url_for_wan_i2v(db):
    from app.utils.prompt_compositor import AssetPromptCompositor

    graph = _create_anchor_production_graph(db)
    compositor = AssetPromptCompositor(db)

    with pytest.raises(ValueError, match="input_image_url"):
        compositor.compose_shot_prompt(graph["shot"].id, video_model_name="Wan 2.7")

    composed = compositor.compose_shot_prompt(
        graph["shot"].id,
        video_model_name="Wan 2.7",
        input_image_url="https://cdn.test/approved-first-frame.png",
    )

    assert composed.input_image_url == "https://cdn.test/approved-first-frame.png"


def test_linked_image_and_video_stage_frames_include_anchor_payload(db):
    from app.services.video_production_service import (
        build_image_stage_frames_for_segments,
        build_video_stage_frames_for_segments,
    )

    graph = _create_anchor_production_graph(db)
    image_frames = build_image_stage_frames_for_segments(db, graph["run"])

    assert image_frames[0]["image_prompt"].startswith("Rainy luxury hotel entrance")
    assert image_frames[0]["reference_urls"] == [
        "https://cdn.test/hero-anchor.png",
        "https://cdn.test/scene-anchor.png",
    ]
    assert image_frames[0]["reference_roles"][0]["role"] == "character_anchor"
    assert image_frames[0]["provider_options"] == {"seed": 3001}

    db.add(VideoProductionAsset(
        run_id=graph["run"].id,
        episode_id=graph["run"].episode_id,
        frame_id=graph["segment"].id,
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/approved-image.png",
        status="approved",
        production_segment_id=graph["segment"].id,
        copy_status="persisted",
        checksum="checksum-001",
        storage_path="/static/image-creation/approved-image.png",
        is_latest=True,
    ))
    db.commit()

    video_frames = build_video_stage_frames_for_segments(db, graph["run"])

    assert video_frames[0]["approved_image_url"] == "https://cdn.test/approved-image.png"
    assert video_frames[0]["input_image_url"] == "https://cdn.test/approved-image.png"
    assert video_frames[0]["reference_urls"] == [
        "https://cdn.test/hero-anchor.png",
        "https://cdn.test/scene-anchor.png",
    ]
