"""角色管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db.models.creative_library import Character
from app.domains.model_configuration.ai_generator import ai_generator
from app.domains.creative_library.asset_ai_rewrite_service import (
    AssetAiRewriteError,
    generate_character_rewrite_candidate,
)
from app.domains.creative_library.asset_lifecycle_service import AssetLifecycleError, archive_character_or_scene
from app.domains.creative_library.reference_asset_service import ReferenceAssetError, generate_character_reference_images

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharacterCreate(BaseModel):
    """业务类：承载 CharacterCreate 相关的数据结构、状态或业务协作。

    类参数：age_range、appearance_desc、default_voice_id、gender、name、outfit_desc、personality、role_type 承载该类的业务配置、状态或数据字段。
    """
    name: str
    role_type: str = "protagonist"
    gender: str = "male"
    age_range: Optional[str] = None
    personality: Optional[str] = None
    appearance_desc: Optional[str] = None
    outfit_desc: Optional[str] = None
    default_voice_id: Optional[str] = None


class AutoGenerateInput(BaseModel):
    """业务类：承载 AutoGenerateInput 相关的数据结构、状态或业务协作。

    类参数：count、genre、text 承载该类的业务配置、状态或数据字段。
    """
    text: str = Field(..., min_length=10, max_length=5000)
    genre: str = "drama"
    count: int = Field(default=4, ge=1, le=10)


class ReferenceGenerateInput(BaseModel):
    """业务类：承载 ReferenceGenerateInput 相关的数据结构、状态或业务协作。

    类参数：slot 承载该类的业务配置、状态或数据字段。
    """
    slot: str = "all"


class AiRewriteInput(BaseModel):
    """业务类：承载 AiRewriteInput 相关的数据结构、状态或业务协作。

    类参数：instruction 承载该类的业务配置、状态或数据字段。
    """
    instruction: str = ""

CHARACTER_GEN_SYSTEM = """你是一位资深的编剧和角色设计师。根据用户提供的故事概要，生成详细的角色档案。

输出要求：
1. 必须是合法的 JSON，不要包含 markdown 代码块标记
2. 角色数量与用户要求一致
3. 每个角色必须包含所有字段
4. appearance_desc 要足够详细（50-100字），用于 AI 生成角色参考图
5. 角色之间要有区分度（不同性格、不同功能）"""


@router.get("")
def list_characters(db: Session = Depends(get_db),
                    include_archived: bool = Query(False),
                    _: str = Depends(verify_admin_token)):
    """业务函数：处理 list_characters 对应的业务流程、校验或数据转换。

    入参：db、include_archived、_ 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    characters = db.query(Character).all()
    if not include_archived:
        characters = [c for c in characters if not (c.meta_json or {}).get("archived")]
    return {"ok": True, "characters": [_to_dict(c) for c in characters]}


@router.post("")
def create_character(body: CharacterCreate, db: Session = Depends(get_db),
                     user = Depends(verify_admin_token)):
    """业务函数：处理 create_character 对应的业务流程、校验或数据转换。

    入参：body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    c = Character(**body.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "character": _to_dict(c)}


@router.put("/{character_id}")
def update_character(character_id: str, body: dict, db: Session = Depends(get_db),
                     user = Depends(verify_admin_token)):
    """业务函数：处理 update_character 对应的业务流程、校验或数据转换。

    入参：character_id、body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    c = db.query(Character).filter(Character.id == character_id).first()
    if not c:
        raise HTTPException(404, "Character not found")
    for k, v in body.items():
        if hasattr(c, k):
            setattr(c, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{character_id}")
def delete_character(character_id: str, db: Session = Depends(get_db),
                     user = Depends(verify_admin_token)):
    """业务函数：处理 delete_character 对应的业务流程、校验或数据转换。

    入参：character_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        result = archive_character_or_scene(db, "character", character_id)
    except AssetLifecycleError as exc:
        status_code = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code, exc.message)
    return {"ok": True, **result}


def _reference_asset_http_error(exc: ReferenceAssetError) -> HTTPException:
    """业务函数：处理 _reference_asset_http_error 对应的业务流程、校验或数据转换。

    入参：exc 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    status_code = 400
    if exc.code == "CHARACTER_NOT_FOUND":
        status_code = 404
    elif exc.code in ("MODEL_SCENE_NOT_CONFIGURED", "MODEL_API_KEY_MISSING"):
        status_code = 503
    elif exc.code in ("REFERENCE_PROVIDER_EMPTY_RESULT", "REFERENCE_PROVIDER_REQUEST_FAILED"):
        status_code = 502
    return HTTPException(status_code, {"code": exc.code, "message": exc.message, "details": exc.details})


def _ai_rewrite_http_error(exc: AssetAiRewriteError) -> HTTPException:
    """业务函数：处理 _ai_rewrite_http_error 对应的业务流程、校验或数据转换。

    入参：exc 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    status_code = 409
    if exc.code == "CHARACTER_NOT_FOUND":
        status_code = 404
    elif exc.code == "AI_REWRITE_INVALID_OUTPUT":
        status_code = 502
    return HTTPException(status_code, {"code": exc.code, "message": exc.message, "details": exc.details})


@router.post("/{character_id}/reference-images/generate")
async def generate_character_reference_images_endpoint(
    character_id: str,
    body: ReferenceGenerateInput | None = None,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 generate_character_reference_images_endpoint 对应的业务流程、校验或数据转换。

    入参：character_id、body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        return await generate_character_reference_images(db, character_id, slot=(body.slot if body else "all"))
    except ReferenceAssetError as exc:
        raise _reference_asset_http_error(exc)


@router.post("/{character_id}/ai-rewrite-candidate")
@router.post("/{character_id}/ai-rewrite")
async def generate_character_ai_rewrite_endpoint(
    character_id: str,
    body: AiRewriteInput | None = None,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 generate_character_ai_rewrite_endpoint 对应的业务流程、校验或数据转换。

    入参：character_id、body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        return await generate_character_rewrite_candidate(
            db, character_id, instruction=(body.instruction if body else "")
        )
    except AssetAiRewriteError as exc:
        raise _ai_rewrite_http_error(exc)
    except Exception as exc:
        logger.warning("Character AI rewrite failed: %s", exc)
        raise HTTPException(
            500,
            {
                "code": "AI_REWRITE_FAILED",
                "message": "Character AI rewrite failed",
                "details": {},
            },
        )


@router.post("/auto-generate")
async def auto_generate_characters(body: AutoGenerateInput, db: Session = Depends(get_db),
                                   user = Depends(verify_admin_token)):
    """业务函数：处理 auto_generate_characters 对应的业务流程、校验或数据转换。

    入参：body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    user_prompt = f"""故事概要：{body.text}
类型：{body.genre}
需要生成的角色数量：{body.count}

为每个角色生成以下字段的 JSON：
- name: 角色姓名
- role_type: protagonist(主角) / antagonist(反派) / supporting(配角) / cameo(客串)
- gender: male / female
- age_range: 年龄段，如 "25-30"
- personality: 性格描述（2-3句）
- appearance_desc: 详细外貌描述（50-100字，用于 AI 图像生成）
- outfit_desc: 典型着装描述（30-50字，用于 AI 图像生成）

严格输出 JSON 数组，格式：{{"characters": [{{"name":"...","role_type":"...",...}}]}}"""
    try:
        raw = await ai_generator.generate_custom(
            db, CHARACTER_GEN_SYSTEM, user_prompt, max_tokens=4096, temperature=0.8
        )
        parsed = _parse_characters_json(raw)
        return {"ok": True, "characters": parsed["characters"]}
    except Exception as e:
        logger.warning("Character auto-generation failed: %s", e)
        raise HTTPException(500, f"AI 角色生成失败: {e}")


def _parse_characters_json(raw: str) -> dict:
    """业务函数：处理 _parse_characters_json 对应的业务流程、校验或数据转换。

    入参：raw 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Parse LLM JSON output with fallback strategies."""
    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Strategy 2: extract from ```json ... ``` block
    import re
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Strategy 3: find first { ... } with "characters" key
    m = re.search(r'\{[^{}]*"characters"\s*:\s*\[[\s\S]*?\][^{}]*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 LLM 返回的角色 JSON: {raw[:300]}")


def _to_dict(c: Character) -> dict:
    """业务函数：处理 _to_dict 对应的业务流程、校验或数据转换。

    入参：c 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}
