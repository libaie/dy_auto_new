"""创意库业务域模块。

创意库业务域，负责锚点、参考资产、素材生命周期和 AI 改写。本文件负责 asset_ai_rewrite_service 相关业务规则、状态转换和外部系统边界。
"""

import json
import re
from json import JSONDecodeError

from sqlalchemy.orm import Session

from app.db.models.creative_library import Character, Scene
from app.domains.model_configuration.ai_generator import ai_generator


class AssetAiRewriteError(Exception):
    """业务类：承载 AssetAiRewriteError 相关的数据结构、状态或业务协作。

    类参数：code、details、message 承载该类的业务配置、状态或数据字段。
    """
    def __init__(self, code: str, message: str, details: dict | None = None):
        """初始化业务对象依赖，保存后续流程需要的运行上下文。

        入参：code、message、details 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
    """业务函数：处理 generate_character_rewrite_candidate 对应的业务流程、校验或数据转换。

    入参：db、character_id、instruction 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 generate_scene_rewrite_candidate 对应的业务流程、校验或数据转换。

    入参：db、scene_id、instruction 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _user_prompt 对应的业务流程、校验或数据转换。

    入参：asset_type、current、instruction 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return (
        f"Asset type: {asset_type}\n"
        f"Current JSON:\n{json.dumps(current, ensure_ascii=False, indent=2)}\n"
        f"Instruction: {instruction or 'Improve clarity while preserving intent.'}\n"
        'Return JSON in this shape: {"candidate": {...}}'
    )


def _response(asset_type: str, asset_id: str, current: dict, candidate: dict) -> dict:
    """业务函数：处理 _response 对应的业务流程、校验或数据转换。

    入参：asset_type、asset_id、current、candidate 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _row_to_allowed_dict 对应的业务流程、校验或数据转换。

    入参：row、allowed_fields 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {field: getattr(row, field) for field in allowed_fields}


def _parse_candidate(raw: str, allowed_fields: tuple[str, ...]) -> dict:
    """业务函数：处理 _parse_candidate 对应的业务流程、校验或数据转换。

    入参：raw、allowed_fields 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    for parsed in _parse_json_objects(raw):
        root = parsed.get("candidate") if isinstance(parsed.get("candidate"), dict) else parsed
        candidate = {field: root[field] for field in allowed_fields if field in root}
        if candidate:
            return candidate
    _raise_invalid(raw, "AI output contained no allowed candidate fields")


def _parse_json_objects(raw: str) -> list[dict]:
    """业务函数：处理 _parse_json_objects 对应的业务流程、校验或数据转换。

    入参：raw 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _raise_invalid 对应的业务流程、校验或数据转换。

    入参：raw、reason 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    preview = raw if isinstance(raw, str) else repr(raw)
    raise AssetAiRewriteError(
        "AI_REWRITE_INVALID_OUTPUT",
        "AI rewrite output was invalid or empty",
        {
            "reason": reason,
            "raw_preview": preview[:300],
        },
    )
