"""Pixelle stage payload mapping for series-level production segments."""
from __future__ import annotations

from typing import Any

from app.domains.video_production.production_status import (
    CONTINUITY_CONTINUOUS_ACTION,
    CONTINUITY_MONTAGE,
    CONTINUITY_NARRATIVE_CUT,
    CONTINUITY_SCENE_CHANGE,
    REFERENCE_PREVIOUS_END_FRAME,
)


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _priority(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _reference_roles(segment: dict[str, Any], continuity_mode: str) -> list[dict[str, Any]]:
    raw_roles = segment.get("reference_roles") or segment.get("reference_roles_json") or []
    roles: list[dict[str, Any]] = []
    if not isinstance(raw_roles, list):
        return roles

    for index, item in enumerate(raw_roles, start=1):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        url = str(item.get("url") or "").strip()
        if not role or not url:
            continue
        if continuity_mode in {CONTINUITY_SCENE_CHANGE, CONTINUITY_MONTAGE} and role == REFERENCE_PREVIOUS_END_FRAME:
            continue
        roles.append({**item, "role": role, "url": url, "priority": _priority(item.get("priority"), index)})
    return roles


def _next_priority(roles: list[dict[str, Any]]) -> int:
    priorities = [_priority(role.get("priority"), 0) for role in roles]
    return max(priorities, default=0) + 1


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        clean = str(url or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped


def _reference_urls(roles: list[dict[str, Any]], segment: dict[str, Any]) -> list[str]:
    raw_roles = segment.get("reference_roles") or segment.get("reference_roles_json") or []
    has_typed_roles = isinstance(raw_roles, list) and any(isinstance(item, dict) for item in raw_roles)
    continuity_mode = str(segment.get("continuity_mode") or CONTINUITY_NARRATIVE_CUT)
    if roles:
        ordered_roles = sorted(roles, key=lambda role: _priority(role.get("priority"), 0))
        return _dedupe_urls([role.get("url", "") for role in ordered_roles])
    if has_typed_roles and continuity_mode in {CONTINUITY_SCENE_CHANGE, CONTINUITY_MONTAGE}:
        return []
    raw_urls = segment.get("reference_urls") or []
    if not isinstance(raw_urls, list):
        return []
    return _dedupe_urls(raw_urls)


def build_video_stage_frame(segment: dict[str, Any], approved_image_url: str) -> dict:
    """Build the Pixelle /api/stages/videos/batch frame payload for one segment."""
    continuity_mode = str(segment.get("continuity_mode") or CONTINUITY_NARRATIVE_CUT)
    previous_end_frame_url = str(segment.get("previous_end_frame_url") or "").strip()
    previous_allowed = continuity_mode in {CONTINUITY_CONTINUOUS_ACTION, CONTINUITY_NARRATIVE_CUT}

    roles = _reference_roles(segment, continuity_mode)
    output_previous_end_frame_url = previous_end_frame_url if previous_allowed and previous_end_frame_url else ""
    if continuity_mode == CONTINUITY_CONTINUOUS_ACTION and output_previous_end_frame_url:
        already_present = any(
            role.get("role") == REFERENCE_PREVIOUS_END_FRAME
            and role.get("url") == output_previous_end_frame_url
            for role in roles
        )
        if not already_present:
            roles.append({
                "role": REFERENCE_PREVIOUS_END_FRAME,
                "url": output_previous_end_frame_url,
                "priority": _next_priority(roles),
            })

    return {
        "frame_id": str(segment.get("frame_id") or segment.get("segment_id") or segment.get("id") or ""),
        "production_segment_id": segment.get("production_segment_id") or segment.get("id") or segment.get("segment_id"),
        "continuity_mode": continuity_mode,
        "approved_image_url": approved_image_url,
        "input_image_url": str(segment.get("input_image_url") or approved_image_url),
        "previous_end_frame_url": output_previous_end_frame_url,
        "reference_roles": roles,
        "reference_urls": _reference_urls(roles, segment),
        "duration": _as_float(segment.get("duration", segment.get("duration_seconds")), 5.0),
        "video_prompt": str(segment.get("video_prompt") or ""),
        "audio_mode": str(segment.get("audio_mode") or "tts"),
        "return_last_frame": bool(segment.get("return_last_frame", True)),
    }
