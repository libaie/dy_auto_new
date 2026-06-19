from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import AITextArtifact
from app.deps import require_role, verify_admin_token
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService


router = APIRouter(prefix="/api/ai-text-artifacts", tags=["ai-text-artifacts"])


class ArtifactEditRequest(BaseModel):
    content_json: dict | None = None
    content_text: str | None = None


class ArtifactRegenerateRequest(BaseModel):
    input_json: dict | None = None
    content_json: dict | None = None
    content_text: str | None = None
    model_trace_json: dict | None = None


def _actor_id(user) -> str | None:
    if isinstance(user, tuple) and user:
        return str(user[0])
    if isinstance(user, str):
        return user
    return None


def _artifact_dict(row: AITextArtifact) -> dict:
    return {
        "id": row.id,
        "series_id": row.series_id,
        "episode_id": row.episode_id,
        "run_id": row.run_id,
        "production_plan_id": row.production_plan_id,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "artifact_type": row.artifact_type,
        "version": row.version,
        "status": row.status,
        "source_type": row.source_type,
        "parent_artifact_id": row.parent_artifact_id,
        "input_json": row.input_json or {},
        "content_json": row.content_json or {},
        "content_text": row.content_text,
        "model_trace_json": row.model_trace_json or {},
        "review_trace_json": row.review_trace_json or {},
        "consumer_trace_json": row.consumer_trace_json or {},
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "superseded_at": row.superseded_at.isoformat() if row.superseded_at else None,
        "stale_reason": row.stale_reason,
    }


def _get_artifact_or_404(db: Session, artifact_id: str) -> AITextArtifact:
    artifact = db.query(AITextArtifact).filter(AITextArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(404, "AI text artifact not found")
    return artifact


@router.get("")
def list_artifacts(
    series_id: str | None = Query(None),
    episode_id: str | None = Query(None),
    artifact_type: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    query = db.query(AITextArtifact)
    if series_id:
        query = query.filter(AITextArtifact.series_id == series_id)
    if episode_id:
        query = query.filter(AITextArtifact.episode_id == episode_id)
    if artifact_type:
        query = query.filter(AITextArtifact.artifact_type == artifact_type)
    if status:
        query = query.filter(AITextArtifact.status == status)
    rows = query.order_by(AITextArtifact.created_at.desc(), AITextArtifact.version.desc()).all()
    return {"ok": True, "artifacts": [_artifact_dict(row) for row in rows]}


@router.get("/{artifact_id}")
def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    return {"ok": True, "artifact": _artifact_dict(_get_artifact_or_404(db, artifact_id))}


@router.get("/{artifact_id}/lineage")
def get_lineage(
    artifact_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    service = AITextArtifactService(db)
    try:
        rows = service.lineage(artifact_id)
    except ValueError as exc:
        if str(exc) == "artifact_not_found":
            raise HTTPException(404, "AI text artifact not found")
        raise
    return {"ok": True, "artifacts": [_artifact_dict(row) for row in rows]}


@router.post("/{artifact_id}/edit")
def edit_artifact(
    artifact_id: str,
    body: ArtifactEditRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    service = AITextArtifactService(db)
    try:
        artifact = service.edit_artifact(
            artifact_id,
            content_json=body.content_json,
            content_text=body.content_text,
            actor_user_id=_actor_id(user),
        )
    except ValueError as exc:
        if str(exc) == "artifact_not_found":
            raise HTTPException(404, "AI text artifact not found")
        raise
    return {"ok": True, "artifact": _artifact_dict(artifact)}


@router.post("/{artifact_id}/approve")
def approve_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    service = AITextArtifactService(db)
    try:
        artifact = service.approve_artifact(artifact_id, actor_user_id=_actor_id(user))
    except ValueError as exc:
        if str(exc) == "artifact_not_found":
            raise HTTPException(404, "AI text artifact not found")
        if str(exc) == "stale_artifact_version":
            raise HTTPException(409, "AI text artifact is not the latest version")
        raise
    return {"ok": True, "artifact": _artifact_dict(artifact)}


@router.post("/{artifact_id}/regenerate")
async def regenerate_artifact(
    artifact_id: str,
    body: ArtifactRegenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    service = AITextArtifactService(db)
    try:
        artifact = await service.regenerate_artifact_with_ai(
            artifact_id,
            input_json=body.input_json,
            actor_user_id=_actor_id(user),
        )
    except ValueError as exc:
        if str(exc) == "artifact_not_found":
            raise HTTPException(404, "AI text artifact not found")
        raise
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True, "artifact": _artifact_dict(artifact)}
