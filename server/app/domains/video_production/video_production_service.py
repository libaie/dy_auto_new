"""Staged video production orchestration owned by dy_auto."""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import PIXELLE_CONFIG_PATH, bj_now
from app.db.models.video_production import ProductionPlan
from app.db_models import (
    Episode,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.domains.agency_operations.agency_backtrack_policy import trigger_backtrack_if_needed
from app.domains.agency_operations.agency_creative_patch_service import unresolved_patch_gate
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator
from app.domains.model_configuration.runtime_model_config import (
    RuntimeModelConfigError,
    redact_runtime_model_config,
    resolve_runtime_model_config,
)
from app.domains.pixelle_integration.pixelle_stage_client import (
    get_stage_task,
    submit_compose,
    submit_image_batch,
    submit_video_batch,
)
from app.domains.production_observability.production_observability_service import record_production_event
from app.domains.quality_audit.audit_gate import classify_audit_gate
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.production_queue_service import enqueue_job
from app.domains.video_production.production_state_contract import asset_is_reviewable
from app.domains.video_production.production_status import (
    PLAN_RUNNING,
    SEGMENT_IMAGE_APPROVED,
    SEGMENT_IMAGE_QUEUED,
    SEGMENT_IMAGE_REVIEW_PENDING,
    SEGMENT_VIDEO_APPROVED,
    SEGMENT_VIDEO_QUEUED,
    SEGMENT_VIDEO_REVIEW_PENDING,
)
from app.domains.video_production.production_status_aggregation import recompute_from_segment
from app.domains.video_production.provider_capability_service import capability_from_model_config
from app.domains.video_production.video_production_run_types import (
    LEGACY_EPISODE_RUN,
    REAL_SHORT_E2E,
    assert_run_type,
    validate_run_type,
)
from app.domains.video_production.video_production_state import (
    assert_can_compose,
    assert_can_start_images,
    assert_can_start_videos,
    latest_assets_by_frame,
    record_stage_task,
    recompute_run_gate,
)

logger = logging.getLogger(__name__)
COMPOSE_SCENE_KEY = "video_composition"
PROVIDER_MODEL_CONFIG_MISSING = "PROVIDER_MODEL_CONFIG_MISSING"
REAL_PROVIDER_PATH_RUN_TYPES = (REAL_SHORT_E2E, LEGACY_EPISODE_RUN)


class VideoProductionError(ValueError):
    pass


def _pixelle_output_root() -> Path:
    return Path(PIXELLE_CONFIG_PATH).resolve().parent / "output"


def _missing_agency_trace(stage: str, exc: Exception, *, status: str = "blocked") -> dict:
    return {
        "stage": stage,
        "stage_status": status,
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": str(exc),
    }


def _stage_context(db: Session, run: VideoProductionRun, payload_key: str, payload: list[dict] | dict) -> dict:
    episode = db.query(Episode).filter(Episode.id == run.episode_id).first() if run.episode_id else None
    return {
        "run_id": run.id,
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "storyboard": (run.storyboard_json or {}),
        payload_key: payload,
        "episode_storyboard": (episode.storyboard_json if episode else {}) or {},
    }


def _store_agency_trace(run: VideoProductionRun, stage: str, trace: dict) -> None:
    model_trace = dict(run.model_trace_json or {})
    reviews = dict(model_trace.get("agency_reviews") or {})
    reviews[stage] = trace
    model_trace["agency_reviews"] = reviews
    run.model_trace_json = model_trace


def _blocked_status_for_agency_stage(stage: str) -> tuple[str, str]:
    if stage in {"image_stage", "image_review"}:
        return "image_human_review_required", "image_review"
    if stage in {"video_stage", "video_review"}:
        return "video_human_review_required", "video_review"
    return "final_review_pending", "final_review"


def _block_provider_stage(db: Session, run: VideoProductionRun, stage: str, trace: dict) -> VideoProductionRun:
    run.status, run.current_stage = _blocked_status_for_agency_stage(stage)
    run.updated_at = bj_now()
    _store_agency_trace(run, stage, trace)
    _record_run_event(
        db,
        run,
        f"agency.{stage}.blocked",
        payload={
            "stage": stage,
            "agency_stage_status": trace.get("stage_status"),
            "error_code": trace.get("error_code"),
            "invocation_ids": trace.get("invocation_ids", []),
        },
    )
    db.commit()
    db.refresh(run)
    return run


def _block_missing_provider_model_config(
    db: Session,
    run: VideoProductionRun,
    *,
    stage: str,
    scene_key: str,
    exc: RuntimeModelConfigError,
) -> None:
    run.status, run.current_stage = _blocked_status_for_agency_stage(stage)
    run.updated_at = bj_now()
    trace = dict(run.model_trace_json or {})
    errors = dict(trace.get("provider_model_config_errors") or {})
    errors[scene_key] = {
        "stage": stage,
        "scene_key": scene_key,
        "error_code": PROVIDER_MODEL_CONFIG_MISSING,
        "error_message": str(exc),
    }
    trace["provider_model_config_errors"] = errors
    run.model_trace_json = trace
    _record_run_event(
        db,
        run,
        f"provider_config.{stage}.blocked",
        payload={
            "stage": stage,
            "scene_key": scene_key,
            "error_code": PROVIDER_MODEL_CONFIG_MISSING,
            "error_message": str(exc),
        },
    )
    db.commit()
    db.refresh(run)


def _block_regeneration_missing_provider_model_config(
    db: Session,
    run: VideoProductionRun,
    asset: VideoProductionAsset,
    *,
    stage: str,
    scene_key: str,
    exc: RuntimeModelConfigError,
) -> None:
    run.status, run.current_stage = _blocked_status_for_agency_stage(stage)
    run.updated_at = bj_now()
    asset.status = "rejected"
    asset.updated_at = bj_now()
    metadata = dict(asset.metadata_json or {})
    metadata["regeneration_error"] = {
        "scene_key": scene_key,
        "error_code": PROVIDER_MODEL_CONFIG_MISSING,
        "error_message": str(exc),
    }
    asset.metadata_json = metadata
    trace = dict(run.model_trace_json or {})
    errors = dict(trace.get("provider_model_config_errors") or {})
    errors[f"regeneration:{asset.id}"] = {
        "stage": stage,
        "scene_key": scene_key,
        "asset_id": asset.id,
        "asset_type": asset.asset_type,
        "frame_id": asset.frame_id,
        "error_code": PROVIDER_MODEL_CONFIG_MISSING,
        "error_message": str(exc),
    }
    trace["provider_model_config_errors"] = errors
    run.model_trace_json = trace
    _record_run_event(
        db,
        run,
        f"provider_config.{stage}.blocked",
        provider_task_id=asset.provider_task_id or asset.pixelle_task_id,
        production_segment_id=asset.production_segment_id,
        payload={
            "stage": stage,
            "scene_key": scene_key,
            "asset_id": asset.id,
            "asset_type": asset.asset_type,
            "frame_id": asset.frame_id,
            "error_code": PROVIDER_MODEL_CONFIG_MISSING,
            "error_message": str(exc),
        },
    )
    db.commit()
    db.refresh(run)
    db.refresh(asset)


async def _run_agency_stage_review(
    db: Session,
    run: VideoProductionRun,
    stage: str,
    stage_context: dict,
) -> dict:
    try:
        runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
    except RuntimeModelConfigError as exc:
        return _missing_agency_trace(stage, exc)

    orchestrator = AgencyOrchestrator()
    kwargs = {
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "run_id": run.id,
        "production_plan_id": run.production_plan_id,
        "production_episode_id": run.production_episode_id,
        "stage_context": stage_context,
        "runtime_config": runtime_config,
    }
    if stage == "image_stage":
        return await orchestrator.run_image_stage_review(db, **kwargs)
    if stage == "image_review":
        return await orchestrator.run_image_review(db, **kwargs)
    if stage == "video_stage":
        return await orchestrator.run_video_stage_review(db, **kwargs)
    if stage == "video_review":
        return await orchestrator.run_video_review(db, **kwargs)
    if stage == "compose_preflight":
        return await orchestrator.run_compose_preflight_review(db, **kwargs)
    return await orchestrator.run_compose_review(db, **kwargs)


async def _guard_provider_stage(
    db: Session,
    run: VideoProductionRun,
    stage: str,
    stage_context: dict,
) -> dict | None:
    trace = await _run_agency_stage_review(db, run, stage, stage_context)
    if trace.get("stage_status") in {"blocked", "failed"}:
        _store_agency_trace(run, stage, trace)
        _block_provider_stage(db, run, stage, trace)
        return None
    _store_agency_trace(run, stage, trace)
    return trace


def _frame_id(frame: dict, index: int) -> str:
    return str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}")


def _next_asset_version(db: Session, run_id: str, frame_id: str, asset_type: str) -> int:
    latest = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.frame_id == frame_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.version.desc()).first()
    return (latest.version + 1) if latest else 1


def _next_asset_version_for_target(
    db: Session,
    run_id: str,
    frame_id: str,
    asset_type: str,
    production_segment_id: str | None = None,
) -> int:
    query = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.asset_type == asset_type,
    )
    if production_segment_id:
        query = query.filter(VideoProductionAsset.production_segment_id == production_segment_id)
    else:
        query = query.filter(VideoProductionAsset.frame_id == frame_id)
    latest = query.order_by(VideoProductionAsset.version.desc()).first()
    return (latest.version + 1) if latest else 1


def _demote_latest_assets(
    db: Session,
    run_id: str,
    asset_type: str,
    production_segment_id: str | None = None,
    frame_id: str | None = None,
) -> None:
    query = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.asset_type == asset_type,
        VideoProductionAsset.is_latest.is_(True),
    )
    if production_segment_id:
        query = query.filter(VideoProductionAsset.production_segment_id == production_segment_id)
    elif frame_id:
        query = query.filter(VideoProductionAsset.frame_id == frame_id)
    query.update({"is_latest": False}, synchronize_session=False)


def _is_linked_run(run: VideoProductionRun) -> bool:
    return bool(
        run.production_plan_id
        and run.production_episode_id
        and run.production_link_status == "linked"
    )


def _review_snapshot(asset: VideoProductionAsset) -> dict:
    return {
        "target_type": asset.target_type,
        "target_id": asset.target_id,
        "production_segment_id": asset.production_segment_id,
        "asset_version": asset.version,
        "is_latest_asset_review": bool(asset.is_latest),
    }


def _raise_stale_asset(asset: VideoProductionAsset) -> None:
    raise ProductionRepairableError(
        code=ProductionErrorCode.STALE_ASSET_VERSION,
        message="A newer asset version exists. Reload before reviewing.",
        repair_action="Reload latest version",
        repair_route=f"/video-production/{asset.run_id}",
        retryable=True,
        affected_ids=[asset.id],
    )


def _record_run_event(
    db: Session,
    run: VideoProductionRun,
    event_type: str,
    *,
    payload: dict | None = None,
    provider_task_id: str | None = None,
    production_segment_id: str | None = None,
) -> None:
    event_payload = dict(payload or {})
    event_payload.setdefault("run_type", run.run_type)
    record_production_event(
        db,
        event_type=event_type,
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        production_segment_id=production_segment_id,
        provider_task_id=provider_task_id,
        payload=event_payload,
    )


def _assert_asset_persisted_for_review(asset: VideoProductionAsset) -> None:
    if not asset_is_reviewable(asset):
        raise ProductionRepairableError(
            code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
            message="Asset is not pending human review and cannot be approved.",
            cause="asset_not_review_pending",
            repair_action="Wait for asset persistence and review readiness, or regenerate the asset.",
            repair_route=f"/video-production/{asset.run_id}",
            retryable=True,
            affected_ids=[asset.id],
        )
    if asset.copy_status != "persisted" or not asset.checksum or not asset.storage_path:
        raise ProductionRepairableError(
            code=ProductionErrorCode.ASSET_STORAGE_FAILED,
            message="Asset has not been persisted and cannot pass human approval.",
            cause="asset_not_persisted",
            repair_action="Retry asset persistence or regenerate the asset.",
            repair_route=f"/video-production/{asset.run_id}",
            retryable=True,
            affected_ids=[asset.id],
        )


def _asset_is_persisted(asset: VideoProductionAsset) -> bool:
    return bool(asset.copy_status == "persisted" and asset.checksum and asset.storage_path)


def _promote_linked_segment_for_approved_asset(db: Session, asset: VideoProductionAsset) -> None:
    if not asset.production_segment_id:
        return
    if asset.asset_type == "image":
        next_status = SEGMENT_IMAGE_APPROVED
    elif asset.asset_type == "video_segment":
        next_status = SEGMENT_VIDEO_APPROVED
    else:
        return
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == asset.production_segment_id).first()
    if not segment:
        return
    segment.status = next_status
    db.flush()
    recompute_from_segment(db, segment.id)


def _controlled_asset_url(asset: VideoProductionAsset) -> str:
    return asset.storage_path or asset.local_path or asset.url or ""


def _provider_input_asset_url(asset: VideoProductionAsset) -> str:
    candidates = (asset.url, asset.source_url, asset.local_path, asset.storage_path)
    for value in candidates:
        clean = str(value or "").strip()
        if clean.lower().startswith(("http://", "https://", "data:image/")):
            return clean
    return _controlled_asset_url(asset)


def _stage_input_asset_url(asset: VideoProductionAsset, *, prefer_controlled_asset: bool = False) -> str:
    if prefer_controlled_asset:
        return _controlled_asset_url(asset) or _provider_input_asset_url(asset)
    return _provider_input_asset_url(asset)


def persist_assets_for_review(db: Session, assets: list[VideoProductionAsset]) -> list[VideoProductionAsset]:
    from app.domains.video_production.asset_storage_guard import persist_provider_asset

    persisted = []
    for asset in assets:
        if _asset_is_persisted(asset):
            persisted.append(asset)
            continue
        try:
            persisted.append(
                persist_provider_asset(
                    db,
                    asset.id,
                    output_root="output/video-production",
                    pixelle_output_root=_pixelle_output_root(),
                )
            )
        except ProductionRepairableError:
            db.refresh(asset)
    return persisted


def _force_review_status_after_blocked_gate(run: VideoProductionRun, asset_type: str) -> None:
    if asset_type == "image":
        run.status = "image_review_pending"
        run.current_stage = "image_review"
    elif asset_type == "video_segment":
        run.status = "video_review_pending"
        run.current_stage = "video_review"
    run.updated_at = bj_now()


def _raise_blocked_aggregate_gate(run: VideoProductionRun, stage: str, gate_result: dict) -> None:
    blocked_ids = gate_result.get("blocked_segment_ids") or [
        detail.get("required_id")
        for detail in gate_result.get("blocked_details", [])
        if detail.get("required_id")
    ]
    raise ProductionRepairableError(
        code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
        message=f"{stage} aggregate gate is blocked.",
        cause=f"{stage}_gate_blocked",
        repair_action="Approve and persist all latest required assets before starting the downstream stage.",
        repair_route=f"/video-production/{run.id}",
        retryable=True,
        affected_ids=blocked_ids,
    )


def _guard_creative_patches(db: Session, run: VideoProductionRun, stage: str) -> None:
    gate = unresolved_patch_gate(db, run, stage=stage)
    if not gate.get("blocked"):
        return
    run.status = "creative_review_required"
    run.current_stage = "creative_review"
    run.updated_at = bj_now()
    _record_run_event(
        db,
        run,
        "agency_creative_patch_gate_blocked",
        payload={"stage": stage, **gate},
    )
    db.commit()
    db.refresh(run)
    raise VideoProductionError(
        f"Creative patches are pending in the director workbench: {gate['blocking_count']} unresolved."
    )


def _assert_real_provider_path_run_type(run: VideoProductionRun) -> None:
    try:
        assert_run_type(run, REAL_PROVIDER_PATH_RUN_TYPES)
    except ValueError as exc:
        raise VideoProductionError(str(exc)) from exc


def _assert_real_short_provider_budget(db: Session, run: VideoProductionRun) -> None:
    if run.run_type != REAL_SHORT_E2E:
        return
    if not run.production_plan_id:
        raise VideoProductionError("real_short_e2e requires a linked production plan with a positive budget_limit.")
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == run.production_plan_id).first()
    if not plan or plan.budget_limit is None or float(plan.budget_limit) <= 0:
        raise VideoProductionError("real_short_e2e requires a positive budget_limit before provider stages can start.")


def _capability_from_runtime_model_config(model_config: dict | None) -> dict:
    if not isinstance(model_config, dict):
        return capability_from_model_config(model_config)
    normalized = dict(model_config)
    if isinstance(model_config.get("config"), dict):
        normalized["config_json"] = {
            **(model_config.get("config_json") or {}),
            **model_config["config"],
        }
    return capability_from_model_config(normalized)


def _runtime_model_name(model_config: dict) -> str:
    return str(model_config.get("model_name") or model_config.get("model") or "")


def _assert_legacy_direct_stage_not_paid(run: VideoProductionRun, model_config: dict, scene_key: str) -> None:
    if validate_run_type(run.run_type) != LEGACY_EPISODE_RUN:
        return
    capability = _capability_from_runtime_model_config(model_config)
    if capability.get("real_paid_allowed") is True:
        raise VideoProductionError(
            f"legacy_episode_run cannot submit paid provider scene '{scene_key}' directly; "
            "start a real_short_e2e run and process it through the worker/executor path."
        )


def _assert_regeneration_not_direct_paid_run(run: VideoProductionRun) -> None:
    if validate_run_type(run.run_type) == REAL_SHORT_E2E:
        raise VideoProductionError(
            "real_short_e2e asset regeneration must use queued segment retry through the worker/executor path; "
            "direct provider regeneration is disabled for paid runs."
        )


async def start_real_provider_stage_via_executor(db: Session, run: VideoProductionRun, stage: str) -> VideoProductionRun:
    if not run.production_plan_id:
        raise VideoProductionError("real_short_e2e requires a linked production plan.")

    normalized_stage = "episode_compose" if stage in {"composition", "episode_compose"} else stage
    if normalized_stage == "image_generation":
        _guard_creative_patches(db, run, "image_stage")
    elif normalized_stage == "video_generation":
        _guard_creative_patches(db, run, "video_stage")
    elif normalized_stage == "episode_compose":
        _guard_creative_patches(db, run, "compose_preflight")
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == run.production_plan_id).first()
    if plan and plan.status != PLAN_RUNNING:
        plan.status = PLAN_RUNNING

    if normalized_stage == "image_generation":
        frames = image_stage_frames(run, db=db)
        if not frames:
            raise VideoProductionError("Run has no production segments for image generation")
        for frame in frames:
            target_id = frame["production_segment_id"]
            enqueue_job(
                db,
                run.production_plan_id,
                "production_segment",
                target_id,
                "image_generation",
                f"{run.id}:{target_id}:image_generation:v1",
            )
            segment = db.query(ProductionSegment).filter(ProductionSegment.id == target_id).first()
            if segment and segment.status == "planned":
                segment.status = SEGMENT_IMAGE_QUEUED
        run.status = "image_batch_running"
        run.current_stage = "image_generation"
    elif normalized_stage == "video_generation":
        frames = video_stage_frames(db, run)
        if not frames:
            raise VideoProductionError("Run has no production segments for video generation")
        for frame in frames:
            target_id = frame["production_segment_id"]
            enqueue_job(
                db,
                run.production_plan_id,
                "production_segment",
                target_id,
                "video_generation",
                f"{run.id}:{target_id}:video_generation:v1",
            )
            segment = db.query(ProductionSegment).filter(ProductionSegment.id == target_id).first()
            if segment:
                segment.status = SEGMENT_VIDEO_QUEUED
        run.status = "video_batch_running"
        run.current_stage = "video_rendering"
    elif normalized_stage == "episode_compose":
        target_id = run.production_episode_id or run.id
        enqueue_job(
            db,
            run.production_plan_id,
            "production_episode",
            target_id,
            "episode_compose",
            f"{run.id}:{target_id}:episode_compose:v1",
        )
        run.status = "composing"
        run.current_stage = "composition"
    else:
        raise VideoProductionError(f"Unsupported real provider stage: {stage}")

    run.updated_at = bj_now()
    _record_run_event(
        db,
        run,
        "provider_stage.enqueued",
        payload={"stage": normalized_stage},
    )
    db.commit()
    db.refresh(run)
    return run


# -- Run creation -----------------------------------------------------------

def create_run_from_episode(
    db: Session,
    series_id: str,
    episode_id: str,
    *,
    commit: bool = True,
    run_type: str = LEGACY_EPISODE_RUN,
) -> VideoProductionRun:
    run_type = validate_run_type(run_type)
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise VideoProductionError("Episode not found")
    storyboard = episode.storyboard_json or {}
    frames = storyboard.get("frames") or []
    if not frames:
        raise VideoProductionError("Episode storyboard_json is empty")

    normalized_frames = []
    for index, frame in enumerate(frames):
        normalized_frames.append({**frame, "frame_id": _frame_id(frame, index)})

    run = VideoProductionRun(
        series_id=series_id,
        episode_id=episode_id,
        status="draft",
        current_stage="storyboard_ready",
        run_type=run_type,
        storyboard_json={**storyboard, "frames": normalized_frames},
    )
    db.add(run)
    db.flush()
    _record_run_event(
        db,
        run,
        "run_type.assigned",
        payload={"run_type": run_type},
    )
    if commit:
        db.commit()
        db.refresh(run)
    return run


# -- Image stage payload helpers -------------------------------------------

def _storyboard_frames_by_id(run: VideoProductionRun) -> dict[str, dict]:
    frames = (run.storyboard_json or {}).get("frames") or []
    by_id: dict[str, dict] = {}
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for key in (frame.get("frame_id"), frame.get("shot_id")):
            if key:
                by_id[str(key)] = frame
    return by_id


def _approved_storyboard_image_assets_by_frame(db: Session, run: VideoProductionRun) -> dict[str, VideoProductionAsset]:
    rows = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.status == "approved",
    ).all()
    by_frame: dict[str, VideoProductionAsset] = {}
    for asset in rows:
        metadata = asset.metadata_json or {}
        if not asset.url:
            continue
        if metadata.get("destination_role") != "storyboard_frame" and not metadata.get("source_image_asset_id"):
            continue
        by_frame[str(asset.frame_id)] = asset
    return by_frame


def _storyboard_image_source_fields(asset: VideoProductionAsset | None) -> dict:
    if not asset:
        return {}
    metadata = asset.metadata_json or {}
    fields = {
        "source_image_url": asset.url,
        "storyboard_video_asset_id": asset.id,
    }
    source_image_asset_id = metadata.get("source_image_asset_id")
    if source_image_asset_id:
        fields["storyboard_image_asset_id"] = source_image_asset_id
    return fields


def build_image_stage_frames_for_segments(db: Session, run: VideoProductionRun) -> list[dict]:
    from app.utils.prompt_compositor import AssetPromptCompositor

    compositor = AssetPromptCompositor(db)
    storyboard_frames = _storyboard_frames_by_id(run)
    approved_storyboard_images = _approved_storyboard_image_assets_by_frame(db, run)
    rows = (
        db.query(ProductionSegment, ProductionShot)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == run.production_episode_id)
        .filter(ProductionSegment.status != "superseded")
        .order_by(
            ProductionScene.order_index.asc(),
            ProductionShot.order_index.asc(),
            ProductionSegment.order_index.asc(),
        )
        .all()
    )
    frames = []
    for segment, shot in rows:
        composed = compositor.compose_shot_prompt(shot.id)
        storyboard_frame = storyboard_frames.get(str(shot.shot_id)) or {}
        reference_roles = _merge_reference_roles(composed.reference_images, segment.reference_roles_json or [])
        reference_urls = [
            item.get("url")
            for item in reference_roles
            if item.get("url")
        ]
        reference_instructions = (
            "Use the supplied character, scene, and style reference images to lock identity, outfit, lighting, "
            "palette, lens language, and environment continuity."
        ) if reference_urls else ""
        approved_storyboard_image = (
            approved_storyboard_images.get(str(segment.id))
            or approved_storyboard_images.get(str(shot.shot_id))
        )
        frames.append({
            "frame_id": segment.id,
            "production_segment_id": segment.id,
            "image_prompt": composed.prompt if composed.reference_images else segment.image_prompt,
            "video_prompt": segment.video_prompt,
            "narration": segment.narration or "",
            "reference_roles": reference_roles,
            "reference_images": composed.reference_images,
            "reference_urls": reference_urls,
            "reference_instructions": reference_instructions,
            "negative_prompt": str(storyboard_frame.get("negative_prompt") or ""),
            "provider_options": composed.provider_options,
            "style_constraints": {
                "continuity_notes": segment.expected_end_state or reference_instructions,
                "continuity_mode": segment.continuity_mode,
                "source_version": segment.version,
            },
            "duration": float(segment.duration_seconds or 5),
            **_storyboard_image_source_fields(approved_storyboard_image),
        })
    return frames


def _merge_reference_roles(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in list(primary or []) + list(secondary or []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        url = str(item.get("url") or "").strip()
        if not role or not url or (role, url) in seen:
            continue
        seen.add((role, url))
        merged.append({**item, "role": role, "url": url, "priority": item.get("priority") or len(merged) + 1})
    return merged


def image_stage_frames(run: VideoProductionRun, db: Session | None = None) -> list[dict]:
    if _is_linked_run(run):
        if db is None:
            raise VideoProductionError("Linked production run requires a database session")
        return build_image_stage_frames_for_segments(db, run)
    frames = (run.storyboard_json or {}).get("frames") or []
    approved_storyboard_images = _approved_storyboard_image_assets_by_frame(db, run) if db is not None else {}
    payloads = []
    for index, frame in enumerate(frames):
        frame_id = _frame_id(frame, index)
        approved_storyboard_image = approved_storyboard_images.get(str(frame_id))
        payloads.append({
            "frame_id": frame_id,
            "image_prompt": frame.get("image_prompt", ""),
            "negative_prompt": frame.get("negative_prompt", ""),
            "reference_urls": frame.get("reference_urls") or [],
            "style_constraints": {
                "character_ids": frame.get("character_ids") or [],
                "scene_id": frame.get("scene_id"),
                "continuity_notes": frame.get("continuity_notes", ""),
            },
            "duration": float(frame.get("duration") or 5),
            **_storyboard_image_source_fields(approved_storyboard_image),
        })
    return payloads


def _assert_real_short_image_references(run: VideoProductionRun, frames: list[dict]) -> None:
    if run.run_type != REAL_SHORT_E2E:
        return
    missing_ids = [
        str(frame.get("production_segment_id") or frame.get("frame_id") or "unknown")
        for frame in frames
        if not frame.get("reference_urls")
    ]
    if not missing_ids:
        return
    raise ProductionRepairableError(
        code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
        message="Real one-sentence image generation requires reference images for every production segment.",
        cause="image_stage_reference_urls_missing",
        repair_action="Regenerate the style lock and storyboard so each frame carries character and scene reference URLs.",
        repair_route=f"/video-production/{run.id}",
        retryable=True,
        affected_ids=missing_ids,
    )


# -- Image stage ------------------------------------------------------------

def mark_image_stage_submitted(db: Session, run: VideoProductionRun, stage_task_id: str, model_trace: dict) -> VideoProductionRun:
    run.status = "image_batch_running"
    run.current_stage = "image_generation"
    run.pixelle_stage_task_id = stage_task_id
    record_stage_task(run, "image_generation", stage_task_id)
    run.model_trace_json = {**model_trace, **(run.model_trace_json or {})}
    run.updated_at = bj_now()
    _record_run_event(
        db,
        run,
        "image_stage.submitted",
        provider_task_id=stage_task_id,
        payload={"stage": "image_generation"},
    )
    db.commit()
    db.refresh(run)
    return run


def mark_image_stage_assets(db: Session, run: VideoProductionRun, assets: list[dict], pixelle_task_id: str) -> list[VideoProductionAsset]:
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.pixelle_task_id == pixelle_task_id,
    ).all()
    if existing:
        return existing

    saved = []
    for item in assets:
        frame_id = item["frame_id"]
        production_segment_id = item.get("production_segment_id") or (frame_id if _is_linked_run(run) else None)
        if production_segment_id:
            _demote_latest_assets(db, run.id, "image", production_segment_id=production_segment_id)
            version = _next_asset_version_for_target(
                db,
                run.id,
                production_segment_id,
                "image",
                production_segment_id=production_segment_id,
            )
        else:
            _demote_latest_assets(db, run.id, "image", frame_id=frame_id)
            version = _next_asset_version(db, run.id, frame_id, "image")
        asset = VideoProductionAsset(
            run_id=run.id,
            episode_id=run.episode_id,
            frame_id=production_segment_id or frame_id,
            asset_type="image",
            stage="image_generation",
            url=item.get("url", ""),
            source_url=item.get("source_url") or item.get("url", ""),
            local_path=item.get("local_path", ""),
            thumbnail_url=item.get("thumbnail_url", ""),
            storage_path=item.get("storage_path"),
            copy_status=item.get("copy_status", "registered"),
            checksum=item.get("checksum"),
            size_bytes=item.get("size_bytes"),
            version=version,
            metadata_json=item.get("metadata", {}),
            status="review_pending",
            pixelle_task_id=pixelle_task_id,
            provider_task_id=item.get("provider_task_id") or pixelle_task_id,
            provider_stage_task_id=item.get("provider_stage_task_id"),
            production_segment_id=production_segment_id,
            target_type="production_segment" if production_segment_id else None,
            target_id=production_segment_id,
            source_version=item.get("source_version") or 1,
            is_latest=True,
        )
        db.add(asset)
        saved.append(asset)
        if production_segment_id:
            segment = db.query(ProductionSegment).filter(ProductionSegment.id == production_segment_id).first()
            if segment:
                segment.status = SEGMENT_IMAGE_REVIEW_PENDING
        _record_run_event(
            db,
            run,
            "image_stage.asset_registered",
            provider_task_id=asset.provider_task_id or pixelle_task_id,
            production_segment_id=asset.production_segment_id,
            payload={"asset_id": asset.id, "asset_type": asset.asset_type, "version": asset.version},
        )
    run.status = "image_review_pending"
    run.current_stage = "image_review"
    run.updated_at = bj_now()
    db.commit()
    for asset in saved:
        db.refresh(asset)
    return saved


async def start_image_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    _assert_real_provider_path_run_type(run)
    _assert_real_short_provider_budget(db, run)
    try:
        assert_can_start_images(run)
    except ValueError as exc:
        raise VideoProductionError(str(exc)) from exc
    _guard_creative_patches(db, run, "image_stage")
    frames = image_stage_frames(run, db=db)
    if not frames:
        raise VideoProductionError("Run has no storyboard frames")
    _assert_real_short_image_references(run, frames)
    if run.run_type == REAL_SHORT_E2E:
        return await start_real_provider_stage_via_executor(db, run, "image_generation")
    agency_trace = await _guard_provider_stage(
        db,
        run,
        "image_stage",
        _stage_context(db, run, "frames", frames),
    )
    if agency_trace is None:
        return run
    try:
        model_config = resolve_runtime_model_config(db, "image_generation")
    except RuntimeModelConfigError as exc:
        _block_missing_provider_model_config(db, run, stage="image_stage", scene_key="image_generation", exc=exc)
        raise VideoProductionError(str(exc)) from exc
    _assert_legacy_direct_stage_not_paid(run, model_config, "image_generation")
    response = await submit_image_batch(
        db=db,
        run_id=run.id,
        episode_id=run.episode_id,
        frames=frames,
        model_config=model_config,
    )
    return mark_image_stage_submitted(
        db,
        run,
        response["stage_task_id"],
        {"image_generation": redact_runtime_model_config(model_config)},
    )


async def sync_image_stage_results(db: Session, run_id: str) -> list[VideoProductionAsset]:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Image stage is not complete: {status.get('status')}")
    assets = mark_image_stage_assets(db, run, status.get("assets", []), pixelle_task_id=run.pixelle_stage_task_id)
    persisted_assets = persist_assets_for_review(db, assets)
    run_ai_audit_for_assets(db, run, persisted_assets)
    return assets


# -- AI audit ---------------------------------------------------------------

def _record_audit_fallback(db: Session, asset: VideoProductionAsset, run_id: str, issues: list[str]) -> None:
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=run_id,
        review_type="ai",
        status="needs_human",
        score=0.0,
        issues_json=issues,
        model_trace_json={},
        **_review_snapshot(asset),
    ))


def _auto_review_policy(run: VideoProductionRun) -> dict:
    trace = run.model_trace_json or {}
    explicit = trace.get("auto_review_policy")
    if isinstance(explicit, dict) and explicit.get("enabled") is True:
        return {"enabled": True, "source": explicit.get("source") or "auto_review_policy"}
    autopilot = trace.get("autopilot")
    if isinstance(autopilot, dict) and autopilot.get("enabled") is True:
        return {"enabled": True, "source": "autopilot"}
    one_sentence = trace.get("one_sentence")
    if isinstance(one_sentence, dict) and one_sentence.get("autostart_images_after_references") is True:
        return {"enabled": True, "source": "one_sentence"}
    return {"enabled": False}


def _auto_approve_asset_if_enabled(
    db: Session,
    run: VideoProductionRun,
    asset: VideoProductionAsset,
    *,
    reason: str,
    recompute_gate: bool = True,
) -> bool:
    policy = _auto_review_policy(run)
    if not policy.get("enabled"):
        return False
    _assert_asset_persisted_for_review(asset)
    existing = db.query(VideoReviewRecord).filter(
        VideoReviewRecord.asset_id == asset.id,
        VideoReviewRecord.run_id == run.id,
        VideoReviewRecord.review_type == "auto",
        VideoReviewRecord.status == "approved",
    ).first()
    if not existing:
        db.add(VideoReviewRecord(
            asset_id=asset.id,
            run_id=run.id,
            review_type="auto",
            status="approved",
            score=1.0,
            issues_json=[],
            model_trace_json={
                "auto_review_policy": policy,
                "reason": reason,
            },
            comment="全自动生成策略自动通过审查",
            **_review_snapshot(asset),
        ))
    asset.status = "approved"
    db.flush()
    if not recompute_gate:
        return True
    if asset.asset_type in {"image", "video_segment"}:
        recompute_run_gate(db, run.id, asset.asset_type)
    elif asset.asset_type == "final_video":
        from app.domains.video_production.production_gate_evaluator import evaluate_stage_gate

        run.status = "final_review_pending"
        run.current_stage = "final_review"
        run.updated_at = bj_now()
        db.flush()
        gate_result = evaluate_stage_gate(db, run.id, stage="episode_compose")
        complete_final_video(db, run, asset, gate_result=gate_result)
    return True


def run_ai_audit_for_assets(db: Session, run: VideoProductionRun, assets: list[VideoProductionAsset]) -> list[VideoProductionAsset]:
    audit_model = {}
    try:
        from app.domains.model_configuration.model_registry import get_model_for_scene
        audit_model = get_model_for_scene(db, "quality_audit")
    except Exception:
        pass

    if not audit_model or not audit_model.get("api_key"):
        try:
            audit_model = resolve_runtime_model_config(db, "quality_audit")
        except Exception:
            audit_model = {}

    backtrack_triggered = False
    for asset in assets:
        existing_review = db.query(VideoReviewRecord).filter(
            VideoReviewRecord.asset_id == asset.id,
            VideoReviewRecord.review_type == "ai",
        ).first()
        if existing_review:
            continue

        audit_url = _controlled_asset_url(asset)
        if not audit_url:
            _record_audit_fallback(db, asset, run.id, ["No asset URL for audit"])
            db.flush()
            result = trigger_backtrack_if_needed(db, run, asset, reason="ai audit could not inspect asset URL")
            backtrack_triggered = backtrack_triggered or bool(result.get("triggered"))
            continue

        if not audit_model or not audit_model.get("api_key"):
            _record_audit_fallback(db, asset, run.id, ["Audit model not configured or missing API key"])
            db.flush()
            auto_approved = _auto_approve_asset_if_enabled(
                db,
                run,
                asset,
                reason="audit_model_unavailable",
                recompute_gate=not backtrack_triggered,
            )
            if not auto_approved:
                result = trigger_backtrack_if_needed(db, run, asset, reason="ai audit model unavailable")
                backtrack_triggered = backtrack_triggered or bool(result.get("triggered"))
            continue

        try:
            from app.domains.quality_audit.audit_router import _do_audit
            result = _do_audit(audit_model, audit_url, None)
        except Exception as exc:
            logger.warning("AI audit failed for asset %s: %s", asset.id, exc)
            result = {"score": 0.0, "pass_fail": False, "issues": [str(exc)], "raw": ""}

        gate = classify_audit_gate(result, error=False)
        db.add(VideoReviewRecord(
            asset_id=asset.id,
            run_id=run.id,
            review_type="ai",
            status=gate["gate_status"],
            score=gate["score"],
            issues_json=gate.get("issues", []),
            model_trace_json={"auditor_model": audit_model.get("provider", "unknown"), "auditor_model_name": _runtime_model_name(audit_model)},
            **_review_snapshot(asset),
        ))

        asset.status = "review_pending"
        if gate["gate_status"] == "approved":
            _auto_approve_asset_if_enabled(
                db,
                run,
                asset,
                reason="ai_audit_approved",
                recompute_gate=not backtrack_triggered,
            )
        else:
            db.flush()
            result = trigger_backtrack_if_needed(db, run, asset, reason="ai audit did not approve asset")
            backtrack_triggered = backtrack_triggered or bool(result.get("triggered"))

    db.commit()
    for asset in assets:
        db.refresh(asset)

    if assets and not backtrack_triggered:
        recompute_run_gate(db, run.id, assets[0].asset_type)
    return assets


# -- Human review actions ---------------------------------------------------

def latest_approved_assets_by_frame(db: Session, run_id: str, asset_type: str = "image") -> dict[str, VideoProductionAsset]:
    latest = latest_assets_by_frame(db, run_id, asset_type)
    return {frame_id: asset for frame_id, asset in latest.items() if asset.status == "approved"}


def approve_asset(db: Session, asset_id: str, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")

    if asset.asset_type == "final_video":
        return approve_final_video_asset(db, asset, reviewer_user_id, comment)

    latest = latest_assets_by_frame(db, asset.run_id, asset.asset_type).get(asset.frame_id)
    if latest and latest.id != asset.id:
        _raise_stale_asset(asset)
    if asset.status == "approved":
        if not _asset_is_persisted(asset):
            _assert_asset_persisted_for_review(asset)
        _promote_linked_segment_for_approved_asset(db, asset)
        return asset
    _assert_asset_persisted_for_review(asset)
    asset.status = "approved"
    _promote_linked_segment_for_approved_asset(db, asset)
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="approved",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
        **_review_snapshot(asset),
    ))
    db.commit()
    db.refresh(asset)
    recompute_run_gate(db, asset.run_id, asset.asset_type)
    from app.domains.video_production.production_gate_evaluator import evaluate_stage_gate

    if asset.asset_type == "image":
        gate_result = evaluate_stage_gate(db, asset.run_id, stage="image_generation")
    elif asset.asset_type == "video_segment":
        gate_result = evaluate_stage_gate(db, asset.run_id, stage="video_generation")
    else:
        gate_result = None
    if gate_result and not gate_result.get("ready"):
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
        if run:
            _force_review_status_after_blocked_gate(run, asset.asset_type)
    db.commit()
    db.refresh(asset)
    return asset


def reject_asset(db: Session, asset_id: str, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")

    if asset.asset_type == "final_video":
        return reject_final_video_asset(db, asset, reviewer_user_id, comment)

    latest = latest_assets_by_frame(db, asset.run_id, asset.asset_type).get(asset.frame_id)
    if latest and latest.id != asset.id:
        _raise_stale_asset(asset)
    asset.status = "rejected"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="rejected",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
        **_review_snapshot(asset),
    ))
    db.commit()
    db.refresh(asset)
    recompute_run_gate(db, asset.run_id, asset.asset_type)
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if run:
        trigger_backtrack_if_needed(db, run, asset, reason=comment or "human rejected asset")
        db.refresh(asset)
    return asset


# -- Video stage payload helpers --------------------------------------------

def build_video_stage_frames_for_segments(
    db: Session,
    run: VideoProductionRun,
    *,
    prefer_controlled_assets: bool = False,
) -> list[dict]:
    image_assets = {
        asset.production_segment_id: asset
        for asset in db.query(VideoProductionAsset).filter(
            VideoProductionAsset.run_id == run.id,
            VideoProductionAsset.asset_type == "image",
            VideoProductionAsset.is_latest.is_(True),
            VideoProductionAsset.status == "approved",
            VideoProductionAsset.copy_status == "persisted",
            VideoProductionAsset.checksum.isnot(None),
            VideoProductionAsset.storage_path.isnot(None),
        ).all()
        if asset.production_segment_id
    }
    frames = []
    for frame in build_image_stage_frames_for_segments(db, run):
        image = image_assets.get(frame["production_segment_id"])
        if not image:
            raise VideoProductionError(f"Approved image missing for segment {frame['production_segment_id']}")
        image_url = _stage_input_asset_url(image, prefer_controlled_asset=prefer_controlled_assets)
        frames.append({
            "frame_id": frame["production_segment_id"],
            "production_segment_id": frame["production_segment_id"],
            "approved_image_url": image_url,
            "input_image_url": image_url,
            "video_prompt": frame["video_prompt"],
            "reference_roles": frame.get("reference_roles") or [],
            "reference_urls": frame["reference_urls"],
            "duration": frame["duration"],
            "audio_mode": "tts",
        })
    return frames


def video_stage_frames(db: Session, run: VideoProductionRun, *, prefer_controlled_assets: bool = False) -> list[dict]:
    if _is_linked_run(run):
        return build_video_stage_frames_for_segments(db, run, prefer_controlled_assets=prefer_controlled_assets)
    latest_images = latest_assets_by_frame(db, run.id, "image")
    frames = (run.storyboard_json or {}).get("frames") or []
    payload = []
    for index, frame in enumerate(frames):
        frame_id = _frame_id(frame, index)
        image = latest_images.get(frame_id)
        if not image or image.status != "approved" or not _asset_is_persisted(image):
            raise VideoProductionError(f"Approved image missing for frame {frame_id}")
        image_url = _stage_input_asset_url(image, prefer_controlled_asset=prefer_controlled_assets)
        payload.append({
            "frame_id": frame_id,
            "approved_image_url": image_url,
            "input_image_url": image_url,
            "video_prompt": frame.get("video_prompt") or frame.get("image_prompt", ""),
            "reference_urls": frame.get("reference_urls") or [],
            "duration": float(frame.get("duration") or 5),
            "audio_mode": frame.get("audio_mode") or "tts",
        })
    return payload


def video_stage_frame_for_asset(
    db: Session,
    run: VideoProductionRun,
    frame_id: str,
    *,
    prefer_controlled_assets: bool = False,
) -> dict:
    for frame in video_stage_frames(db, run, prefer_controlled_assets=prefer_controlled_assets):
        if frame["frame_id"] == frame_id:
            return frame
    raise VideoProductionError(f"Frame not found for video regeneration: {frame_id}")


def image_stage_frame_for_asset(db: Session, run: VideoProductionRun, frame_id: str) -> dict:
    for frame in image_stage_frames(run, db=db):
        if frame["frame_id"] == frame_id:
            return frame
    raise VideoProductionError(f"Frame not found for image regeneration: {frame_id}")


# -- Video stage ------------------------------------------------------------

def mark_video_stage_assets(db: Session, run: VideoProductionRun, assets: list[dict], pixelle_task_id: str) -> list[VideoProductionAsset]:
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "video_segment",
        VideoProductionAsset.pixelle_task_id == pixelle_task_id,
    ).all()
    if existing:
        return existing

    saved = []
    for item in assets:
        frame_id = item["frame_id"]
        production_segment_id = item.get("production_segment_id") or (frame_id if _is_linked_run(run) else None)
        if production_segment_id:
            _demote_latest_assets(db, run.id, "video_segment", production_segment_id=production_segment_id)
            version = _next_asset_version_for_target(
                db,
                run.id,
                production_segment_id,
                "video_segment",
                production_segment_id=production_segment_id,
            )
        else:
            _demote_latest_assets(db, run.id, "video_segment", frame_id=frame_id)
            version = _next_asset_version(db, run.id, frame_id, "video_segment")
        asset = VideoProductionAsset(
            run_id=run.id,
            episode_id=run.episode_id,
            frame_id=production_segment_id or frame_id,
            asset_type="video_segment",
            stage="video_rendering",
            url=item.get("url", ""),
            source_url=item.get("source_url") or item.get("url", ""),
            local_path=item.get("local_path", ""),
            thumbnail_url=item.get("thumbnail_url", ""),
            storage_path=item.get("storage_path"),
            copy_status=item.get("copy_status", "registered"),
            checksum=item.get("checksum"),
            size_bytes=item.get("size_bytes"),
            duration_seconds=(item.get("metadata") or {}).get("duration"),
            version=version,
            metadata_json={
                **(item.get("metadata") or {}),
                "error_code": item.get("error_code"),
                "message": item.get("message"),
                "retryable": item.get("retryable", True),
            },
            status="failed" if item.get("status") == "failed" else "review_pending",
            pixelle_task_id=pixelle_task_id,
            provider_task_id=item.get("provider_task_id") or pixelle_task_id,
            provider_stage_task_id=item.get("provider_stage_task_id"),
            production_segment_id=production_segment_id,
            target_type="production_segment" if production_segment_id else None,
            target_id=production_segment_id,
            source_version=item.get("source_version") or 1,
            is_latest=True,
        )
        db.add(asset)
        saved.append(asset)
        if production_segment_id:
            segment = db.query(ProductionSegment).filter(ProductionSegment.id == production_segment_id).first()
            if segment:
                segment.status = SEGMENT_VIDEO_REVIEW_PENDING
        _record_run_event(
            db,
            run,
            "video_stage.asset_registered",
            provider_task_id=asset.provider_task_id or pixelle_task_id,
            production_segment_id=asset.production_segment_id,
            payload={"asset_id": asset.id, "asset_type": asset.asset_type, "version": asset.version},
        )
    run.status = "video_review_pending"
    run.current_stage = "video_review"
    run.updated_at = bj_now()
    db.commit()
    for asset in saved:
        db.refresh(asset)
    return saved


async def start_video_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    _assert_real_provider_path_run_type(run)
    _assert_real_short_provider_budget(db, run)
    try:
        assert_can_start_videos(db, run)
    except ValueError as exc:
        raise VideoProductionError(str(exc)) from exc
    from app.domains.video_production.production_gate_evaluator import evaluate_stage_gate

    gate_result = evaluate_stage_gate(db, run.id, stage="image_generation")
    if not gate_result.get("ready"):
        _force_review_status_after_blocked_gate(run, "image")
        db.commit()
        _raise_blocked_aggregate_gate(run, "image_generation", gate_result)
    _guard_creative_patches(db, run, "video_stage")
    frames = video_stage_frames(db, run)
    if run.run_type == REAL_SHORT_E2E:
        return await start_real_provider_stage_via_executor(db, run, "video_generation")
    image_review_trace = await _guard_provider_stage(
        db,
        run,
        "image_review",
        _stage_context(db, run, "frames", frames),
    )
    if image_review_trace is None:
        return run
    agency_trace = await _guard_provider_stage(
        db,
        run,
        "video_stage",
        _stage_context(db, run, "frames", frames),
    )
    if agency_trace is None:
        return run
    try:
        model_config = resolve_runtime_model_config(db, "video_rendering")
    except RuntimeModelConfigError as exc:
        _block_missing_provider_model_config(db, run, stage="video_stage", scene_key="video_rendering", exc=exc)
        raise VideoProductionError(str(exc)) from exc
    _assert_legacy_direct_stage_not_paid(run, model_config, "video_rendering")
    response = await submit_video_batch(
        db=db,
        run_id=run.id,
        frames=frames,
        model_config=model_config,
    )
    run.status = "video_batch_running"
    run.current_stage = "video_rendering"
    run.pixelle_stage_task_id = response["stage_task_id"]
    record_stage_task(run, "video_rendering", response["stage_task_id"])
    trace = run.model_trace_json or {}
    trace["video_rendering"] = redact_runtime_model_config(model_config)
    run.model_trace_json = trace
    run.updated_at = bj_now()
    _record_run_event(
        db,
        run,
        "video_stage.submitted",
        provider_task_id=response["stage_task_id"],
        payload={"stage": "video_rendering"},
    )
    db.commit()
    db.refresh(run)
    return run


async def sync_video_stage_results(db: Session, run_id: str) -> list[VideoProductionAsset]:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Video stage is not complete: {status.get('status')}")
    assets = mark_video_stage_assets(db, run, status.get("assets", []), pixelle_task_id=run.pixelle_stage_task_id)
    persisted_assets = persist_assets_for_review(db, assets)
    run_ai_audit_for_assets(db, run, persisted_assets)
    return assets


# -- Compose stage ----------------------------------------------------------

def build_compose_segments_for_production(db: Session, run: VideoProductionRun) -> list[dict]:
    video_assets = {
        asset.production_segment_id: asset
        for asset in db.query(VideoProductionAsset).filter(
            VideoProductionAsset.run_id == run.id,
            VideoProductionAsset.asset_type == "video_segment",
            VideoProductionAsset.is_latest.is_(True),
            VideoProductionAsset.status == "approved",
            VideoProductionAsset.copy_status == "persisted",
            VideoProductionAsset.checksum.isnot(None),
            VideoProductionAsset.storage_path.isnot(None),
        ).all()
        if asset.production_segment_id
    }
    segments = []
    for frame in build_image_stage_frames_for_segments(db, run):
        asset = video_assets.get(frame["production_segment_id"])
        if not asset:
            raise VideoProductionError(f"Approved video segment missing for segment {frame['production_segment_id']}")
        segments.append({
            "frame_id": frame["production_segment_id"],
            "video_url": _controlled_asset_url(asset),
            "duration": float(asset.duration_seconds or frame["duration"]),
            "narration": frame["narration"],
        })
    return segments


def compose_segments(db: Session, run: VideoProductionRun) -> list[dict]:
    if _is_linked_run(run):
        return build_compose_segments_for_production(db, run)
    latest_segments = latest_assets_by_frame(db, run.id, "video_segment")
    frames = (run.storyboard_json or {}).get("frames") or []
    segments = []
    for index, frame in enumerate(frames):
        frame_id = _frame_id(frame, index)
        segment = latest_segments.get(frame_id)
        if not segment or segment.status != "approved" or not _asset_is_persisted(segment):
            raise VideoProductionError(f"Approved video segment missing for frame {frame_id}")
        segments.append({
            "frame_id": frame_id,
            "video_url": _controlled_asset_url(segment),
            "duration": float(segment.duration_seconds or frame.get("duration") or 5),
            "narration": frame.get("narration", ""),
        })
    return segments


def default_edit_manifest(run: VideoProductionRun) -> dict:
    existing = run.edit_manifest_json or {}
    if existing:
        return existing
    return {
        "subtitle_style": {"position": "bottom", "font_size": 42},
        "bgm_policy": {"mode": "auto", "volume": 0.18},
        "intro_outro": {"intro_enabled": False, "outro_enabled": False},
        "watermark": {"enabled": False},
        "output_spec": {"aspect_ratio": "9:16", "resolution": "1080x1920"},
    }


def compose_model_config(db: Session) -> dict:
    return resolve_runtime_model_config(db, COMPOSE_SCENE_KEY)


async def start_compose_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    _assert_real_provider_path_run_type(run)
    _assert_real_short_provider_budget(db, run)
    try:
        assert_can_compose(db, run)
    except ValueError as exc:
        raise VideoProductionError(str(exc)) from exc
    from app.domains.video_production.production_gate_evaluator import evaluate_stage_gate

    gate_result = evaluate_stage_gate(db, run.id, stage="video_generation")
    if not gate_result.get("ready"):
        _force_review_status_after_blocked_gate(run, "video_segment")
        db.commit()
        _raise_blocked_aggregate_gate(run, "video_generation", gate_result)
    _guard_creative_patches(db, run, "compose_preflight")
    segments = compose_segments(db, run)
    edit_manifest = default_edit_manifest(run)
    if run.run_type == REAL_SHORT_E2E:
        run.edit_manifest_json = edit_manifest
        return await start_real_provider_stage_via_executor(db, run, "episode_compose")
    video_review_trace = await _guard_provider_stage(
        db,
        run,
        "video_review",
        _stage_context(db, run, "segments", segments),
    )
    if video_review_trace is None:
        return run
    agency_trace = await _guard_provider_stage(
        db,
        run,
        "compose_preflight",
        _stage_context(db, run, "segments", {"segments": segments, "edit_manifest": edit_manifest}),
    )
    if agency_trace is None:
        return run
    try:
        model_config = compose_model_config(db)
    except RuntimeModelConfigError as exc:
        _block_missing_provider_model_config(db, run, stage="compose", scene_key=COMPOSE_SCENE_KEY, exc=exc)
        raise VideoProductionError(str(exc)) from exc
    _assert_legacy_direct_stage_not_paid(run, model_config, COMPOSE_SCENE_KEY)
    response = await submit_compose(
        db=db,
        run_id=run.id,
        segments=segments,
        edit_manifest=edit_manifest,
        model_config=model_config,
    )
    run.status = "composing"
    run.current_stage = "composition"
    run.pixelle_stage_task_id = response["stage_task_id"]
    record_stage_task(run, "composition", response["stage_task_id"])
    run.edit_manifest_json = edit_manifest
    trace = dict(run.model_trace_json or {})
    trace[COMPOSE_SCENE_KEY] = redact_runtime_model_config(model_config)
    run.model_trace_json = trace
    run.updated_at = bj_now()
    _record_run_event(
        db,
        run,
        "compose_stage.submitted",
        provider_task_id=response["stage_task_id"],
        payload={"stage": "composition"},
    )
    db.commit()
    db.refresh(run)
    return run


# -- Final video writeback --------------------------------------------------

def _assert_final_asset_ready_for_writeback(
    db: Session,
    run: VideoProductionRun,
    asset: VideoProductionAsset,
    *,
    gate_result: dict | None = None,
) -> None:
    if asset.asset_type != "final_video":
        raise VideoProductionError("Asset is not a final video")
    if not asset.is_latest:
        _raise_stale_asset(asset)
    latest = latest_assets_by_frame(db, asset.run_id, "final_video").get(asset.frame_id)
    if latest and latest.id != asset.id:
        _raise_stale_asset(asset)
    if asset.status != "approved":
        raise ProductionRepairableError(
            code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
            message="Final video must be human-approved before writeback.",
            cause="final_asset_not_approved",
            repair_action="Approve the latest persisted final video asset.",
            repair_route=f"/video-production/{asset.run_id}",
            retryable=True,
            affected_ids=[asset.id],
        )
    if asset.copy_status != "persisted" or not asset.checksum or not asset.storage_path:
        raise ProductionRepairableError(
            code=ProductionErrorCode.ASSET_STORAGE_FAILED,
            message="Final video has not been persisted and cannot be written back.",
            cause="final_asset_not_persisted",
            repair_action="Retry final video persistence or regenerate the final video.",
            repair_route=f"/video-production/{asset.run_id}",
            retryable=True,
            affected_ids=[asset.id],
        )
    writeback_approval = db.query(VideoReviewRecord.id).filter(
        VideoReviewRecord.asset_id == asset.id,
        VideoReviewRecord.run_id == run.id,
        VideoReviewRecord.review_type.in_(("human", "auto")),
        VideoReviewRecord.status == "approved",
    ).order_by(VideoReviewRecord.created_at.desc()).first()
    if not writeback_approval:
        raise ProductionRepairableError(
            code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
            message="Final video requires an approval record before writeback.",
            cause="final_human_approval_missing",
            repair_action="Approve the latest persisted final video asset before completing the run.",
            repair_route=f"/video-production/{asset.run_id}",
            retryable=True,
            affected_ids=[asset.id],
        )
    if gate_result is None:
        from app.domains.video_production.production_gate_evaluator import evaluate_stage_gate

        gate_result = evaluate_stage_gate(db, run.id, stage="episode_compose")
    if not gate_result.get("ready"):
        raise ProductionRepairableError(
            code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
            message="Final video gate is blocked and cannot be written back.",
            cause="final_gate_blocked",
            repair_action="Approve the latest persisted final video asset.",
            repair_route=f"/video-production/{asset.run_id}",
            retryable=True,
            affected_ids=[asset.id],
        )


def complete_final_video(
    db: Session,
    run: VideoProductionRun,
    asset: VideoProductionAsset,
    *,
    gate_result: dict | None = None,
) -> VideoProductionAsset:
    from app.db.models.video_library import GeneratedVideo
    from app.db_models import Series

    _assert_final_asset_ready_for_writeback(db, run, asset, gate_result=gate_result)
    duration = int(asset.duration_seconds or 0)
    episode = db.query(Episode).filter(Episode.id == run.episode_id).first()
    series = db.query(Series).filter(Series.id == run.series_id).first() if run.series_id else None
    title = (episode.title if episode and episode.title else series.title if series else "Generated video")
    keyword = title or run.id

    if episode:
        episode.video_url = _controlled_asset_url(asset)
        episode.duration_seconds = duration or episode.duration_seconds
        episode.status = "done"

    video = db.query(GeneratedVideo).filter(GeneratedVideo.pixelle_task_id == run.id).first()
    video_path = asset.local_path or asset.storage_path or asset.url
    if not video:
        video = GeneratedVideo(
            keyword=keyword,
            title=title,
            video_path=video_path,
            duration=duration,
            status="completed",
            pixelle_task_id=run.id,
        )
        db.add(video)
    else:
        video.video_path = video_path
        video.duration = duration
        video.status = "completed"

    run.status = "completed"
    run.current_stage = "completed"
    run.completed_at = bj_now()
    run.updated_at = bj_now()
    _record_run_event(
        db,
        run,
        "run.completed",
        provider_task_id=asset.provider_task_id or asset.pixelle_task_id,
        payload={"asset_id": asset.id, "video_url": _controlled_asset_url(asset)},
    )
    _record_run_event(
        db,
        run,
        "final_video.completed",
        provider_task_id=asset.provider_task_id or asset.pixelle_task_id,
        payload={"asset_id": asset.id, "video_url": _controlled_asset_url(asset)},
    )
    db.commit()
    db.refresh(asset)
    return asset


def approve_final_video_asset(db: Session, asset: VideoProductionAsset, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if asset.asset_type != "final_video":
        raise VideoProductionError("Asset is not a final video")
    if run.status != "final_review_pending" or run.current_stage != "final_review":
        raise VideoProductionError("Final video can be approved only during final review")
    if asset.status != "review_pending":
        raise VideoProductionError("Final video asset must be review_pending before approval")
    if not asset.is_latest:
        _raise_stale_asset(asset)
    latest = latest_assets_by_frame(db, asset.run_id, "final_video").get(asset.frame_id)
    if latest and latest.id != asset.id:
        _raise_stale_asset(asset)
    _assert_asset_persisted_for_review(asset)
    asset.status = "approved"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="approved",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
        **_review_snapshot(asset),
    ))
    db.flush()
    from app.domains.video_production.production_gate_evaluator import evaluate_stage_gate

    gate_result = evaluate_stage_gate(db, run.id, stage="episode_compose")
    return complete_final_video(db, run, asset, gate_result=gate_result)


def reject_final_video_asset(db: Session, asset: VideoProductionAsset, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if asset.asset_type != "final_video":
        raise VideoProductionError("Asset is not a final video")
    if run.status != "final_review_pending" or run.current_stage != "final_review":
        raise VideoProductionError("Final video can be rejected only during final review")
    if not asset.is_latest:
        _raise_stale_asset(asset)
    latest = latest_assets_by_frame(db, asset.run_id, "final_video").get(asset.frame_id)
    if latest and latest.id != asset.id:
        _raise_stale_asset(asset)
    if asset.status != "review_pending":
        raise VideoProductionError("Final video asset must be review_pending for human rejection")
    asset.status = "rejected"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="rejected",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
        **_review_snapshot(asset),
    ))
    run.status = "video_segments_approved"
    run.current_stage = "video_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def run_final_audit_for_asset(db: Session, run: VideoProductionRun, asset: VideoProductionAsset) -> VideoProductionAsset:
    audit_model_missing = False
    try:
        audit_model = resolve_runtime_model_config(db, "quality_audit")
    except Exception:
        audit_model = {}
        audit_model_missing = True

    if not audit_model or not audit_model.get("api_key"):
        audit_model_missing = True
        result = {"score": 0.0, "pass_fail": False, "issues": ["Final audit model not configured"]}
    else:
        try:
            from app.domains.quality_audit.audit_router import _do_audit
            result = _do_audit(audit_model, _controlled_asset_url(asset), None)
        except Exception as exc:
            result = {"score": 0.0, "pass_fail": False, "issues": [str(exc)]}

    gate = classify_audit_gate(result, error=False)
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=run.id,
        review_type="ai",
        status=gate["gate_status"],
        score=gate["score"],
        issues_json=gate.get("issues", []),
        model_trace_json={"auditor_model": audit_model.get("provider", "unknown"), "auditor_model_name": _runtime_model_name(audit_model)},
        **_review_snapshot(asset),
    ))
    if gate["gate_status"] == "approved":
        asset.status = "review_pending"
    else:
        asset.status = "review_pending"

    run.status = "final_review_pending"
    run.current_stage = "final_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def persist_final_video(db: Session, run: VideoProductionRun, item: dict, *, run_audit: bool = True) -> VideoProductionAsset:
    metadata = item.get("metadata") or {}
    duration = int(metadata.get("duration") or 0)
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "final_video",
        VideoProductionAsset.pixelle_task_id == run.pixelle_stage_task_id,
    ).first()
    if existing:
        return existing
    _demote_latest_assets(db, run.id, "final_video", frame_id="final")
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url=item.get("url", ""),
        source_url=item.get("source_url") or item.get("url", ""),
        local_path=item.get("local_path", ""),
        thumbnail_url=item.get("thumbnail_url", ""),
        storage_path=item.get("storage_path"),
        copy_status=item.get("copy_status", "registered"),
        checksum=item.get("checksum"),
        size_bytes=item.get("size_bytes"),
        duration_seconds=duration,
        version=_next_asset_version(db, run.id, "final", "final_video"),
        metadata_json=metadata,
        status="review_pending",
        pixelle_task_id=run.pixelle_stage_task_id,
        provider_task_id=item.get("provider_task_id") or run.pixelle_stage_task_id,
        provider_stage_task_id=item.get("provider_stage_task_id"),
        is_latest=True,
    )
    db.add(asset)
    db.flush()
    _record_run_event(
        db,
        run,
        "compose_stage.asset_registered",
        provider_task_id=asset.provider_task_id or asset.pixelle_task_id,
        payload={"asset_id": asset.id, "asset_type": asset.asset_type, "version": asset.version},
    )
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    if not run_audit:
        return asset
    return run_final_audit_for_asset(db, run, asset)


async def sync_compose_stage_results(db: Session, run_id: str) -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Compose stage is not complete: {status.get('status')}")
    final_assets = [item for item in status.get("assets", []) if item.get("asset_type") == "final_video"]
    if not final_assets:
        raise VideoProductionError("Compose stage returned no final video")
    asset = persist_final_video(db, run, final_assets[0], run_audit=False)
    persisted_assets = persist_assets_for_review(db, [asset])
    if not persisted_assets:
        return asset
    return run_final_audit_for_asset(db, run, persisted_assets[0])


# -- Single-item regeneration -----------------------------------------------

async def start_asset_regeneration(db: Session, asset_id: str) -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    _assert_real_provider_path_run_type(run)
    _assert_regeneration_not_direct_paid_run(run)
    _assert_real_short_provider_budget(db, run)
    if asset.asset_type == "image":
        frame = image_stage_frame_for_asset(db, run, asset.frame_id)
        scene_key = "image_generation"
        try:
            model_config = resolve_runtime_model_config(db, scene_key)
        except RuntimeModelConfigError as exc:
            _block_regeneration_missing_provider_model_config(
                db,
                run,
                asset,
                stage="image_stage",
                scene_key=scene_key,
                exc=exc,
            )
            raise VideoProductionError(str(exc)) from exc
        response = await submit_image_batch(
            db=db,
            run_id=run.id,
            episode_id=run.episode_id,
            frames=[frame],
            model_config=model_config,
        )
    elif asset.asset_type == "video_segment":
        scene_key = "video_rendering"
        try:
            model_config = resolve_runtime_model_config(db, scene_key)
        except RuntimeModelConfigError as exc:
            _block_regeneration_missing_provider_model_config(
                db,
                run,
                asset,
                stage="video_stage",
                scene_key=scene_key,
                exc=exc,
            )
            raise VideoProductionError(str(exc)) from exc
        response = await submit_video_batch(
            db=db,
            run_id=run.id,
            frames=[video_stage_frame_for_asset(db, run, asset.frame_id, prefer_controlled_assets=True)],
            model_config=model_config,
        )
    else:
        raise VideoProductionError(f"Unsupported regeneration asset type: {asset.asset_type}")

    asset.status = "regenerating"
    asset.pixelle_task_id = response["stage_task_id"]
    record_stage_task(run, f"regeneration:{asset.asset_type}:{asset.frame_id}", response["stage_task_id"])
    db.commit()
    db.refresh(asset)
    return asset


def _generated_or_old(generated: dict, key: str, old_value):
    value = generated.get(key)
    return value if value is not None else old_value


async def sync_regenerated_asset(db: Session, asset_id: str) -> VideoProductionAsset:
    old = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not old:
        raise VideoProductionError("Asset not found")
    if not old.pixelle_task_id:
        raise VideoProductionError("Asset has no regeneration task")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == old.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    status = await get_stage_task(db, old.pixelle_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Regeneration task is not complete: {status.get('status')}")
    generated = next((item for item in status.get("assets", []) if item.get("frame_id") == old.frame_id), None)
    if not generated:
        raise VideoProductionError("Regeneration returned no matching asset")
    production_segment_id = _generated_or_old(generated, "production_segment_id", old.production_segment_id)
    target_type = _generated_or_old(generated, "target_type", old.target_type)
    target_id = _generated_or_old(generated, "target_id", old.target_id)
    source_version = _generated_or_old(generated, "source_version", old.source_version)
    if production_segment_id:
        _demote_latest_assets(db, old.run_id, old.asset_type, production_segment_id=production_segment_id)
        version = _next_asset_version_for_target(
            db,
            old.run_id,
            production_segment_id,
            old.asset_type,
            production_segment_id=production_segment_id,
        )
    else:
        _demote_latest_assets(db, old.run_id, old.asset_type, frame_id=old.frame_id)
        version = _next_asset_version(db, old.run_id, old.frame_id, old.asset_type)
    old.status = "regenerating"
    new_asset = VideoProductionAsset(
        run_id=old.run_id,
        episode_id=old.episode_id,
        frame_id=production_segment_id or old.frame_id,
        asset_type=old.asset_type,
        stage=old.stage,
        url=generated.get("url", ""),
        source_url=generated.get("source_url") or generated.get("url", ""),
        local_path=generated.get("local_path", ""),
        thumbnail_url=generated.get("thumbnail_url", ""),
        storage_path=generated.get("storage_path"),
        copy_status=generated.get("copy_status") or "registered",
        checksum=generated.get("checksum"),
        size_bytes=generated.get("size_bytes"),
        duration_seconds=(generated.get("metadata") or {}).get("duration"),
        version=version,
        metadata_json=generated.get("metadata", {}),
        status="review_pending",
        pixelle_task_id=old.pixelle_task_id,
        provider_task_id=generated.get("provider_task_id") or old.pixelle_task_id,
        provider_stage_task_id=generated.get("provider_stage_task_id") or old.provider_stage_task_id,
        production_segment_id=production_segment_id,
        target_type=target_type,
        target_id=target_id,
        source_version=source_version,
        is_latest=True,
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    persisted_assets = persist_assets_for_review(db, [new_asset])
    run_ai_audit_for_assets(db, run, persisted_assets)
    db.refresh(new_asset)
    return new_asset


# Legacy regeneration (manual payload) — kept for backward compat
def create_regenerated_image_asset(db: Session, asset_id: str, generated: dict) -> VideoProductionAsset:
    old = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not old:
        raise VideoProductionError("Asset not found")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == old.run_id).first()
    old.status = "regenerating"
    new_asset = VideoProductionAsset(
        run_id=old.run_id,
        episode_id=old.episode_id,
        frame_id=old.frame_id,
        asset_type="image",
        stage="image_generation",
        url=generated.get("url", ""),
        source_url=generated.get("source_url") or generated.get("url", ""),
        local_path=generated.get("local_path", ""),
        thumbnail_url=generated.get("thumbnail_url", ""),
        storage_path=generated.get("storage_path"),
        copy_status=generated.get("copy_status") or "registered",
        checksum=generated.get("checksum"),
        size_bytes=generated.get("size_bytes"),
        version=_next_asset_version(db, old.run_id, old.frame_id, "image"),
        metadata_json=generated.get("metadata", {}),
        status="review_pending",
        pixelle_task_id=generated.get("pixelle_task_id"),
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    persisted_assets = persist_assets_for_review(db, [new_asset])
    if run and persisted_assets:
        run_ai_audit_for_assets(db, run, persisted_assets)
    db.refresh(new_asset)
    return new_asset
