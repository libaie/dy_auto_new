"""场景管理 API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Scene

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


class SceneCreate(BaseModel):
    name: str
    scene_type: str = "indoor"
    location_desc: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None


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


def _to_dict(s: Scene) -> dict:
    return {col.name: getattr(s, col.name) for col in Scene.__table__.columns}
