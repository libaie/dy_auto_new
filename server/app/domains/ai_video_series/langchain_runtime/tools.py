from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.db.models import Episode, Series
from app.domains.agency_operations.agency_runtime_contracts import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.agent_runner import extract_json_object


def series_context_payload(db: Session, series_id: str, episode_id: str | None = None) -> dict[str, Any]:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise AgencyRuntimeError("AI_VIDEO_CONTEXT_NOT_FOUND", "Series not found.")
    episode = None
    if episode_id:
        episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
        if not episode:
            raise AgencyRuntimeError("AI_VIDEO_CONTEXT_NOT_FOUND", "Episode not found.")
    return {
        "series": {
            "id": series.id,
            "title": series.title,
            "logline": series.logline,
            "genre": series.genre,
            "total_episodes": series.total_episodes,
        },
        "episode": None if episode is None else {
            "id": episode.id,
            "episode_number": episode.episode_number,
            "title": episode.title,
        },
        "characters": [
            {"id": item.id, "name": item.name, "role_type": item.role_type}
            for item in (series.characters or [])
        ],
        "scenes": [
            {"id": item.id, "name": item.name, "scene_type": item.scene_type}
            for item in (series.scenes or [])
        ],
        "story_bible": series.story_bible_json if isinstance(series.story_bible_json, dict) else {},
    }


def build_ai_video_tools(db: Session | None, allowed_tools: list[str] | None = None) -> list[Any]:
    selected = set(["validate_json", "read_series_context"] if allowed_tools is None else allowed_tools)

    @tool
    def validate_json(raw: str) -> dict[str, Any]:
        """Parse a JSON object from model text and return it."""
        return extract_json_object(raw)

    @tool
    def read_series_context(series_id: str, episode_id: str | None = None) -> str:
        """Read series and optional episode context as JSON."""
        if db is None:
            raise AgencyRuntimeError("AI_VIDEO_CONTEXT_NOT_FOUND", "Database session is required.")
        return json.dumps(series_context_payload(db, series_id, episode_id), ensure_ascii=False)

    tools_by_name = {
        "validate_json": validate_json,
        "read_series_context": read_series_context,
    }
    return [tools_by_name[name] for name in tools_by_name if name in selected]
