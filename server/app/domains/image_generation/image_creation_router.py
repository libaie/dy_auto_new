from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import quote, unquote

import httpx
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import PIXELLE_API_KEY
from app.database import get_db
from app.deps import require_role
from app.domains.image_generation.image_creation_errors import image_error
from app.domains.image_generation.image_creation_storage import configured_public_base_url, save_upload
from app.services.image_creation_service import (
    asset_payload,
    create_image_task,
    dispatch_queued_image_task,
    ensure_image_asset_action_allowed,
    list_image_assets,
    review_image_asset,
    review_payload,
    sync_image_task,
    task_payload,
)
from app.services.pixelle_client import _get_base_url


router = APIRouter(prefix="/api/image-creation", tags=["image-creation"])


class CreateImageTaskRequest(BaseModel):
    mode: str
    prompt: str
    negative_prompt: str = ""
    source: dict | None = None
    source_url: str | None = None
    source_asset_id: str | None = None
    reference_images: list[dict] = Field(default_factory=list)
    size: str | None = None
    count: int = 1
    output_format: str | None = None
    response_format: str | None = None
    watermark: bool | None = None
    provider_options: dict = Field(default_factory=dict)
    idempotency_key: str | None = None
    destination_role: str | None = None
    destination_context: dict = Field(default_factory=dict)
    cost_confirmation: bool = False
    series_id: str | None = None
    episode_id: str | None = None
    model_id: str | None = None
    strategy_id: str | None = None
    strategy_version: int | None = None
    selection_preview_id: str | None = None
    selection_preview_request_hash: str | None = None


class ReviewImageAssetRequest(BaseModel):
    action: str
    comment: str = ""
    asset_version: int = Field(..., ge=1)
    report_json: dict = Field(default_factory=dict)


class EditImageAssetRequest(BaseModel):
    prompt: str
    action: str = "repaint"
    asset_version: int | None = Field(None, ge=1)
    negative_prompt: str = ""
    reference_images: list[dict] = Field(default_factory=list)
    size: str | None = None
    count: int = 1
    output_format: str | None = None
    response_format: str | None = None
    watermark: bool | None = None
    provider_options: dict = Field(default_factory=dict)
    idempotency_key: str | None = None
    destination_role: str | None = None
    destination_context: dict = Field(default_factory=dict)
    cost_confirmation: bool = False
    series_id: str | None = None
    episode_id: str | None = None
    model_id: str | None = None
    strategy_id: str | None = None
    strategy_version: int | None = None
    selection_preview_id: str | None = None
    selection_preview_request_hash: str | None = None


@router.post("/uploads")
async def upload_image(file: UploadFile = File(...), user=Depends(require_role("admin"))):
    try:
        saved = await save_upload(file, configured_public_base_url())
    except ValueError as exc:
        error_code = str(exc)
        if error_code == "SOURCE_IMAGE_TOO_LARGE":
            raise image_error(413, error_code, "Upload exceeds the 30MB image limit.", "Choose a smaller image.")
        raise image_error(
            400,
            "SOURCE_IMAGE_UNSUPPORTED_TYPE",
            "Upload must be jpeg, png, webp, bmp, tiff, or gif.",
            "Choose a supported image file.",
            retryable=False,
        )
    return {"ok": True, **saved}


@router.get("/pixelle-files/{file_path:path}")
async def pixelle_file(file_path: str, db: Session = Depends(get_db)):
    clean = unquote(file_path).lstrip("/")
    if not clean or ".." in PurePosixPath(clean).parts:
        raise image_error(
            400,
            "PIXELLE_FILE_PATH_INVALID",
            "Pixelle file path is invalid.",
            "Reload the generated asset.",
            retryable=False,
        )
    if not clean.startswith("output/"):
        raise image_error(
            403,
            "PIXELLE_FILE_PATH_FORBIDDEN",
            "Pixelle file proxy only allows generated output files.",
            "Reload the generated asset.",
            retryable=False,
        )
    headers = {"X-API-Key": PIXELLE_API_KEY} if PIXELLE_API_KEY else {}
    try:
        async with httpx.AsyncClient(base_url=_get_base_url(db), timeout=httpx.Timeout(60, connect=5), trust_env=False) as client:
            resp = await client.get(f"/api/files/{quote(clean, safe='/')}", headers=headers)
    except httpx.TimeoutException as exc:
        raise image_error(504, "PIXELLE_FILE_TIMEOUT", "Pixelle file proxy timed out.", "Try again later.") from exc
    except httpx.RequestError as exc:
        raise image_error(502, "PIXELLE_FILE_PROXY_FAILED", "Pixelle file proxy failed.", "Check Pixelle service status.") from exc
    if resp.status_code == 404:
        raise image_error(404, "PIXELLE_FILE_NOT_FOUND", "Pixelle file was not found.", "Regenerate or sync the task again.", retryable=False)
    if resp.status_code >= 400:
        raise image_error(resp.status_code, "PIXELLE_FILE_PROXY_FAILED", "Pixelle file proxy failed.", "Check Pixelle service status.")
    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type") or "application/octet-stream",
        headers={"cache-control": "public, max-age=3600"},
    )


@router.post("/tasks")
async def create_task(body: CreateImageTaskRequest, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    payload = body.model_dump()
    if isinstance(user, tuple):
        payload["user_id"] = user[0]
    task = await create_image_task(db, payload)
    return {"ok": True, "task": task_payload(task), "assets": [], "reviews": []}


@router.get("/tasks/{task_id}")
async def read_task(task_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    from app.db_models import ImageCreationAsset, ImageCreationTask

    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()
    if not task:
        raise image_error(404, "IMAGE_TASK_NOT_FOUND", "Image creation task not found.", "Reload the task list.", retryable=False)
    assets = db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id == task.id).all()
    return {"ok": True, "task": task_payload(task), "assets": [asset_payload(asset) for asset in assets], "reviews": []}


@router.post("/tasks/{task_id}/sync")
async def sync_task(task_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    from app.db_models import ImageCreationAsset

    task = await sync_image_task(db, task_id)
    task_assets = db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id == task.id).all()
    return {"ok": True, "task": task_payload(task), "assets": [asset_payload(asset) for asset in task_assets]}


@router.post("/tasks/{task_id}/dispatch")
async def dispatch_task(task_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    task = await dispatch_queued_image_task(db, task_id)
    return {"ok": True, "task": task_payload(task), "assets": []}


@router.get("/assets")
async def assets(
    status: str | None = Query(None),
    destination_role: str | None = Query(None),
    series_id: str | None = Query(None),
    episode_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    rows, total = list_image_assets(
        db,
        status=status,
        destination_role=destination_role,
        series_id=series_id,
        episode_id=episode_id,
        page=page,
        page_size=page_size,
    )
    return {"ok": True, "assets": [asset_payload(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.post("/assets/{asset_id}/review")
async def review_asset(asset_id: str, body: ReviewImageAssetRequest, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    asset, reviews = review_image_asset(
        db,
        asset_id,
        body.action,
        body.comment,
        asset_version=body.asset_version,
        report_json=body.report_json,
    )
    return {"ok": True, "asset": asset_payload(asset), "reviews": [review_payload(review) for review in reviews]}


@router.post("/assets/{asset_id}/edit")
async def edit_asset(asset_id: str, body: EditImageAssetRequest, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    from app.db_models import ImageCreationAsset

    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset:
        raise image_error(
            404,
            "SOURCE_ASSET_NOT_FOUND",
            "Source image asset was not found.",
            "Choose another source asset or upload a source image.",
            retryable=False,
            affected_ids=[asset_id],
        )

    ensure_image_asset_action_allowed(asset, body.action, body.asset_version)

    payload = body.model_dump()
    if isinstance(user, tuple):
        payload["user_id"] = user[0]
    payload["mode"] = "image_to_image"
    payload["source"] = {"type": "asset", "asset_id": asset.id, "url": asset.url}
    if not payload.get("series_id"):
        payload["series_id"] = asset.series_id
    if not payload.get("episode_id"):
        payload["episode_id"] = asset.episode_id

    task = await create_image_task(db, payload)
    if body.action == "repaint":
        asset.status = "regenerating"
        db.commit()
    db.refresh(task)
    return {"ok": True, "task": task_payload(task)}
