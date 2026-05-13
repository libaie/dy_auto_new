"""场景管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Scene
from app.services.ai_generator import ai_generator

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

SCENE_GEN_SYSTEM = """你是一位资深的电影导演和场景设计师。根据用户提供的故事概要，生成详细的拍摄场景描述。

输出要求：
1. 必须是合法的 JSON，不要包含 markdown 代码块标记
2. 场景数量与用户要求一致
3. 每个场景必须包含所有字段
4. location_desc 要足够详细（50-100字），用于 AI 生成场景参考图
5. 场景之间要有区分度，覆盖故事的主要场景发生地"""


@router.get("")
def list_scenes(db: Session = Depends(get_db)):
    return {"ok": True, "scenes": [_to_dict(s) for s in db.query(Scene).all()]}


@router.post("")
def create_scene(body: SceneCreate, db: Session = Depends(get_db),
                 _: str = Depends(verify_admin_token)):
    s = Scene(**body.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return {"ok": True, "scene": _to_dict(s)}


@router.put("/{scene_id}")
def update_scene(scene_id: str, body: dict, db: Session = Depends(get_db),
                 _: str = Depends(verify_admin_token)):
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
                 _: str = Depends(verify_admin_token)):
    db.query(Scene).filter(Scene.id == scene_id).delete()
    db.commit()
    return {"ok": True}


@router.post("/auto-generate")
async def auto_generate_scenes(body: AutoGenerateInput, db: Session = Depends(get_db),
                               _: str = Depends(verify_admin_token)):
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
