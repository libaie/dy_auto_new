"""系统字典 API — 管理所有下拉选项 + 分类."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import ReferenceData, ReferenceCategory

router = APIRouter(prefix="/api", tags=["reference-data"])

DEFAULT_CATEGORIES = [
    ("series_genre", "系列类型"),
    ("character_role", "角色类型"),
    ("scene_type", "场景类型"),
    ("scene_lighting", "场景光照"),
    ("scene_mood", "场景氛围"),
    ("dataSourceTypes", "数据来源类型"),
    ("llm_script_models", "脚本生成模型"),
    ("image_models", "画面生成模型"),
    ("video_models", "视频渲染模型"),
    ("tts_models", "语音合成模型"),
    ("audit_models", "质量审计模型"),
]

DEFAULT_DATA = {
    "series_genre": [
        ("drama", "都市爱情"), ("romance", "古装言情"), ("fantasy", "奇幻"),
        ("suspense", "悬疑推理"), ("scifi", "科幻"), ("comedy", "喜剧"),
        ("action", "动作"), ("horror", "恐怖"), ("history", "历史"),
    ],
    "character_role": [
        ("protagonist", "主角"), ("antagonist", "反派"),
        ("supporting", "配角"), ("cameo", "客串"),
    ],
    "scene_type": [
        ("indoor", "室内"), ("outdoor", "室外"),
        ("transition", "转场"), ("special", "特殊"),
    ],
    "scene_lighting": [
        ("day", "白天"), ("dusk", "黄昏"), ("night", "夜晚"),
        ("warm_indoor", "室内暖光"), ("cold_fluorescent", "冷荧光"),
    ],
    "scene_mood": [
        ("warm", "温馨"), ("tense", "紧张"), ("romantic", "浪漫"),
        ("mysterious", "悬疑"), ("sad", "悲伤"), ("joyful", "欢快"),
    ],
    "dataSourceTypes": [
        ("0", "普通视频"), ("1", "带货视频"),
    ],
    "llm_script_models": [
        ("qwen-max", "Qwen Max", "通义千问 · 阿里云"),
        ("gpt-4o", "GPT-4o", "OpenAI 旗舰"),
        ("deepseek-v3", "DeepSeek V3", "高性价比"),
        ("claude-opus", "Claude Opus", "创意写作"),
        ("ollama-local", "Ollama 本地", "开源本地部署"),
    ],
    "image_models": [
        ("flux", "FLUX", "RunningHub · 高质量静态图"),
        ("sdxl", "SDXL", "ComfyUI · 灵活可控"),
        ("auto", "自动选择", "根据场景自动匹配"),
    ],
    "video_models": [
        ("auto", "自动选择", "根据镜头类型智能切换"),
        ("seedance", "Seedance 2.0", "字节跳动 · 人脸最优"),
        ("kling", "Kling 3.0", "快手 · 4K AI导演"),
        ("wan", "Wan 2.7", "阿里 · 开源 RunningHub"),
        ("flux", "FLUX 静态图", "仅静态画面，无动态视频"),
    ],
    "tts_models": [
        ("edge-tts", "Edge-TTS", "微软免费 · 40+语言"),
        ("index-tts", "Index-TTS", "声音克隆 · 上传参考音频"),
        ("spark-tts", "Spark-TTS", "火山引擎 · 高级合成"),
        ("custom", "自定义 ComfyUI", "自托管 TTS 工作流"),
    ],
    "audit_models": [
        ("auto", "自动选择", "根据内容类型自动"),
        ("gemini", "Gemini", "Google 多模态审计"),
        ("gpt-4o", "GPT-4o", "OpenAI 视觉审计"),
        ("local", "本地 vLLM", "自托管审计模型"),
        ("none", "跳过审计", "不进行质量检查"),
    ],
}


# ==== Category CRUD ====

@router.get("/reference-categories")
def list_categories(db: Session = Depends(get_db)):
    """获取所有字典分类 (公开只读), 含每类已启用选项数."""
    cats = db.query(ReferenceCategory).order_by(ReferenceCategory.sort_order).all()
    # Per-category enabled item count
    counts = {}
    if cats:
        rows = (
            db.query(ReferenceData.category, func.count(ReferenceData.id))
            .filter(ReferenceData.enabled == True)
            .group_by(ReferenceData.category)
            .all()
        )
        counts = {row[0]: row[1] for row in rows}
    return {"ok": True, "categories": [
        {"id": c.id, "key": c.key, "label": c.label,
         "sort_order": c.sort_order, "item_count": counts.get(c.key, 0)}
        for c in cats
    ]}


class CategoryCreate(BaseModel):
    key: str
    label: str
    sort_order: int = 0


@router.post("/reference-categories")
def create_category(body: CategoryCreate, db: Session = Depends(get_db),
                    _: str = Depends(verify_admin_token)):
    cat = ReferenceCategory(key=body.key, label=body.label, sort_order=body.sort_order)
    db.add(cat)
    try:
        db.commit(); db.refresh(cat)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"分类 key '{body.key}' 已存在")
    return {"ok": True, "category": {"id": cat.id, "key": cat.key, "label": cat.label}}


@router.put("/reference-categories/{cat_id}")
def update_category(cat_id: str, body: dict, db: Session = Depends(get_db),
                    _: str = Depends(verify_admin_token)):
    cat = db.query(ReferenceCategory).filter(ReferenceCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(404, "分类不存在")
    if "label" in body:
        cat.label = body["label"]
    if "sort_order" in body:
        cat.sort_order = body["sort_order"]
    if "key" in body and body["key"] != cat.key:
        old_key = cat.key
        cat.key = body["key"]
        db.query(ReferenceData).filter(ReferenceData.category == old_key).update(
            {"category": body["key"]}, synchronize_session=False)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"分类 key '{body.get('key')}' 已存在")
    return {"ok": True}


@router.delete("/reference-categories/{cat_id}")
def delete_category(cat_id: str, db: Session = Depends(get_db),
                    _: str = Depends(verify_admin_token)):
    cat = db.query(ReferenceCategory).filter(ReferenceCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(404, "分类不存在")
    db.query(ReferenceData).filter(ReferenceData.category == cat.key).delete()
    db.delete(cat)
    db.commit()
    return {"ok": True}


# ==== Item CRUD ====

@router.get("/reference-data/{category}")
def list_items(category: str, db: Session = Depends(get_db)):
    """获取某分类下的所有启用选项 (公开只读)."""
    items = db.query(ReferenceData).filter(
        ReferenceData.category == category, ReferenceData.enabled == True
    ).order_by(ReferenceData.sort_order).all()
    return {"ok": True, "items": [
        {"value": it.value, "label": it.label, "description": it.description or ""}
        for it in items
    ]}


class RefDataCreate(BaseModel):
    category: str
    value: str
    label: str
    description: str = ""
    sort_order: int = 0


@router.post("/reference-data")
def create_item(body: RefDataCreate, db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    item = ReferenceData(**body.model_dump())
    db.add(item)
    try:
        db.commit(); db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"选项 '{body.value}' 在分类 '{body.category}' 中已存在")
    return {"ok": True, "item": {"value": item.value, "label": item.label}}


@router.put("/reference-data/{item_id}")
def update_item(item_id: str, body: dict, db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    item = db.query(ReferenceData).filter(ReferenceData.id == item_id).first()
    if not item: raise HTTPException(404)
    for k, v in body.items():
        if hasattr(item, k): setattr(item, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/reference-data/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    db.query(ReferenceData).filter(ReferenceData.id == item_id).delete()
    db.commit()
    return {"ok": True}


@router.get("/reference-data/admin/{category}")
def list_all_items(category: str, db: Session = Depends(get_db),
                   _: str = Depends(verify_admin_token)):
    """管理端：列出某分类所有项 (含 id, enabled)."""
    items = db.query(ReferenceData).filter(
        ReferenceData.category == category
    ).order_by(ReferenceData.sort_order).all()
    return {"ok": True, "items": [
        {"id": it.id, "value": it.value, "label": it.label,
         "description": it.description or "",
         "sort_order": it.sort_order, "enabled": it.enabled}
        for it in items
    ]}


# ==== Seed ====

def seed_reference_data(db: Session):
    """启动时 seed 默认分类 + 字典数据。幂等：已存在则跳过。"""
    for i, (key, label) in enumerate(DEFAULT_CATEGORIES):
        exists = db.query(ReferenceCategory).filter(ReferenceCategory.key == key).first()
        if not exists:
            db.add(ReferenceCategory(key=key, label=label, sort_order=i))
    db.commit()
    for category, entries in DEFAULT_DATA.items():
        for i, entry in enumerate(entries):
            val = entry[0]
            label = entry[1]
            desc = entry[2] if len(entry) > 2 else ""
            exists = db.query(ReferenceData).filter(
                ReferenceData.category == category,
                ReferenceData.value == val
            ).first()
            if not exists:
                db.add(ReferenceData(category=category, value=val, label=label,
                                     description=desc, sort_order=i))
    db.commit()
