"""角色管理 API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Character

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharacterCreate(BaseModel):
    name: str
    role_type: str = "protagonist"
    gender: str = "male"
    personality: Optional[str] = None
    appearance_desc: Optional[str] = None
    outfit_desc: Optional[str] = None
    default_voice_id: Optional[str] = None


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


def _to_dict(c: Character) -> dict:
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}
