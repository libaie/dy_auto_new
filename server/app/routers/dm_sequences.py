"""DM 私信序列模板 CRUD API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, require_role, verify_device_secret
from app.db_models import DMSequence

router = APIRouter(prefix="/api/dm-sequences", tags=["dm-sequences"])


class SequenceMessage(BaseModel):
    order: int
    content: str = Field(..., min_length=1, max_length=500)
    delay_ms: int = Field(default=0, ge=0, le=60000)


class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    messages: list[SequenceMessage] = Field(..., min_length=1)
    industry: Optional[str] = None


class SequenceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    messages: Optional[list[SequenceMessage]] = Field(default=None, min_length=1)
    industry: Optional[str] = None


def _to_dict(s: DMSequence) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "messages": s.messages,
        "message_count": len(s.messages),
        "industry": s.industry or "",
        "created_at": str(s.created_at) if s.created_at else None,
        "updated_at": str(s.updated_at) if s.updated_at else None,
    }


def _to_device_dict(s: DMSequence) -> dict:
    """Device-facing: only id + messages, minimal payload."""
    return {"id": s.id, "messages": s.messages}


@router.get("")
def list_sequences(
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    query = db.query(DMSequence)
    if industry:
        query = query.filter(DMSequence.industry == industry)
    sequences = query.order_by(DMSequence.updated_at.desc()).all()
    return {"sequences": [_to_dict(s) for s in sequences]}


@router.post("")
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    # Auto-renumber: sort by order, assign 1,2,3...
    sorted_msgs = sorted(
        [{"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
         for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))],
        key=lambda x: x["order"],
    )
    seq = DMSequence(
        name=body.name,
        messages=sorted_msgs,
        industry=body.industry or None,
    )
    db.add(seq)
    db.commit()
    db.refresh(seq)
    return _to_dict(seq)


@router.get("/{sequence_id}")
def get_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    return _to_dict(seq)


@router.put("/{sequence_id}")
def update_sequence(
    sequence_id: str,
    body: SequenceUpdate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")

    if body.name is not None:
        seq.name = body.name
    if body.messages is not None:
        seq.messages = [
            {"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
            for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))
        ]
    if body.industry is not None:
        seq.industry = body.industry or None

    db.commit()
    db.refresh(seq)
    return _to_dict(seq)


@router.delete("/{sequence_id}")
def delete_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    db.delete(seq)
    db.commit()
    return {"deleted": True, "id": sequence_id}


@router.get("/device/sync")
def device_sync(
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """设备端同步全量 DM 序列模板（用于 poll 响应或独立拉取）"""
    sequences = db.query(DMSequence).all()
    return {"dm_sequences": [_to_device_dict(s) for s in sequences]}
