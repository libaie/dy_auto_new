"""角色管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Character
from app.services.ai_generator import ai_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharacterCreate(BaseModel):
    name: str
    role_type: str = "protagonist"
    gender: str = "male"
    age_range: Optional[str] = None
    personality: Optional[str] = None
    appearance_desc: Optional[str] = None
    outfit_desc: Optional[str] = None
    default_voice_id: Optional[str] = None


class AutoGenerateInput(BaseModel):
    text: str = Field(..., min_length=10, max_length=5000)
    genre: str = "drama"
    count: int = Field(default=4, ge=1, le=10)

CHARACTER_GEN_SYSTEM = """你是一位资深的编剧和角色设计师。根据用户提供的故事概要，生成详细的角色档案。

输出要求：
1. 必须是合法的 JSON，不要包含 markdown 代码块标记
2. 角色数量与用户要求一致
3. 每个角色必须包含所有字段
4. appearance_desc 要足够详细（50-100字），用于 AI 生成角色参考图
5. 角色之间要有区分度（不同性格、不同功能）"""


@router.get("")
def list_characters(db: Session = Depends(get_db)):
    return {"ok": True, "characters": [_to_dict(c) for c in db.query(Character).all()]}


@router.post("")
def create_character(body: CharacterCreate, db: Session = Depends(get_db),
                     _: str = Depends(verify_admin_token)):
    c = Character(**body.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "character": _to_dict(c)}


@router.put("/{character_id}")
def update_character(character_id: str, body: dict, db: Session = Depends(get_db),
                     _: str = Depends(verify_admin_token)):
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
                     _: str = Depends(verify_admin_token)):
    db.query(Character).filter(Character.id == character_id).delete()
    db.commit()
    return {"ok": True}


@router.post("/auto-generate")
async def auto_generate_characters(body: AutoGenerateInput, db: Session = Depends(get_db),
                                   _: str = Depends(verify_admin_token)):
    """AI 根据故事文本自动生成角色档案。返回角色列表（不持久化），前端确认后逐个创建。"""
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
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}
