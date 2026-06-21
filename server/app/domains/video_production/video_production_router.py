"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 video_production_router 相关业务规则、状态转换和外部系统边界。
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps import require_role
from app.config import PIXELLE_CONFIG_PATH
from app.db.models.video_production import (
    ProviderCostReservation,
    ProviderStageTask,
    ProductionEpisode,
    ProductionPlan,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError, to_http_detail
from app.domains.video_production.production_review_service import apply_bulk_review_action
from app.domains.video_production.production_segment_service import retry_segment
from app.domains.video_production.production_tree_service import get_run_tree
from app.domains.video_production.review_asset_edit_service import (
    ReviewAssetEditError,
    edit_image_asset,
    void_asset_version,
)
from app.domains.video_production.mock_scale_scheduler_service import advance_mock_scheduler
from app.domains.video_production.one_sentence_video_service import (
    complete_one_sentence_reference_generation,
    create_one_sentence_video,
)
from app.domains.video_production.video_production_readiness import build_run_readiness
from app.domains.video_production.video_production_run_types import LEGACY_EPISODE_RUN, MOCK_SERIES_SCALE, REAL_SHORT_E2E, get_run_type
from app.domains.video_production.video_production_service import (
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

DEFAULT_REVIEW_ITEM_STATUSES = ("review_pending", "failed", "regenerating", "rejected")


class CreateRunRequest(BaseModel):
    """业务类：承载 CreateRunRequest 相关的数据结构、状态或业务协作。"""
    series_id: str
    episode_id: str


class StartRunRequest(BaseModel):
    """业务类：承载 StartRunRequest 相关的数据结构、状态或业务协作。"""
    series_id: str
    episode_id: str
    target_duration_seconds: int | None = None
    budget_limit: float | None = None
    autostart_images: bool = True
    run_type: str = LEGACY_EPISODE_RUN
    auto_repair_policy: dict | None = None


class OneSentenceVideoRequest(BaseModel):
    """业务类：承载 OneSentenceVideoRequest 相关的数据结构、状态或业务协作。"""
    prompt: str = Field(..., min_length=4, max_length=2000)
    title: str | None = None
    genre: str = "drama"
    target_duration_seconds: int = Field(60, ge=5, le=28800)
    budget_limit: float | None = None
    autostart_images: bool = True
    run_type: str = REAL_SHORT_E2E
    auto_repair_policy: dict | None = None


class ReviewAssetRequest(BaseModel):
    """业务类：承载 ReviewAssetRequest 相关的数据结构、状态或业务协作。"""
    action: str
    comment: str = ""


class VoidAssetRequest(BaseModel):
    """业务类：承载 VoidAssetRequest 相关的数据结构、状态或业务协作。"""
    comment: str = ""
    expected_version: int | None = None


class ImageEditRequest(BaseModel):
    """业务类：承载 ImageEditRequest 相关的数据结构、状态或业务协作。"""
    instruction: str = Field(..., min_length=1, max_length=2000)
    expected_version: int | None = None


class RegenerateAssetRequest(BaseModel):
    """业务类：承载 RegenerateAssetRequest 相关的数据结构、状态或业务协作。"""
    url: str
    source_url: str | None = None
    local_path: str = ""
    thumbnail_url: str = ""
    storage_path: str | None = None
    checksum: str | None = None
    copy_status: str | None = None
    size_bytes: int | None = None
    metadata: dict = {}
    pixelle_task_id: str | None = None


class BulkReviewActionRequest(BaseModel):
    """业务类：承载 BulkReviewActionRequest 相关的数据结构、状态或业务协作。"""
    asset_ids: list[str]
    action: str
    comment: str = ""


class MockWorkerStepRequest(BaseModel):
    """业务类：承载 MockWorkerStepRequest 相关的数据结构、状态或业务协作。"""
    lease_id: str = "manual-worker"
    batch_size: int = Field(1, ge=1, le=100)


class RealWorkerStepRequest(BaseModel):
    """业务类：承载 RealWorkerStepRequest 相关的数据结构、状态或业务协作。"""
    lease_id: str = "manual-real-worker"
    batch_size: int = Field(1, ge=1, le=100)
    async_mode: bool = False


class CreateCollectionRequest(BaseModel):
    """业务类：承载 CreateCollectionRequest 相关的数据结构、状态或业务协作。"""
    series_id: str


# -- Payload helpers --------------------------------------------------------

def _storyboard_frame(run: VideoProductionRun, frame_id: str) -> dict:
    """业务函数：处理 _storyboard_frame 对应的业务流程、校验或数据转换。"""
    for index, frame in enumerate((run.storyboard_json or {}).get("frames") or []):
        candidate = str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}")
        if candidate == frame_id:
            return frame
    return {}


def _reference_evidence_from_storyboard(frame: dict | None) -> dict:
    """业务函数：处理 _reference_evidence_from_storyboard 对应的业务流程、校验或数据转换。"""
    frame = frame or {}
    return {
        "reference_urls": frame.get("reference_urls") or [],
        "character_ids": frame.get("character_ids") or [],
        "scene_id": frame.get("scene_id"),
        "continuity_notes": frame.get("continuity_notes"),
        "image_prompt": frame.get("image_prompt"),
        "character_reference_urls": frame.get("character_reference_urls") or [],
        "style_reference_urls": frame.get("style_reference_urls") or [],
        "missing": [],
    }


def _series_payload(series) -> dict:
    """业务函数：处理 _series_payload 对应的业务流程、校验或数据转换。"""
    return {
        "id": series.id,
        "title": series.title,
        "logline": series.logline,
        "genre": series.genre,
        "target_duration": series.target_duration,
        "status": series.status,
    }


def _episode_payload(episode) -> dict:
    """业务函数：处理 _episode_payload 对应的业务流程、校验或数据转换。"""
    return {
        "id": episode.id,
        "series_id": episode.series_id,
        "episode_number": episode.episode_number,
        "title": episode.title,
        "status": episode.status,
        "storyboard_json": episode.storyboard_json,
        "video_url": episode.video_url,
        "duration_seconds": episode.duration_seconds,
    }


def _latest_ai_review(db: Session, asset_id: str) -> dict | None:
    """业务函数：处理 _latest_ai_review 对应的业务流程、校验或数据转换。"""
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


def _run_payload(run: VideoProductionRun, db: Session | None = None) -> dict:
    """业务函数：处理 _run_payload 对应的业务流程、校验或数据转换。"""
    payload = {
        "id": run.id,
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "run_type": get_run_type(run),
        "status": run.status,
        "current_stage": run.current_stage,
        "pixelle_stage_task_id": run.pixelle_stage_task_id,
        "production_plan_id": run.production_plan_id,
        "production_episode_id": run.production_episode_id,
        "production_link_status": run.production_link_status,
        "storyboard_json": run.storyboard_json or {},
        "model_trace_json": run.model_trace_json or {},
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }
    if db is not None:
        from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

        payload["consumed_text_artifacts"] = AITextArtifactService(db).consumed_artifacts_for_run(run.id)
    else:
        payload["consumed_text_artifacts"] = []
    return payload


def _asset_payload(asset: VideoProductionAsset, db: Session | None = None, run: VideoProductionRun | None = None) -> dict:
    """业务函数：处理 _asset_payload 对应的业务流程、校验或数据转换。"""
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
        "source_url": asset.source_url,
        "storage_path": asset.storage_path,
        "copy_status": asset.copy_status,
        "checksum": asset.checksum,
        "size_bytes": asset.size_bytes,
        "production_segment_id": asset.production_segment_id,
        "storage_error_json": asset.storage_error_json or {},
        "permission": {
            "can_approve": (
                asset.copy_status == "persisted"
                and bool(asset.checksum)
                and bool(asset.storage_path)
                and asset.status == "review_pending"
            ),
        },
    }
    if db and run:
        storyboard_frame = _storyboard_frame(run, asset.frame_id)
        payload["storyboard_frame"] = storyboard_frame
        payload["reference_evidence"] = _reference_evidence_from_storyboard(storyboard_frame)
        payload["latest_ai_review"] = _latest_ai_review(db, asset.id)
        payload["model_trace_json"] = run.model_trace_json or {}
    return payload


def _production_segment_payload(segment) -> dict:
    """业务函数：处理 _production_segment_payload 对应的业务流程、校验或数据转换。"""
    return {
        "id": segment.id,
        "segment_id": segment.segment_id,
        "version": segment.version,
        "status": segment.status,
    }


def _review_item_status_filters(status: str | None, statuses: list[str] | None) -> list[str] | None:
    """业务函数：处理 _review_item_status_filters 对应的业务流程、校验或数据转换。"""
    if statuses:
        values = []
        for item in statuses:
            values.extend(part.strip() for part in item.split(",") if part.strip())
        return values or None
    if status is not None:
        status = status.strip()
        return [status] if status else None
    return list(DEFAULT_REVIEW_ITEM_STATUSES)


def _bounded_page(page: int, page_size: int, *, max_page_size: int = 100) -> tuple[int, int]:
    """业务函数：处理 _bounded_page 对应的业务流程、校验或数据转换。"""
    return max(1, int(page or 1)), min(max(1, int(page_size or 50)), max_page_size)


def _asset_summary(db: Session, run_id: str) -> dict:
    """业务函数：处理 _asset_summary 对应的业务流程、校验或数据转换。"""
    rows = (
        db.query(
            VideoProductionAsset.asset_type,
            VideoProductionAsset.status,
            func.count(VideoProductionAsset.id),
        )
        .filter(VideoProductionAsset.run_id == run_id)
        .group_by(VideoProductionAsset.asset_type, VideoProductionAsset.status)
        .all()
    )
    summary = {}
    for asset_type, status, count in rows:
        summary.setdefault(asset_type, {})[status] = count
    return summary


def _mock_worker_error(code: ProductionErrorCode, run_id: str) -> ProductionRepairableError:
    """业务函数：处理 _mock_worker_error 对应的业务流程、校验或数据转换。"""
    if code == ProductionErrorCode.RUN_NOT_FOUND:
        return ProductionRepairableError(
            code=code,
            message="Video production run was not found.",
            cause="run_not_found",
            repair_action="Choose an existing production run.",
            repair_route="/video-production",
            affected_ids=[run_id],
        )
    return ProductionRepairableError(
        code=code,
        message="Mock worker steps only accept mock_series_scale runs.",
        cause="invalid_run_type",
        repair_action="Use a mock_series_scale run or start the real provider stages instead.",
        repair_route=f"/video-production/{run_id}",
        affected_ids=[run_id],
    )


def _review_gate_counts(db: Session, run_id: str | None) -> dict[str, int]:
    """业务函数：处理 _review_gate_counts 对应的业务流程、校验或数据转换。"""
    counts = {"image": 0, "video_segment": 0, "final_video": 0}
    if not run_id:
        return counts
    rows = (
        db.query(VideoProductionAsset.asset_type)
        .filter(
            VideoProductionAsset.run_id == run_id,
            VideoProductionAsset.asset_type.in_(tuple(counts.keys())),
            VideoProductionAsset.status == "review_pending",
            VideoProductionAsset.is_latest.is_(True),
        )
        .all()
    )
    for (asset_type,) in rows:
        counts[asset_type] += 1
    return counts


def _provider_stage_task_payload(task: ProviderStageTask, reservation: ProviderCostReservation | None = None) -> dict:
    """业务函数：处理 _provider_stage_task_payload 对应的业务流程、校验或数据转换。"""
    payload = {
        "id": task.id,
        "run_id": task.run_id,
        "plan_id": task.plan_id,
        "job_id": task.job_id,
        "target_type": task.target_type,
        "target_id": task.target_id,
        "stage": task.stage,
        "provider": task.provider,
        "model_name": task.model_name,
        "status": task.status,
        "provider_task_id": task.provider_task_id,
        "external_task_id": task.external_task_id,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "response_summary_json": task.response_summary_json or {},
        "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }
    if reservation:
        payload["cost_reservation"] = {
            "id": reservation.id,
            "status": reservation.status,
            "estimated_cost": reservation.estimated_cost,
            "reserved_cost": reservation.reserved_cost,
            "actual_cost": reservation.actual_cost,
            "currency": reservation.currency,
            "expires_at": reservation.expires_at.isoformat() if reservation.expires_at else None,
            "submitted_at": reservation.submitted_at.isoformat() if reservation.submitted_at else None,
            "settled_at": reservation.settled_at.isoformat() if reservation.settled_at else None,
        }
    else:
        payload["cost_reservation"] = None
    return payload


# -- Run CRUD ---------------------------------------------------------------

@router.post("/runs")
def create_run(
    body: CreateRunRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 create_run 对应的业务流程、校验或数据转换。"""
    try:
        run = create_run_from_episode(db, body.series_id, body.episode_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run, db)}


@router.post("/runs/start")
async def start_run(
    body: StartRunRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 start_run 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_run_service import start_episode_production

    try:
        run = await start_episode_production(
            db,
            series_id=body.series_id,
            episode_id=body.episode_id,
            target_duration_seconds=body.target_duration_seconds,
            budget_limit=body.budget_limit,
            autostart_images=body.autostart_images,
            run_type=body.run_type,
            auto_repair_policy=body.auto_repair_policy,
            prepare_text_artifacts=True,
        )
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run, db), "route": f"/video-production/{run.id}"}


@router.post("/one-sentence")
async def one_sentence_video(
    body: OneSentenceVideoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 one_sentence_video 对应的业务流程、校验或数据转换。"""
    try:
        result = await create_one_sentence_video(
            db,
            prompt=body.prompt,
            title=body.title,
            genre=body.genre,
            target_duration_seconds=body.target_duration_seconds,
            budget_limit=body.budget_limit,
            autostart_images=body.autostart_images,
            run_type=body.run_type,
            auto_repair_policy=body.auto_repair_policy,
        )
    except ProductionRepairableError as exc:
        if exc.code == ProductionErrorCode.INVALID_RUN_TYPE:
            raise HTTPException(400, to_http_detail(exc))
        raise HTTPException(409, to_http_detail(exc))
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    if result.get("background_reference_pending"):
        background_tasks.add_task(
            _complete_one_sentence_reference_background,
            result["run"].id,
            body.autostart_images,
        )
    return {
        "ok": True,
        "series": _series_payload(result["series"]),
        "episode": _episode_payload(result["episode"]),
        "run": _run_payload(result["run"], db),
        "steps": result["steps"],
        "agency_trace_status": result.get("agency_trace_status", "partial"),
        "agency_trace": result.get("agency_trace", {}),
        "background_reference_pending": bool(result.get("background_reference_pending")),
        "route": f"/video-production/{result['run'].id}",
    }


def _complete_one_sentence_reference_background(run_id: str, autostart_images: bool) -> None:
    """业务函数：处理 _complete_one_sentence_reference_background 对应的业务流程、校验或数据转换。"""
    db = SessionLocal()
    try:
        _run_async_service(complete_one_sentence_reference_generation(
            db,
            run_id,
            autostart_images=autostart_images,
        ))
    finally:
        db.close()


def _run_async_service(coro):
    """业务函数：处理 _run_async_service 对应的业务流程、校验或数据转换。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 get_run 对应的业务流程、校验或数据转换。"""
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return {"ok": True, "run": _run_payload(run, db), "asset_summary": _asset_summary(db, run.id)}


@router.post("/runs/{run_id}/backfill-text-artifacts")
def backfill_run_text_artifacts(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 backfill_run_text_artifacts 对应的业务流程、校验或数据转换。"""
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    consumed = AITextArtifactService(db).backfill_run_text_artifacts(run_id)
    db.refresh(run)
    return {"ok": True, "run": _run_payload(run, db), "consumed_text_artifacts": consumed}


@router.post("/runs/{run_id}/mock-worker-step")
def mock_worker_step(
    run_id: str,
    body: MockWorkerStepRequest = MockWorkerStepRequest(),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 mock_worker_step 对应的业务流程、校验或数据转换。"""
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, to_http_detail(_mock_worker_error(ProductionErrorCode.RUN_NOT_FOUND, run_id)))
    if get_run_type(run) != MOCK_SERIES_SCALE:
        raise HTTPException(400, to_http_detail(_mock_worker_error(ProductionErrorCode.INVALID_RUN_TYPE, run_id)))
    result = advance_mock_scheduler(db, run_id, limit=body.batch_size, lease_id=body.lease_id)
    return {
        "ok": True,
        "lease_id": body.lease_id,
        "run": _run_payload(result["run"], db),
        "processed": result["processed"],
        "remaining": result["remaining"],
        "open_jobs": result["open_jobs"],
        "completed": result["completed"],
    }


@router.post("/runs/{run_id}/worker-step")
def real_worker_step(
    run_id: str,
    body: RealWorkerStepRequest = RealWorkerStepRequest(),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 real_worker_step 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_worker_service import run_real_worker_step

    if body.async_mode:
        background_tasks.add_task(_run_real_worker_step_background, run_id, body.lease_id, body.batch_size)
        return {
            "ok": True,
            "status": "accepted",
            "lease_id": body.lease_id,
            "run_id": run_id,
            "batch_size": body.batch_size,
        }

    try:
        return run_real_worker_step(db, run_id, lease_id=body.lease_id, batch_size=body.batch_size)
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    except ValueError as exc:
        message = str(exc)
        if message == "Run not found":
            raise HTTPException(404, str(exc))
        error = ProductionRepairableError(
            code=ProductionErrorCode.RUN_LINK_MISSING,
            message=message,
            cause="worker_step_value_error",
            repair_action="Repair the linked production run state before retrying the worker step.",
            repair_route=f"/video-production/{run_id}",
            retryable=True,
            affected_ids=[run_id],
        )
        raise HTTPException(409, to_http_detail(error))


def _run_real_worker_step_background(run_id: str, lease_id: str, batch_size: int) -> None:
    """业务函数：处理 _run_real_worker_step_background 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_worker_service import run_real_worker_step

    db = SessionLocal()
    try:
        run_real_worker_step(db, run_id, lease_id=lease_id, batch_size=batch_size)
    finally:
        db.close()


@router.get("/runs/{run_id}/readiness")
def get_run_readiness(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 get_run_readiness 对应的业务流程、校验或数据转换。"""
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        error = ProductionRepairableError(
            code=ProductionErrorCode.RUN_NOT_FOUND,
            message="Video production run was not found.",
            cause="run_not_found",
            repair_action="Choose an existing production run.",
            repair_route="/video-production",
            affected_ids=[run_id],
        )
        raise HTTPException(404, to_http_detail(error))
    return {"ok": True, "readiness": build_run_readiness(db, run)}


@router.get("/runs/{run_id}/provider-stage-tasks")
def get_provider_stage_tasks(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    stage: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 get_provider_stage_tasks 对应的业务流程、校验或数据转换。"""
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    page, page_size = _bounded_page(page, page_size)
    query = db.query(ProviderStageTask).filter(ProviderStageTask.run_id == run_id)
    if stage:
        query = query.filter(ProviderStageTask.stage == stage)
    if status:
        query = query.filter(ProviderStageTask.status == status)
    total = query.count()
    tasks = (
        query.order_by(ProviderStageTask.created_at.desc(), ProviderStageTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    reservations = {
        reservation.provider_stage_task_id: reservation
        for reservation in db.query(ProviderCostReservation)
        .filter(ProviderCostReservation.provider_stage_task_id.in_([task.id for task in tasks]))
        .all()
    } if tasks else {}
    return {
        "ok": True,
        "tasks": [_provider_stage_task_payload(task, reservations.get(task.id)) for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _tree_response(
    db: Session,
    plan_id: str,
    page: int,
    page_size: int,
    status: str | None,
    *,
    run_id: str | None = None,
) -> dict:
    """业务函数：处理 _tree_response 对应的业务流程、校验或数据转换。"""
    return {"ok": True, **get_run_tree(db, plan_id, page=page, page_size=page_size, status=status, run_id=run_id)}


def _production_plan_for_run(db: Session, run: VideoProductionRun) -> ProductionPlan:
    """业务函数：处理 _production_plan_for_run 对应的业务流程、校验或数据转换。"""
    if run.production_plan_id:
        plan = (
            db.query(ProductionPlan)
            .join(ProductionEpisode, ProductionEpisode.plan_id == ProductionPlan.id)
            .filter(
                ProductionPlan.id == run.production_plan_id,
                ProductionPlan.series_id == run.series_id,
                ProductionEpisode.episode_id == run.episode_id,
            )
            .first()
        )
        if not plan:
            raise HTTPException(409, "Run is linked to an invalid production plan")
        return plan

    trace = run.model_trace_json or {}
    traced_plan_id = trace.get("production_plan_id") or trace.get("plan_id")
    if traced_plan_id:
        plan = (
            db.query(ProductionPlan)
            .join(ProductionEpisode, ProductionEpisode.plan_id == ProductionPlan.id)
            .filter(
                ProductionPlan.id == traced_plan_id,
                ProductionPlan.series_id == run.series_id,
                ProductionEpisode.episode_id == run.episode_id,
            )
            .first()
        )
        if not plan:
            raise HTTPException(409, "Run is linked to an invalid production plan")
        return plan

    candidates = (
        db.query(ProductionPlan)
        .join(ProductionEpisode, ProductionEpisode.plan_id == ProductionPlan.id)
        .filter(ProductionPlan.series_id == run.series_id, ProductionEpisode.episode_id == run.episode_id)
        .order_by(ProductionPlan.updated_at.desc(), ProductionPlan.created_at.desc())
        .all()
    )
    if not candidates:
        raise HTTPException(404, "Production plan not found")
    if len(candidates) > 1:
        raise HTTPException(409, "Run is not linked to a unique production plan")
    return candidates[0]


@router.get("/plans/{plan_id}/tree")
def get_production_plan_tree(
    plan_id: str,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 get_production_plan_tree 对应的业务流程、校验或数据转换。"""
    try:
        return _tree_response(db, plan_id, page=page, page_size=page_size, status=status)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/runs/{run_id}/tree")
def get_production_run_tree(
    run_id: str,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 get_production_run_tree 对应的业务流程、校验或数据转换。"""
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    plan = _production_plan_for_run(db, run)
    try:
        return _tree_response(db, plan.id, page=page, page_size=page_size, status=status, run_id=run.id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/runs/{run_id}/costs")
def run_costs(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 run_costs 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_cost_summary_service import get_run_costs

    try:
        return {"ok": True, **get_run_costs(db, run_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/segments/{segment_id}/detail")
def segment_detail(
    segment_id: str,
    history_limit: int = 10,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 segment_detail 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_segment_detail_service import get_segment_detail

    try:
        return {"ok": True, **get_segment_detail(db, segment_id, history_limit)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/segments/{segment_id}/retry-impact")
def segment_retry_impact(
    segment_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 segment_retry_impact 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_retry_service import get_retry_impact

    try:
        return {"ok": True, **get_retry_impact(db, segment_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/runs/{run_id}/pause")
def pause_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 pause_run 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_queue_service import pause_plan_jobs

    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run or not run.production_plan_id:
        raise HTTPException(404, "Linked run not found")
    count = pause_plan_jobs(db, run.production_plan_id, "PAUSED_BY_OPERATOR")
    trace = dict(run.model_trace_json or {})
    if run.status != "paused":
        trace["pause_state"] = {
            "status": run.status,
            "current_stage": run.current_stage,
        }
    run.model_trace_json = trace
    run.status = "paused"
    db.commit()
    db.refresh(run)
    return {"ok": True, "paused_jobs": count, "run": _run_payload(run, db)}


@router.post("/runs/{run_id}/resume")
def resume_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 resume_run 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_queue_service import resume_plan_jobs

    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run or not run.production_plan_id:
        raise HTTPException(404, "Linked run not found")
    count = resume_plan_jobs(db, run.production_plan_id)
    trace = dict(run.model_trace_json or {})
    pause_state = trace.pop("pause_state", {}) if isinstance(trace.get("pause_state"), dict) else {}
    run.model_trace_json = trace
    run.status = pause_state.get("status") or "running"
    run.current_stage = pause_state.get("current_stage") or run.current_stage
    db.commit()
    db.refresh(run)
    return {"ok": True, "resumed_jobs": count, "run": _run_payload(run, db)}


# -- Review items -----------------------------------------------------------

@router.get("/review-items")
def review_items(
    run_id: str | None = None,
    status: str | None = None,
    statuses: list[str] | None = Query(None),
    series_id: str | None = None,
    episode_id: str | None = None,
    stage: str | None = None,
    asset_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 review_items 对应的业务流程、校验或数据转换。"""
    page, page_size = _bounded_page(page, page_size)
    query = db.query(VideoProductionAsset).filter(VideoProductionAsset.is_latest.is_(True))
    if run_id:
        query = query.filter(VideoProductionAsset.run_id == run_id)
    status_filters = _review_item_status_filters(status, statuses)
    if status_filters:
        query = query.filter(VideoProductionAsset.status.in_(status_filters))
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
        "gate_counts": _review_gate_counts(db, run_id),
    }


# -- Human review actions ---------------------------------------------------

def _review_edit_pending_response(exc: ReviewAssetEditError) -> JSONResponse:
    """业务函数：处理 _review_edit_pending_response 对应的业务流程、校验或数据转换。"""
    details = exc.details or {}
    return JSONResponse(status_code=202, content={
        "ok": False,
        "status": "pending",
        "code": exc.code,
        "message": "改图任务已提交，等待生成结果同步。",
        "image_creation_task_id": details.get("image_task_id"),
        "warnings": [{"code": exc.code, "message": exc.message, "details": details}],
        "missing_requirements": [],
    })


def _review_edit_http_error(exc: ReviewAssetEditError) -> HTTPException:
    """业务函数：处理 _review_edit_http_error 对应的业务流程、校验或数据转换。"""
    status_code = 404 if exc.code == "ASSET_NOT_FOUND" else 409
    if exc.code == "IMAGE_EDIT_PROVIDER_FAILED":
        status_code = int((exc.details or {}).get("status_code") or 502)
        if status_code == 500:
            status_code = 502
    return HTTPException(status_code=status_code, detail={
        "code": exc.code,
        "message": exc.message,
        "details": exc.details or {},
    })


@router.post("/assets/{asset_id}/review")
def review_asset(
    asset_id: str,
    body: ReviewAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 review_asset 对应的业务流程、校验或数据转换。"""
    reviewer_id = user[0] if isinstance(user, tuple) else None
    try:
        if body.action == "approve":
            asset = approve_asset(db, asset_id, reviewer_user_id=reviewer_id, comment=body.comment)
        elif body.action == "reject":
            asset = reject_asset(db, asset_id, reviewer_user_id=reviewer_id, comment=body.comment)
        else:
            raise HTTPException(400, f"Unknown action: {body.action}")
    except ProductionRepairableError as exc:
        raise HTTPException(status_code=409, detail=to_http_detail(exc))
    except VideoProductionError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


@router.post("/assets/{asset_id}/void")
def void_asset(
    asset_id: str,
    body: VoidAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 void_asset 对应的业务流程、校验或数据转换。"""
    reviewer_id = user[0] if isinstance(user, tuple) else None
    try:
        result = void_asset_version(
            db,
            asset_id,
            reviewer_user_id=reviewer_id,
            comment=body.comment,
            expected_version=body.expected_version,
        )
    except ReviewAssetEditError as exc:
        raise _review_edit_http_error(exc)
    return {
        "ok": True,
        "asset": _asset_payload(result["asset"]),
        "warnings": [],
        "missing_requirements": [],
    }


@router.post("/assets/{asset_id}/image-edit")
async def image_edit_asset(
    asset_id: str,
    body: ImageEditRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 image_edit_asset 对应的业务流程、校验或数据转换。"""
    try:
        result = await edit_image_asset(
            db,
            asset_id,
            instruction=body.instruction,
            expected_version=body.expected_version,
        )
    except ReviewAssetEditError as exc:
        if exc.code in {"IMAGE_EDIT_TASK_QUEUED", "IMAGE_EDIT_TASK_PENDING"}:
            return _review_edit_pending_response(exc)
        raise _review_edit_http_error(exc)
    return {
        "ok": True,
        "asset": _asset_payload(result["asset"]),
        "warnings": [],
        "missing_requirements": [],
    }


@router.post("/assets/{asset_id}/persist-retry")
def retry_asset_persistence(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 retry_asset_persistence 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.asset_storage_guard import persist_provider_asset
    from app.domains.video_production.video_production_service import run_ai_audit_for_assets, run_final_audit_for_asset

    try:
        existing = db.query(VideoProductionAsset).filter_by(id=asset_id).first()
        if not existing:
            raise HTTPException(404, "Asset not found")
        if existing.copy_status not in {"registered", "storage_failed"}:
            raise HTTPException(409, "Asset persistence can only be retried for registered or storage_failed assets")
        asset = persist_provider_asset(
            db,
            asset_id,
            output_root="output/video-production",
            pixelle_output_root=Path(PIXELLE_CONFIG_PATH).resolve().parent / "output",
        )
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
        existing_ai_review = db.query(VideoReviewRecord).filter(
            VideoReviewRecord.asset_id == asset.id,
            VideoReviewRecord.review_type == "ai",
        ).first()
        if run and not existing_ai_review:
            if asset.asset_type == "final_video":
                asset = run_final_audit_for_asset(db, run, asset)
            else:
                audited = run_ai_audit_for_assets(db, run, [asset])
                asset = audited[0] if audited else asset
    except ProductionRepairableError as exc:
        raise HTTPException(status_code=409, detail=to_http_detail(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


@router.post("/segments/{segment_id}/retry")
def retry_production_segment(
    segment_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 retry_production_segment 对应的业务流程、校验或数据转换。"""
    try:
        segment = retry_segment(db, segment_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(404, message)
        if "not retryable" in message:
            raise HTTPException(409, message)
        raise HTTPException(400, message)
    return {"ok": True, "segment": _production_segment_payload(segment)}


@router.post("/reviews/bulk-action")
def bulk_review_action(
    body: BulkReviewActionRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 bulk_review_action 对应的业务流程、校验或数据转换。"""
    reviewer_id = user[0] if isinstance(user, tuple) else None
    try:
        result = apply_bulk_review_action(
            db,
            body.asset_ids,
            action=body.action,
            reviewer_user_id=reviewer_id,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "result": result}


@router.post("/collections")
def create_collection(
    body: CreateCollectionRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 create_collection 对应的业务流程、校验或数据转换。"""
    from app.domains.video_production.production_collection_service import create_collection_from_approved_episodes

    try:
        collection = create_collection_from_approved_episodes(db, body.series_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "ok": True,
        "collection": {
            "id": collection.id,
            "series_id": collection.series_id,
            "status": collection.status,
            "included_episode_ids": collection.included_episode_ids,
            "duration_seconds": collection.duration_seconds,
            "video_url": collection.video_url,
        },
    }


# -- Image stage ------------------------------------------------------------

@router.post("/runs/{run_id}/start-images")
async def start_images(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 start_images 对应的业务流程、校验或数据转换。"""
    try:
        run = await start_image_stage(db, run_id)
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run, db)}


@router.post("/runs/{run_id}/sync-image-results")
async def sync_images(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 sync_images 对应的业务流程、校验或数据转换。"""
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
    user=Depends(require_role("admin")),
):
    """业务函数：处理 start_videos 对应的业务流程、校验或数据转换。"""
    try:
        run = await start_video_stage(db, run_id)
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run, db)}


@router.post("/runs/{run_id}/sync-video-results")
async def sync_videos(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 sync_videos 对应的业务流程、校验或数据转换。"""
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
    user=Depends(require_role("admin")),
):
    """业务函数：处理 compose_run 对应的业务流程、校验或数据转换。"""
    try:
        run = await start_compose_stage(db, run_id)
    except ProductionRepairableError as exc:
        raise HTTPException(409, to_http_detail(exc))
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run, db)}


@router.post("/runs/{run_id}/sync-compose-results")
async def sync_compose(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 sync_compose 对应的业务流程、校验或数据转换。"""
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
    user=Depends(require_role("admin")),
):
    """业务函数：处理 regenerate_asset 对应的业务流程、校验或数据转换。"""
    try:
        asset = create_regenerated_image_asset(db, asset_id, body.model_dump())
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


@router.post("/assets/{asset_id}/start-regeneration")
async def start_regeneration(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 start_regeneration 对应的业务流程、校验或数据转换。"""
    try:
        asset = await start_asset_regeneration(db, asset_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


@router.post("/assets/{asset_id}/sync-regeneration")
async def sync_regeneration(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 sync_regeneration 对应的业务流程、校验或数据转换。"""
    try:
        asset = await sync_regenerated_asset(db, asset_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
