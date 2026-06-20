"""AI rewrite candidates for character and scene assets."""
import json
import re
from json import JSONDecodeError

from sqlalchemy.orm import Session

from app.db_models import Character, Scene
from app.services.ai_generator import ai_generator


class AssetAiRewriteError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


CHARACTER_ALLOWED_FIELDS = (
    "name",
    "role_type",
    "gender",
    "age_range",
    "personality",
    "appearance_desc",
    "outfit_desc",
    "default_voice_id",
)

SCENE_ALLOWED_FIELDS = (
    "name",
    "scene_type",
    "location_desc",
    "lighting",
    "mood",
)

_SYSTEM_PROMPT = """You generate candidate-only JSON rewrites for an existing asset.
Return valid JSON only. Do not include markdown.
Use either {{"candidate": {{...}}}} or a flat object.
Only include fields that should change, and never persist changes.
Allowed fields: {fields}."""


async def generate_character_rewrite_candidate(db: Session, character_id: str, instruction: str = "") -> dict:
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise AssetAiRewriteError(
            "CHARACTER_NOT_FOUND",
            "Character not found",
            {"character_id": character_id},
        )

    current = _row_to_allowed_dict(character, CHARACTER_ALLOWED_FIELDS)
    raw = await ai_generator.generate_custom(
        db,
        _SYSTEM_PROMPT.format(fields=", ".join(CHARACTER_ALLOWED_FIELDS)),
        _user_prompt("character", current, instruction),
        max_tokens=2048,
        temperature=0.4,
    )
    candidate = _parse_candidate(raw, CHARACTER_ALLOWED_FIELDS)
    return _response("character", character_id, current, candidate)


async def generate_scene_rewrite_candidate(db: Session, scene_id: str, instruction: str = "") -> dict:
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise AssetAiRewriteError(
            "SCENE_NOT_FOUND",
            "Scene not found",
            {"scene_id": scene_id},
        )

    current = _row_to_allowed_dict(scene, SCENE_ALLOWED_FIELDS)
    raw = await ai_generator.generate_custom(
        db,
        _SYSTEM_PROMPT.format(fields=", ".join(SCENE_ALLOWED_FIELDS)),
        _user_prompt("scene", current, instruction),
        max_tokens=2048,
        temperature=0.4,
    )
    candidate = _parse_candidate(raw, SCENE_ALLOWED_FIELDS)
    return _response("scene", scene_id, current, candidate)


def _user_prompt(asset_type: str, current: dict, instruction: str) -> str:
    return (
        f"Asset type: {asset_type}\n"
        f"Current JSON:\n{json.dumps(current, ensure_ascii=False, indent=2)}\n"
        f"Instruction: {instruction or 'Improve clarity while preserving intent.'}\n"
        'Return JSON in this shape: {"candidate": {...}}'
    )


def _response(asset_type: str, asset_id: str, current: dict, candidate: dict) -> dict:
    return {
        "ok": True,
        "asset_type": asset_type,
        "asset_id": asset_id,
        "current": current,
        "candidate": candidate,
        "warnings": [],
        "missing_requirements": [],
    }


def _row_to_allowed_dict(row, allowed_fields: tuple[str, ...]) -> dict:
    return {field: getattr(row, field) for field in allowed_fields}


def _parse_candidate(raw: str, allowed_fields: tuple[str, ...]) -> dict:
    for parsed in _parse_json_objects(raw):
        root = parsed.get("candidate") if isinstance(parsed.get("candidate"), dict) else parsed
        candidate = {field: root[field] for field in allowed_fields if field in root}
        if candidate:
            return candidate
    _raise_invalid(raw, "AI output contained no allowed candidate fields")


def _parse_json_objects(raw: str) -> list[dict]:
    if not isinstance(raw, str) or not raw.strip():
        _raise_invalid(raw or "", "AI output was empty")

    text = raw.strip()
    attempts = [text]
    attempts.extend(match.group(1).strip() for match in re.finditer(r"```(?:json)?\s*([\s\S]+?)\s*```", text))

    decoder = json.JSONDecoder()
    parsed_objects: list[dict] = []
    for attempt in attempts:
        try:
            value = json.loads(attempt)
            if isinstance(value, dict):
                parsed_objects.append(value)
        except JSONDecodeError:
            pass

        for index, char in enumerate(attempt):
            if char != "{":
                continue
            try:
                value, _end = decoder.raw_decode(attempt[index:])
            except JSONDecodeError:
                continue
            if isinstance(value, dict):
                parsed_objects.append(value)

    if not parsed_objects:
        _raise_invalid(raw, "AI output was not valid JSON")
    return parsed_objects


def _raise_invalid(raw: str, reason: str) -> None:
    preview = raw if isinstance(raw, str) else repr(raw)
    raise AssetAiRewriteError(
        "AI_REWRITE_INVALID_OUTPUT",
        "AI rewrite output was invalid or empty",
        {
            "reason": reason,
            "raw_preview": preview[:300],
        },
    )
