from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_service import (
    VideoProductionError,
    approve_asset,
    create_regenerated_image_asset,
    create_run_from_episode,
    reject_asset,
    start_asset_regeneration,
    start_compose_stage,
    start_image_stage,
    start_video_stage,
    sync_compose_stage_results,
    sync_image_stage_results,
    sync_regenerated_asset,
    sync_video_stage_results,
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


# -- Payload helpers --------------------------------------------------------

def _storyboard_frame(run: VideoProductionRun, frame_id: str) -> dict:
    for index, frame in enumerate((run.storyboard_json or {}).get("frames") or []):
        candidate = str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}")
        if candidate == frame_id:
            return frame
    return {}


def _latest_ai_review(db: Session, asset_id: str) -> dict | None:
    row = db.query(VideoReviewRecord).filter(
        VideoReviewRecord.asset_id == asset_id,
        VideoReviewRecord.review_type == "ai",
    ).order_by(VideoReviewRecord.created_at.desc()).first()
    if not row:
        return None
    return {
        "id": row.id,
        "status": row.status,
        "score": row.score,
        "criteria_json": row.criteria_json or [],
        "issues_json": row.issues_json or [],
        "model_trace_json": row.model_trace_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


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


def _asset_payload(asset: VideoProductionAsset, db: Session | None = None, run: VideoProductionRun | None = None) -> dict:
    payload = {
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
    if db and run:
        payload["storyboard_frame"] = _storyboard_frame(run, asset.frame_id)
        payload["latest_ai_review"] = _latest_ai_review(db, asset.id)
        payload["model_trace_json"] = run.model_trace_json or {}
    return payload


# -- Run CRUD ---------------------------------------------------------------

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


# -- Review items -----------------------------------------------------------

@router.get("/review-items")
def review_items(
    run_id: str | None = None,
    status: str = "review_pending",
    series_id: str | None = None,
    episode_id: str | None = None,
    stage: str | None = None,
    asset_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    query = db.query(VideoProductionAsset)
    if run_id:
        query = query.filter(VideoProductionAsset.run_id == run_id)
    if status:
        query = query.filter(VideoProductionAsset.status == status)
    if series_id:
        query = query.join(VideoProductionRun, VideoProductionAsset.run_id == VideoProductionRun.id).filter(
            VideoProductionRun.series_id == series_id
        )
    if episode_id:
        query = query.filter(VideoProductionAsset.episode_id == episode_id)
    if stage:
        query = query.filter(VideoProductionAsset.stage == stage)
    if asset_type:
        query = query.filter(VideoProductionAsset.asset_type == asset_type)

    query = query.order_by(VideoProductionAsset.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    run_ids = {item.run_id for item in items}
    runs_by_id = {
        run.id: run
        for run in db.query(VideoProductionRun).filter(VideoProductionRun.id.in_(run_ids)).all()
    } if run_ids else {}

    return {
        "ok": True,
        "items": [_asset_payload(item, db=db, run=runs_by_id.get(item.run_id)) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# -- Human review actions ---------------------------------------------------

@router.post("/assets/{asset_id}/review")
def review_asset(
    asset_id: str,
    body: ReviewAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    reviewer_id = user[0] if isinstance(user, tuple) else None
    try:
        if body.action == "approve":
            asset = approve_asset(db, asset_id, reviewer_user_id=reviewer_id, comment=body.comment)
        elif body.action == "reject":
            asset = reject_asset(db, asset_id, reviewer_user_id=reviewer_id, comment=body.comment)
        else:
            raise HTTPException(400, f"Unknown action: {body.action}")
    except VideoProductionError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


# -- Image stage ------------------------------------------------------------

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


# -- Video segment stage ----------------------------------------------------

@router.post("/runs/{run_id}/start-videos")
async def start_videos(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = await start_video_stage(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.post("/runs/{run_id}/sync-video-results")
async def sync_videos(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        assets = await sync_video_stage_results(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "assets": [_asset_payload(asset) for asset in assets]}


# -- Compose stage ----------------------------------------------------------

@router.post("/runs/{run_id}/compose")
async def compose_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = await start_compose_stage(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.post("/runs/{run_id}/sync-compose-results")
async def sync_compose(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = await sync_compose_stage_results(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


# -- Regeneration -----------------------------------------------------------

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


@router.post("/assets/{asset_id}/start-regeneration")
async def start_regeneration(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = await start_asset_regeneration(db, asset_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


@router.post("/assets/{asset_id}/sync-regeneration")
async def sync_regeneration(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = await sync_regenerated_asset(db, asset_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
