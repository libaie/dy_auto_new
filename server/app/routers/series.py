"""系列 + 剧集管理 API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Series, Episode, Character, Scene

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
                  _: str = Depends(verify_admin_token)):
    s = Series(**body.model_dump())
    db.add(s)
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
                  _: str = Depends(verify_admin_token)):
    db.query(Series).filter(Series.id == series_id).delete()
    db.commit()
    return {"ok": True}

# === M2M 关联 ===

@router.post("/{series_id}/characters/{character_id}")
def link_character(series_id: str, character_id: str, db: Session = Depends(get_db),
                   _: str = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    c = db.query(Character).filter(Character.id == character_id).first()
    if not s or not c:
        raise HTTPException(404, "Series or Character not found")
    s.characters.append(c)
    db.commit()
    return {"ok": True}

@router.post("/{series_id}/scenes/{scene_id}")
def link_scene(series_id: str, scene_id: str, db: Session = Depends(get_db),
               _: str = Depends(verify_admin_token)):
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
                   db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    ep = db.query(Episode).filter(
        Episode.id == episode_id, Episode.series_id == series_id
    ).first()
    if not ep:
        raise HTTPException(404, "Episode not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ep, k, v)
    db.commit()
    return {"ok": True}
