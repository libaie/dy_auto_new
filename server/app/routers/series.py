"""系列 + 剧集管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Series, Episode, Character, Scene, PipelineRun, series_characters, series_scenes
from app.services.ai_generator import ai_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/series", tags=["series"])


class SeriesCreate(BaseModel):
    title: str
    logline: Optional[str] = None
    genre: str = "drama"
    total_episodes: int = 30
    target_duration: int = 90
    mode: str = "step_by_step"
    pilot_first: bool = True


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_json: Optional[dict] = None
    storyboard_json: Optional[dict] = None


# === AI 自动生成角色 + 场景 ===

@router.post("/{series_id}/auto-generate")
async def auto_generate_series_assets(series_id: str, db: Session = Depends(get_db),
                                      user = Depends(verify_admin_token)):
    """根据系列 logline 自动生成角色和场景，自动创建并关联到系列。"""
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    if not s.logline:
        raise HTTPException(400, "请先填写系列的故事概要 (logline)")

    text = s.logline
    genre = s.genre

    # 1. 生成角色
    char_prompt = f"""故事概要：{text}
类型：{genre}
需要生成的角色数量：4

为每个角色生成以下字段的 JSON：
- name: 角色姓名
- role_type: protagonist(主角) / antagonist(反派) / supporting(配角) / cameo(客串)
- gender: male / female
- age_range: 年龄段，如 "25-30"
- personality: 性格描述（2-3句）
- appearance_desc: 详细外貌描述（50-100字，用于 AI 图像生成）
- outfit_desc: 典型着装描述（30-50字，用于 AI 图像生成）

严格输出 JSON 数组，格式：{{"characters": [...]}}"""
    try:
        raw_chars = await ai_generator.generate_custom(
            db, _CHAR_SYSTEM, char_prompt, max_tokens=4096, temperature=0.8
        )
        char_data = _parse_json_with_key(raw_chars, "characters")
    except Exception as e:
        logger.warning("Auto-generate characters failed: %s", e)
        raise HTTPException(500, f"角色生成失败: {e}")

    # 2. 生成场景
    scene_prompt = f"""故事概要：{text}
类型：{genre}
需要生成的场景数量：5

为每个场景生成以下字段的 JSON：
- name: 场景/地点名称
- scene_type: indoor(室内) / outdoor(室外) / transition(转场) / special(特殊)
- location_desc: 详细地点描述（50-100字，用于 AI 图像生成）
- lighting: day(白天) / dusk(黄昏) / night(夜晚) / warm_indoor(室内暖光) / cold_fluorescent(冷荧光)
- mood: warm(温馨) / tense(紧张) / romantic(浪漫) / mysterious(悬疑) / sad(悲伤) / joyful(欢快)

严格输出 JSON 数组，格式：{{"scenes": [...]}}"""
    try:
        raw_scenes = await ai_generator.generate_custom(
            db, _SCENE_SYSTEM, scene_prompt, max_tokens=4096, temperature=0.8
        )
        scene_data = _parse_json_with_key(raw_scenes, "scenes")
    except Exception as e:
        logger.warning("Auto-generate scenes failed: %s", e)
        raise HTTPException(500, f"场景生成失败: {e}")

    # 3. 持久化角色
    created_chars = []
    for c in char_data["characters"]:
        ch = Character(
            name=c.get("name", "?"),
            role_type=c.get("role_type", "supporting"),
            gender=c.get("gender", "male"),
            age_range=c.get("age_range", ""),
            personality=c.get("personality", ""),
            appearance_desc=c.get("appearance_desc", ""),
            outfit_desc=c.get("outfit_desc", ""),
        )
        db.add(ch)
        created_chars.append(ch)

    # 4. 持久化场景
    created_scenes = []
    for sc in scene_data["scenes"]:
        scene = Scene(
            name=sc.get("name", "?"),
            scene_type=sc.get("scene_type", "indoor"),
            location_desc=sc.get("location_desc", ""),
            lighting=sc.get("lighting", ""),
            mood=sc.get("mood", ""),
        )
        db.add(scene)
        created_scenes.append(scene)

    db.flush()

    # 5. 关联到系列
    for ch in created_chars:
        s.characters.append(ch)
    for sc in created_scenes:
        s.scenes.append(sc)

    db.commit()

    return {
        "ok": True,
        "characters": [_series_char_dict(c) for c in created_chars],
        "scenes": [_series_scene_dict(sc) for sc in created_scenes],
    }


_CHAR_SYSTEM = """你是一位资深的编剧和角色设计师。根据故事概要生成详细的角色档案。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个角色包含所有要求字段。
appearance_desc 要足够详细（50-100字），用于 AI 图像生成。角色之间要有区分度。"""

_SCENE_SYSTEM = """你是一位资深的电影导演和场景设计师。根据故事概要生成详细的场景描述。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个场景包含所有要求字段。
location_desc 要足够详细（50-100字），用于 AI 图像生成。场景之间要有区分度。"""


def _parse_json_with_key(raw: str, key: str) -> dict:
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
    # Brace-counting extraction: find {"key":[...]} with proper nesting
    key_pos = raw.find('"' + key + '"')
    if key_pos >= 0:
        # Find the opening brace before the key
        brace_start = raw.rfind('{', 0, key_pos)
        if brace_start >= 0:
            depth = 0
            i = brace_start
            while i < len(raw):
                if raw[i] == '{':
                    depth += 1
                elif raw[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[brace_start:i + 1])
                        except json.JSONDecodeError:
                            pass
                        break
                i += 1
    raise ValueError(f"无法解析 LLM 返回的 JSON (key={key}): {raw[:300]}")


def _series_char_dict(c: Character) -> dict:
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}


def _series_scene_dict(s: Scene) -> dict:
    return {col.name: getattr(s, col.name) for col in Scene.__table__.columns}


def _series_dict(s: Series) -> dict:
    base = {col.name: getattr(s, col.name) for col in Series.__table__.columns}
    base["character_count"] = len(s.characters) if hasattr(s, "characters") else 0
    base["scene_count"] = len(s.scenes) if hasattr(s, "scenes") else 0
    return base


def _episode_dict(e: Episode) -> dict:
    return {col.name: getattr(e, col.name) for col in Episode.__table__.columns}


# === Series CRUD ===

@router.get("")
def list_series(db: Session = Depends(get_db)):
    all_series = db.query(Series).order_by(Series.updated_at.desc()).all()
    return {"ok": True, "series": [_series_dict(s) for s in all_series]}

@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = Series(**body.model_dump())
    db.add(s)
    db.flush()  # 确保 s.id 已生成，满足 Episode FK 约束
    for ep_num in range(1, body.total_episodes + 1):
        db.add(Episode(series_id=s.id, episode_number=ep_num, status="pending"))
    db.commit(); db.refresh(s)
    return {"ok": True, "series": _series_dict(s)}

@router.get("/{series_id}")
def get_series(series_id: str, db: Session = Depends(get_db)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    episodes = db.query(Episode).filter(
        Episode.series_id == series_id
    ).order_by(Episode.episode_number).all()
    return {"ok": True, "series": _series_dict(s),
            "episodes": [_episode_dict(e) for e in episodes]}

@router.delete("/{series_id}")
def delete_series(series_id: str, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    # Clean M2M rows first, then episodes, then series
    db.execute(series_characters.delete().where(series_characters.c.series_id == series_id))
    db.execute(series_scenes.delete().where(series_scenes.c.series_id == series_id))
    db.query(Episode).filter(Episode.series_id == series_id).delete()
    db.query(PipelineRun).filter(PipelineRun.series_id == series_id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True}

# === M2M 关联 ===

@router.post("/{series_id}/characters/{character_id}")
def link_character(series_id: str, character_id: str, db: Session = Depends(get_db),
                   user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    c = db.query(Character).filter(Character.id == character_id).first()
    if not s or not c:
        raise HTTPException(404, "Series or Character not found")
    s.characters.append(c)
    db.commit()
    return {"ok": True}

@router.post("/{series_id}/scenes/{scene_id}")
def link_scene(series_id: str, scene_id: str, db: Session = Depends(get_db),
               user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    sc = db.query(Scene).filter(Scene.id == scene_id).first()
    if not s or not sc:
        raise HTTPException(404, "Series or Scene not found")
    s.scenes.append(sc)
    db.commit()
    return {"ok": True}

# === Episode 管理 ===

@router.put("/{series_id}/episodes/{episode_id}")
def update_episode(series_id: str, episode_id: str, body: EpisodeUpdate,
                   db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    ep = db.query(Episode).filter(
        Episode.id == episode_id, Episode.series_id == series_id
    ).first()
    if not ep:
        raise HTTPException(404, "Episode not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ep, k, v)
    db.commit()
    return {"ok": True}
