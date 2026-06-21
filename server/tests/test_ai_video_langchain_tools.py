import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_build_ai_video_tools_can_select_provider_tool(db):
    tools = build_ai_video_tools(db=None, allowed_tools=["submit_image_generation"])

    assert [tool.name for tool in tools] == ["submit_image_generation"]
    assert tools[0].coroutine is not None


def test_build_ai_video_tools_respects_empty_allowed_tools(db):
    tools = build_ai_video_tools(db=None, allowed_tools=[])

    assert tools == []


def test_langchain_tools_import_has_no_config_side_effects_under_production_debug():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "server")
    env["DEBUG"] = "false"
    for key in ("DEVICE_SECRET", "ADMIN_PASSWORD", "JWT_SECRET"):
        env.pop(key, None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.domains.ai_video_series.langchain_runtime.tools; print('import-ok')",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    assert "import-ok" in completed.stdout


@pytest.mark.asyncio
async def test_read_series_context_tool_is_async_and_returns_context_json(db):
    series = Series(title="Async Tool Series", logline="Hidden ledger.", total_episodes=1)
    character = Character(name="Chen Yu", role_type="protagonist", gender="male")
    scene = Scene(name="Archive", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Ledger")
    db.add(episode)
    db.commit()
    read_series_context = build_ai_video_tools(db=db, allowed_tools=["read_series_context"])[0]

    assert read_series_context.coroutine is not None
    payload = json.loads(
        await read_series_context.ainvoke({"series_id": series.id, "episode_id": episode.id})
    )

    assert payload["series"]["title"] == "Async Tool Series"
    assert payload["episode"]["title"] == "Ledger"
    assert payload["characters"] == [{"id": character.id, "name": "Chen Yu", "role_type": "protagonist"}]
    assert payload["scenes"] == [{"id": scene.id, "name": "Archive", "scene_type": "indoor"}]
