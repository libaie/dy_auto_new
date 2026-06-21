from app.db.models import Character, Episode, Scene, Series
from app.domains.ai_video_series.langchain_runtime.tools import (
    build_ai_video_tools,
    series_context_payload,
)


def test_series_context_payload_includes_episode_assets(db):
    series = Series(title="Tool Series", logline="Secret heir.", total_episodes=1)
    character = Character(name="Lin Xia", role_type="protagonist", gender="female")
    scene = Scene(name="Clinic", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.commit()

    payload = series_context_payload(db, series.id, episode.id)

    assert payload["series"]["title"] == "Tool Series"
    assert payload["episode"]["title"] == "Pilot"
    assert payload["characters"] == [{"id": character.id, "name": "Lin Xia", "role_type": "protagonist"}]
    assert payload["scenes"] == [{"id": scene.id, "name": "Clinic", "scene_type": "indoor"}]


def test_build_ai_video_tools_returns_restricted_tool_names(db):
    tools = build_ai_video_tools(db=None, allowed_tools=["validate_json"])

    assert [tool.name for tool in tools] == ["validate_json"]
