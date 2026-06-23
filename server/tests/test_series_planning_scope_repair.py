from types import SimpleNamespace

import pytest

from app.db.models import AITextArtifact, Character, Episode, Scene, Series


def _story_payload(total_episodes: int, character_ids: list[str], scene_ids: list[str]) -> dict:
    return {
        "series_story_plan": {"summary": "The secret escalates."},
        "season_arc": {"arc_summary": "Every episode turns the knife."},
        "continuity_ledger": {"mainline": "Keep the secret coherent."},
        "episode_outlines": [
            {
                "episode_number": episode_number,
                "title": f"Episode {episode_number}",
                "hook": f"Hook {episode_number}",
                "episode_goal": f"Goal {episode_number}",
                "central_conflict": "The family secret gets harder to hide.",
                "reversal": f"Reversal {episode_number}",
                "cliffhanger": f"Cliffhanger {episode_number}",
                "previous_episode_handoff": "" if episode_number == 1 else f"From {episode_number - 1}",
                "next_episode_handoff": "Finale" if episode_number == total_episodes else f"To {episode_number + 1}",
                "character_state_changes": [],
                "foreshadowing_introduced": [],
                "foreshadowing_resolved": [],
                "character_ids": character_ids,
                "scene_ids": scene_ids,
            }
            for episode_number in range(1, total_episodes + 1)
        ],
    }


@pytest.mark.asyncio
async def test_story_plan_repairs_mechanical_full_asset_pool_copy(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning

    series = Series(title="Scope Repair", logline="A family secret returns.", total_episodes=3, status="draft")
    characters = [
        Character(name="Lead", role_type="protagonist", gender="female"),
        Character(name="Friend", role_type="supporting", gender="female"),
        Character(name="Rival", role_type="supporting", gender="male"),
        Character(name="Witness", role_type="supporting", gender="unknown"),
    ]
    scenes = [
        Scene(name="Home", scene_type="indoor"),
        Scene(name="Clinic", scene_type="indoor"),
        Scene(name="Street", scene_type="outdoor"),
    ]
    series.characters.extend(characters)
    series.scenes.extend(scenes)
    db.add(series)
    db.flush()
    db.add_all([
        Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending"),
        Episode(series_id=series.id, episode_number=2, title="Second", status="pending"),
        Episode(series_id=series.id, episode_number=3, title="Third", status="pending"),
    ])
    db.commit()

    character_ids = [character.id for character in characters]
    scene_ids = [scene.id for scene in scenes]
    payload = _story_payload(3, character_ids, scene_ids)

    async def fake_story_generator(**_kwargs):
        return SimpleNamespace(
            parsed=payload,
            source_type="ai",
            model_trace={"stage": "story_planning", "stage_status": "expert", "expert_id": "story_generator"},
        )

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)

    await planning.generate_series_story_plan(db, series.id, force=True)

    outlines = (
        db.query(AITextArtifact)
        .filter(AITextArtifact.series_id == series.id)
        .filter(AITextArtifact.artifact_type == "episode_outline")
        .filter(AITextArtifact.status == "approved")
        .all()
    )
    contents = sorted((artifact.content_json for artifact in outlines), key=lambda item: item["episode_number"])
    signatures = {(tuple(item["character_ids"]), tuple(item["scene_ids"])) for item in contents}

    assert len(contents) == 3
    assert len(signatures) > 1
    assert all(len(item["character_ids"]) < len(character_ids) for item in contents)
    assert all(len(item["scene_ids"]) < len(scene_ids) for item in contents)
    assert all(item["asset_scope_repair"]["characters"] == "mechanical_full_pool" for item in contents)
    assert all(item["asset_scope_repair"]["scenes"] == "mechanical_full_pool" for item in contents)
