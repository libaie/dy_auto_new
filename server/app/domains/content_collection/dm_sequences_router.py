"""DM sequence template API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, verify_admin_token, verify_device_secret
from app.domains.content_collection import mutations


router = APIRouter(prefix="/api/dm-sequences", tags=["dm-sequences"])
random = mutations.random
_ORIGINAL_VARIANT_DELAY_MS = mutations._variant_delay_ms


def _variant_delay_ms() -> int:
    return _ORIGINAL_VARIANT_DELAY_MS()


def _sync_legacy_monkeypatch_hooks():
    mutations.random = random
    mutations._variant_delay_ms = _variant_delay_ms


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
    variants: Optional[list] = None


class DMSequenceGenerateRequest(BaseModel):
    industry: str = Field(default="general", description="行业key: health/beauty/education/travel/secondhand/general")
    description: str = Field(..., min_length=5, max_length=500, description="大白话描述")
    link_url: str = Field(..., min_length=5, max_length=500, description="消息2的短链URL")


class VariantsGenerateRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=20, description="生成变体套数")


@router.get("")
def list_sequences(
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    return mutations.list_dm_sequences(db, user, industry=industry)


@router.post("")
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    return mutations.create_dm_sequence(db, user, body)


@router.get("/{sequence_id}")
def get_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    return mutations.get_dm_sequence(db, user, sequence_id)


@router.put("/{sequence_id}")
def update_sequence(
    sequence_id: str,
    body: SequenceUpdate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    return mutations.update_dm_sequence(db, user, sequence_id, body)


@router.delete("/{sequence_id}")
def delete_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    return mutations.delete_dm_sequence(db, user, sequence_id)


@router.post("/generate")
async def generate_dm_sequence(
    body: DMSequenceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    return StreamingResponse(
        await mutations.generate_dm_sequence_events(db, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{seq_id}/variants")
async def generate_variants(
    seq_id: str,
    body: VariantsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    _sync_legacy_monkeypatch_hooks()
    return await mutations.generate_dm_variants(db, seq_id, body)


@router.get("/device/sync")
def device_sync(
    db: Session = Depends(get_db),
    device_id: Optional[str] = Depends(verify_device_secret),
):
    _sync_legacy_monkeypatch_hooks()
    return mutations.device_sync_dm_sequences(db, device_id)
