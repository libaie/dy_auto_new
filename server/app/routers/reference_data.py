"""系统字典 API — 管理所有下拉选项."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import ReferenceData

router = APIRouter(prefix="/api/reference-data", tags=["reference-data"])

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
}


@router.get("/{category}")
def list_items(category: str, db: Session = Depends(get_db)):
    """获取某分类下的所有选项. 如不存在则自动 seed 默认值."""
    items = db.query(ReferenceData).filter(
        ReferenceData.category == category, ReferenceData.enabled == True
    ).order_by(ReferenceData.sort_order).all()

    if not items and category in DEFAULT_DATA:
        for i, (val, label) in enumerate(DEFAULT_DATA[category]):
            db.add(ReferenceData(category=category, value=val, label=label, sort_order=i))
        db.commit()
        items = db.query(ReferenceData).filter(
            ReferenceData.category == category, ReferenceData.enabled == True
        ).order_by(ReferenceData.sort_order).all()

    return {"ok": True, "items": [{"value": it.value, "label": it.label} for it in items]}


class RefDataCreate(BaseModel):
    category: str
    value: str
    label: str
    sort_order: int = 0


@router.post("")
def create_item(body: RefDataCreate, db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    item = ReferenceData(**body.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"ok": True, "item": {"value": item.value, "label": item.label}}


@router.put("/{item_id}")
def update_item(item_id: str, body: dict, db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    item = db.query(ReferenceData).filter(ReferenceData.id == item_id).first()
    if not item: raise HTTPException(404)
    for k, v in body.items():
        if hasattr(item, k): setattr(item, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    db.query(ReferenceData).filter(ReferenceData.id == item_id).delete()
    db.commit()
    return {"ok": True}


@router.get("/admin/{category}")
def list_all_items(category: str, db: Session = Depends(get_db),
                   _: str = Depends(verify_admin_token)):
    """管理端：列出某分类所有项 (含 id, enabled)."""
    items = db.query(ReferenceData).filter(
        ReferenceData.category == category
    ).order_by(ReferenceData.sort_order).all()
    if not items and category in DEFAULT_DATA:
        for i, (val, label) in enumerate(DEFAULT_DATA[category]):
            db.add(ReferenceData(category=category, value=val, label=label, sort_order=i))
        db.commit()
        items = db.query(ReferenceData).filter(
            ReferenceData.category == category
        ).order_by(ReferenceData.sort_order).all()
    return {"ok": True, "items": [
        {"id": it.id, "value": it.value, "label": it.label,
         "sort_order": it.sort_order, "enabled": it.enabled}
        for it in items
    ]}
