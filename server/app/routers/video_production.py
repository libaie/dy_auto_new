from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import (
    VideoProductionError,
    approve_asset,
    create_regenerated_image_asset,
    create_run_from_episode,
    latest_assets_by_frame,
    start_image_stage,
    sync_image_stage_results,
)

router = APIRouter(prefix="/api/video-production", tags=["video-production"])


class CreateRunRequest(BaseModel):
    series_id: str
    episode_id: str


class ReviewAssetRequest(BaseModel):
    action: str
    comment: str = ""


class RegenerateAssetRequest(BaseModel):
    url: str
    local_path: str = ""
    thumbnail_url: str = ""
    metadata: dict = {}
    pixelle_task_id: str | None = None


def _run_payload(run: VideoProductionRun) -> dict:
    return {
        "id": run.id,
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "pixelle_stage_task_id": run.pixelle_stage_task_id,
        "storyboard_json": run.storyboard_json or {},
        "model_trace_json": run.model_trace_json or {},
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def _asset_payload(asset: VideoProductionAsset) -> dict:
    return {
        "id": asset.id,
        "run_id": asset.run_id,
        "episode_id": asset.episode_id,
        "frame_id": asset.frame_id,
        "asset_type": asset.asset_type,
        "stage": asset.stage,
        "url": asset.url,
        "local_path": asset.local_path,
        "thumbnail_url": asset.thumbnail_url,
        "duration_seconds": asset.duration_seconds,
        "version": asset.version,
        "metadata_json": asset.metadata_json or {},
        "status": asset.status,
        "pixelle_task_id": asset.pixelle_task_id,
    }


@router.post("/runs")
def create_run(
    body: CreateRunRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = create_run_from_episode(db, body.series_id, body.episode_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    assets = db.query(VideoProductionAsset).filter(VideoProductionAsset.run_id == run.id).all()
    return {"ok": True, "run": _run_payload(run), "assets": [_asset_payload(a) for a in assets]}


@router.get("/review-items")
def review_items(
    run_id: str | None = None,
    status: str = "review_pending",
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    query = db.query(VideoProductionAsset).filter(VideoProductionAsset.status == status)
    if run_id:
        query = query.filter(VideoProductionAsset.run_id == run_id)
    items = query.order_by(VideoProductionAsset.created_at.desc()).limit(100).all()
    return {"ok": True, "items": [_asset_payload(item) for item in items]}


@router.post("/assets/{asset_id}/review")
def review_asset(
    asset_id: str,
    body: ReviewAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    reviewer_id = user[0] if isinstance(user, tuple) else None
    if body.action != "approve":
        raise HTTPException(400, "Only approve is implemented in the image wedge")
    try:
        asset = approve_asset(db, asset_id, reviewer_user_id=reviewer_id, comment=body.comment)
    except VideoProductionError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


@router.post("/runs/{run_id}/start-images")
async def start_images(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = await start_image_stage(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.post("/runs/{run_id}/sync-image-results")
async def sync_images(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        assets = await sync_image_stage_results(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "assets": [_asset_payload(asset) for asset in assets]}


@router.post("/assets/{asset_id}/regenerate")
def regenerate_asset(
    asset_id: str,
    body: RegenerateAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = create_regenerated_image_asset(db, asset_id, body.model_dump())
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
