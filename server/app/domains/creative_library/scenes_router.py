"""场景管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Scene
from app.services.ai_generator import ai_generator
from app.services.asset_ai_rewrite_service import (
    AssetAiRewriteError,
    generate_scene_rewrite_candidate,
)
from app.services.asset_lifecycle_service import AssetLifecycleError, archive_character_or_scene
from app.domains.creative_library.reference_asset_service import ReferenceAssetError, generate_scene_reference_images

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scenes", tags=["scenes"])


class SceneCreate(BaseModel):
    name: str
    scene_type: str = "indoor"
    location_desc: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None


class AutoGenerateInput(BaseModel):
    text: str = Field(..., min_length=10, max_length=5000)
    genre: str = "drama"
    count: int = Field(default=5, ge=1, le=10)


class ReferenceGenerateInput(BaseModel):
    slot: str = "all"


class AiRewriteInput(BaseModel):
    instruction: str = ""

SCENE_GEN_SYSTEM = """你是一位资深的电影导演和场景设计师。根据用户提供的故事概要，生成详细的拍摄场景描述。

输出要求：
1. 必须是合法的 JSON，不要包含 markdown 代码块标记
2. 场景数量与用户要求一致
3. 每个场景必须包含所有字段
4. location_desc 要足够详细（50-100字），用于 AI 生成场景参考图
5. 场景之间要有区分度，覆盖故事的主要场景发生地"""


@router.get("")
def list_scenes(db: Session = Depends(get_db),
                include_archived: bool = Query(False),
                _: str = Depends(verify_admin_token)):
    scenes = db.query(Scene).all()
    if not include_archived:
        scenes = [s for s in scenes if not (s.meta_json or {}).get("archived")]
    return {"ok": True, "scenes": [_to_dict(s) for s in scenes]}


@router.post("")
def create_scene(body: SceneCreate, db: Session = Depends(get_db),
                 user = Depends(verify_admin_token)):
    s = Scene(**body.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return {"ok": True, "scene": _to_dict(s)}


@router.put("/{scene_id}")
def update_scene(scene_id: str, body: dict, db: Session = Depends(get_db),
                 user = Depends(verify_admin_token)):
    s = db.query(Scene).filter(Scene.id == scene_id).first()
    if not s:
        raise HTTPException(404, "Scene not found")
    for k, v in body.items():
        if hasattr(s, k):
            setattr(s, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{scene_id}")
def delete_scene(scene_id: str, db: Session = Depends(get_db),
                 user = Depends(verify_admin_token)):
    try:
        result = archive_character_or_scene(db, "scene", scene_id)
    except AssetLifecycleError as exc:
        status_code = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code, exc.message)
    return {"ok": True, **result}


def _reference_asset_http_error(exc: ReferenceAssetError) -> HTTPException:
    status_code = 400
    if exc.code == "SCENE_NOT_FOUND":
        status_code = 404
    elif exc.code in ("MODEL_SCENE_NOT_CONFIGURED", "MODEL_API_KEY_MISSING"):
        status_code = 503
    elif exc.code in ("REFERENCE_PROVIDER_EMPTY_RESULT", "REFERENCE_PROVIDER_REQUEST_FAILED"):
        status_code = 502
    return HTTPException(status_code, {"code": exc.code, "message": exc.message, "details": exc.details})


def _ai_rewrite_http_error(exc: AssetAiRewriteError) -> HTTPException:
    status_code = 409
    if exc.code == "SCENE_NOT_FOUND":
        status_code = 404
    elif exc.code == "AI_REWRITE_INVALID_OUTPUT":
        status_code = 502
    return HTTPException(status_code, {"code": exc.code, "message": exc.message, "details": exc.details})


@router.post("/{scene_id}/reference-images/generate")
async def generate_scene_reference_images_endpoint(
    scene_id: str,
    body: ReferenceGenerateInput | None = None,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        return await generate_scene_reference_images(db, scene_id, slot=(body.slot if body else "all"))
    except ReferenceAssetError as exc:
        raise _reference_asset_http_error(exc)


@router.post("/{scene_id}/ai-rewrite-candidate")
@router.post("/{scene_id}/ai-rewrite")
async def generate_scene_ai_rewrite_endpoint(
    scene_id: str,
    body: AiRewriteInput | None = None,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        return await generate_scene_rewrite_candidate(
            db, scene_id, instruction=(body.instruction if body else "")
        )
    except AssetAiRewriteError as exc:
        raise _ai_rewrite_http_error(exc)
    except Exception as exc:
        logger.warning("Scene AI rewrite failed: %s", exc)
        raise HTTPException(
            500,
            {
                "code": "AI_REWRITE_FAILED",
                "message": "Scene AI rewrite failed",
                "details": {},
            },
        )


@router.post("/auto-generate")
async def auto_generate_scenes(body: AutoGenerateInput, db: Session = Depends(get_db),
                               user = Depends(verify_admin_token)):
    """AI 根据故事文本自动生成场景描述。返回场景列表（不持久化），前端确认后逐个创建。"""
    user_prompt = f"""故事概要：{body.text}
类型：{body.genre}
需要生成的场景数量：{body.count}

为每个场景生成以下字段的 JSON：
- name: 场景/地点名称
- scene_type: indoor(室内) / outdoor(室外) / transition(转场) / special(特殊)
- location_desc: 详细地点描述（50-100字，用于 AI 图像生成）
- lighting: day(白天) / dusk(黄昏) / night(夜晚) / warm_indoor(室内暖光) / cold_fluorescent(冷荧光)
- mood: warm(温馨) / tense(紧张) / romantic(浪漫) / mysterious(悬疑) / sad(悲伤) / joyful(欢快)

严格输出 JSON 数组，格式：{{"scenes": [{{"name":"...","scene_type":"...",...}}]}}"""
    try:
        raw = await ai_generator.generate_custom(
            db, SCENE_GEN_SYSTEM, user_prompt, max_tokens=4096, temperature=0.8
        )
        parsed = _parse_scenes_json(raw)
        return {"ok": True, "scenes": parsed["scenes"]}
    except Exception as e:
        logger.warning("Scene auto-generation failed: %s", e)
        raise HTTPException(500, f"AI 场景生成失败: {e}")


def _parse_scenes_json(raw: str) -> dict:
    import re
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r'\{[^{}]*"scenes"\s*:\s*\[[\s\S]*?\][^{}]*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 LLM 返回的场景 JSON: {raw[:300]}")


def _to_dict(s: Scene) -> dict:
    return {col.name: getattr(s, col.name) for col in Scene.__table__.columns}
