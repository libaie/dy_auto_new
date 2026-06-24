import json

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
    payload = json.loads(prompt)
    episodes = payload["episodes"]

    assert "do not assign the full series cast to every frame" in prompt
    assert payload["series"]["title"] == "Long Clinic"
    assert payload["series"]["logline"] == "Thirty compact medical mysteries."
    assert payload["series"]["genre"] == "medical"
    assert payload["asset_pool"]["characters"][0]["name"] == "Dr Lin"
    assert payload["asset_pool"]["scenes"][0]["name"] == "Clinic Hallway"
    assert payload["output_schema"]["covered_episode_numbers"] == list(range(1, 31))
    assert [episode["episode_number"] for episode in episodes] == list(range(1, 31))
    assert [episode["script_json"]["script"] for episode in episodes] == [
        f"Episode {index} uses Dr Lin and a one-off guest only when written."
        for index in range(1, 31)
    ]
    assert [episode["storyboard_json"]["frames"][0]["frame_id"] for episode in episodes] == [
        f"ep{index}-f1" for index in range(1, 31)
    ]
    assert "ep30-f1" in prompt
