from app.db.models import Character, Episode, Scene, Series
from app.domains.ai_video_series.asset_director_service import (
    build_asset_director_prompt,
    load_asset_director_inputs,
)


def test_thirty_episode_prompt_contains_series_wide_context_without_full_cast_instruction(db):
    series = Series(
        title="Long Clinic",
        logline="Thirty compact medical mysteries.",
        genre="medical",
        total_episodes=30,
        story_bible_json={"style_lock": {"locked": True, "version": 1}},
    )
    lead = Character(name="Dr Lin", role_type="protagonist", gender="female")
    hallway = Scene(name="Clinic Hallway", scene_type="indoor")
    series.characters.append(lead)
    series.scenes.append(hallway)
    db.add(series)
    for index in range(1, 31):
        db.add(
            Episode(
                series=series,
                episode_number=index,
                title=f"Case {index}",
                script_json={
                    "script": f"Episode {index} uses Dr Lin and a one-off guest only when written."
                },
                storyboard_json={
                    "frames": [
                        {"frame_id": f"ep{index}-f1", "visual": "Only scripted people appear."}
                    ]
                },
            )
        )
    db.commit()

    prompt = build_asset_director_prompt(load_asset_director_inputs(db=db, series_id=series.id))

    assert "covered_episode_numbers" in prompt
    assert "do not assign the full series cast to every frame" in prompt
    assert "ep30-f1" in prompt
    assert prompt.count("episode_number") >= 30
