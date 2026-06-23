import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

SMOKE_EXPERT_TIMEOUT_DEFAULT_SECONDS = "180"
SMOKE_REFERENCE_SYNC_POLL_ATTEMPTS_DEFAULT = "180"
os.environ.setdefault("DY_AUTO_ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS", SMOKE_EXPERT_TIMEOUT_DEFAULT_SECONDS)
os.environ.setdefault("DY_AUTO_DEFERRED_STAGE_GATE_TIMEOUT_SECONDS", SMOKE_EXPERT_TIMEOUT_DEFAULT_SECONDS)
os.environ.setdefault("DY_AUTO_REFERENCE_SYNC_POLL_ATTEMPTS", SMOKE_REFERENCE_SYNC_POLL_ATTEMPTS_DEFAULT)

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.database import SessionLocal
from app.db.models import Episode, GeneratedVideo, VideoProductionAsset, VideoProductionRun
from app.domains.video_production import one_sentence_video_service as one_sentence_service
from app.domains.creative_library import reference_asset_service
one_sentence_service.ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS = float(
    os.getenv("DY_AUTO_ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS", SMOKE_EXPERT_TIMEOUT_DEFAULT_SECONDS)
)
reference_asset_service.REFERENCE_SYNC_POLL_ATTEMPTS = int(
    os.getenv("DY_AUTO_REFERENCE_SYNC_POLL_ATTEMPTS", SMOKE_REFERENCE_SYNC_POLL_ATTEMPTS_DEFAULT)
)

from app.domains.video_production.one_sentence_video_service import (
    ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
    complete_one_sentence_reference_generation,
    create_one_sentence_video,
)
from app.domains.video_production.production_worker_service import run_real_worker_step
from app.domains.model_configuration.runtime_model_config import redact_runtime_model_config, resolve_runtime_model_config
from app.domains.video_production.video_production_run_types import REAL_SHORT_E2E
from app.domains.video_production.video_production_service import approve_asset, start_compose_stage, start_video_stage


ALLOW_ENV = "DY_AUTO_ALLOW_REAL_PROVIDER_E2E"
EXPECTED_EXPERT_GATE_PROVIDER = "bailian"
EXPECTED_EXPERT_GATE_MODEL = "qwen3.7-plus"
IMAGE_STAGE_DONE_STATUSES = {
    "image_review_pending",
    "image_human_review_required",
    "image_approved",
    "video_batch_running",
    "video_review_pending",
    "video_human_review_required",
    "video_segments_approved",
    "composing",
    "final_review_pending",
    "completed",
}
VIDEO_STAGE_STARTED_STATUSES = {
    "video_batch_running",
    "video_review_pending",
    "video_human_review_required",
    "video_segments_approved",
    "composing",
    "final_review_pending",
    "completed",
}
VIDEO_STAGE_DONE_STATUSES = {
    "video_review_pending",
    "video_human_review_required",
    "video_segments_approved",
    "composing",
    "final_review_pending",
    "completed",
}
COMPOSE_STAGE_STARTED_STATUSES = {"composing", "final_review_pending", "completed"}
COMPOSE_STAGE_DONE_STATUSES = {"final_review_pending", "completed"}
STOP_ON_ERROR_CODES = {"PROVIDER_THROTTLED", "BUDGET_BLOCKED"}
PAID_SMOKE_WORKER_BATCH_SIZE = 1


def _log(event: str, **payload) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a paid Bailian one-sentence E2E smoke.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--title", default="百炼一句话成片 Smoke")
    parser.add_argument("--budget", type=float, default=5.0)
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--worker-batch-size", type=int, default=1)
    parser.add_argument("--max-worker-rounds", type=int, default=80)
    parser.add_argument("--resume-run-id", default="")
    parser.add_argument("--retry-provider-blockers", action="store_true")
    parser.add_argument(
        "--bypass-expert-gates",
        action="store_true",
        help="Use smoke-only pass-through expert gates instead of real LLM expert review.",
    )
    return parser.parse_args()


class _SmokePassAgencyOrchestrator:
    async def run_style_lock_review(self, *args, **kwargs):
        return {"stage_status": "passed", "invocation_ids": ["smoke-style"], "invocations": []}

    async def run_storyboard_review(self, *args, **kwargs):
        return {"stage_status": "passed", "invocation_ids": ["smoke-storyboard"], "invocations": []}


async def _smoke_pass_provider_stage(*args, **kwargs):
    return {"stage_status": "passed", "invocation_ids": ["smoke-stage"], "invocations": []}


def _install_smoke_gate_overrides() -> None:
    import app.domains.video_production.one_sentence_video_service as one_sentence_service
    import app.domains.video_production.video_production_service as video_service

    one_sentence_service.AgencyOrchestrator = _SmokePassAgencyOrchestrator
    video_service._guard_provider_stage = _smoke_pass_provider_stage


def _preflight_expert_gate_model(db) -> dict:
    resolved = resolve_runtime_model_config(db, "llm_agency_expert_review")
    redacted = redact_runtime_model_config(resolved)
    if (
        resolved["provider"] != EXPECTED_EXPERT_GATE_PROVIDER
        or resolved["model"] != EXPECTED_EXPERT_GATE_MODEL
    ):
        _log(
            "expert_gate_model_mismatch",
            expected_provider=EXPECTED_EXPERT_GATE_PROVIDER,
            expected_model=EXPECTED_EXPERT_GATE_MODEL,
            resolved=redacted,
        )
        raise RuntimeError(
            "Expert gates must resolve to Bailian qwen3.7-plus; "
            f"got provider={resolved['provider']} model={resolved['model']}"
        )
    _log("expert_gate_model_ready", resolved=redacted)
    return resolved


def _prepare_expert_gates(db, args: argparse.Namespace) -> dict | None:
    if args.bypass_expert_gates:
        _install_smoke_gate_overrides()
        _log("expert_gates_bypassed")
        return None
    return _preflight_expert_gate_model(db)


def _run_worker_rounds(db, run_id: str, *, lease_prefix: str, batch_size: int, max_rounds: int) -> list[dict]:
    results = []
    idle_rounds = 0
    for index in range(max_rounds):
        result = run_real_worker_step(
            db,
            run_id,
            lease_id=f"{lease_prefix}-{index + 1}",
            batch_size=batch_size,
        )
        results.append(result)
        _log(
            "worker_step",
            lease_id=result["lease_id"],
            processed=result["processed"],
            remaining=result["remaining"],
            item_statuses=[
                {
                    "ok": item.get("ok"),
                    "status": item.get("status"),
                    "error_code": item.get("error_code"),
                }
                for item in result.get("items", [])
            ],
        )
        if result["processed"] == 0:
            idle_rounds += 1
        else:
            idle_rounds = 0
        if result["remaining"] == 0 and idle_rounds:
            break
        time.sleep(1)
    return results


def _complete_background_reference_if_pending(db, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
    if run.status != ONE_SENTENCE_REFERENCE_RUNNING_STATUS:
        return run
    trace = dict((run.model_trace_json or {}).get("one_sentence") or {})
    autostart = bool(trace.get("autostart_images_after_references"))
    _log("reference_generation_resume", run_id=run.id, autostart_images=autostart)
    asyncio.run(
        complete_one_sentence_reference_generation(
            db,
            run.id,
            autostart_images=autostart,
        )
    )
    db.expire_all()
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
    _log("reference_generation_completed", run_status=run.status, current_stage=run.current_stage)
    return run


def _run_stage_until(
    db,
    run_id: str,
    *,
    stage: str,
    done_statuses: set[str],
    lease_prefix: str,
    batch_size: int,
    max_rounds: int,
    retry_provider_blockers: bool = False,
) -> None:
    if batch_size != PAID_SMOKE_WORKER_BATCH_SIZE:
        _log("worker_batch_size_forced", requested=batch_size, effective=PAID_SMOKE_WORKER_BATCH_SIZE)
        batch_size = PAID_SMOKE_WORKER_BATCH_SIZE
    for index in range(max_rounds):
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
        if run.status in done_statuses:
            _log("stage_ready", stage=stage, run_status=run.status)
            return
        if retry_provider_blockers:
            _clear_stage_stop_error_codes(db, run, stage)
        existing_stop_code = _existing_stage_stop_error_code(db, run, stage)
        if existing_stop_code:
            raise RuntimeError(f"Stage {stage} stopped on existing {existing_stop_code}; run_status={run.status}")
        result = run_real_worker_step(
            db,
            run_id,
            lease_id=f"{lease_prefix}-{index + 1}",
            batch_size=batch_size,
        )
        _log(
            "worker_step",
            lease_id=result["lease_id"],
            processed=result["processed"],
            remaining=result["remaining"],
            item_statuses=[
                {
                    "ok": item.get("ok"),
                    "status": item.get("status"),
                    "error_code": item.get("error_code"),
                }
                for item in result.get("items", [])
            ],
        )
        stop_code = _stage_stop_error_code(result)
        if stop_code:
            raise RuntimeError(f"Stage {stage} stopped on {stop_code}; run_status={run.status}")
        if result["processed"] > 0:
            continue
        delay = _next_retry_delay_seconds(db, run.production_plan_id, stage)
        if delay is None:
            break
        sleep_seconds = max(1, min(delay, 65))
        _log("stage_wait", stage=stage, retry_after_seconds=sleep_seconds)
        time.sleep(sleep_seconds)
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
    raise RuntimeError(f"Stage {stage} did not reach {sorted(done_statuses)}; run_status={run.status}")


def _stage_stop_error_code(result: dict) -> str | None:
    for item in result.get("items", []):
        code = item.get("error_code")
        if code in STOP_ON_ERROR_CODES:
            return code
    return None


def _existing_stage_stop_error_code(db, run: VideoProductionRun, stage: str) -> str | None:
    if not run.production_episode_id:
        return None
    row = db.execute(
        text("""
        select error_code
        from production_jobs job
        where job.plan_id = :plan_id
          and job.stage = :stage
          and job.status = 'retry_wait'
          and job.error_code in ('PROVIDER_THROTTLED', 'BUDGET_BLOCKED')
          and (
            (job.target_type = 'production_episode' and job.target_id = :production_episode_id)
            or (
              job.target_type = 'production_segment'
              and job.target_id in (
                select segment.id
                from production_segments segment
                join production_shots shot on segment.shot_plan_id = shot.id
                join production_scenes scene on shot.scene_plan_id = scene.id
                where scene.episode_plan_id = :production_episode_id
              )
            )
          )
        order by job.updated_at desc
        limit 1
        """),
        {"plan_id": run.production_plan_id, "production_episode_id": run.production_episode_id, "stage": stage},
    ).first()
    return str(row[0]) if row else None


def _clear_stage_stop_error_codes(db, run: VideoProductionRun, stage: str) -> None:
    if not run.production_episode_id:
        raise RuntimeError("Cannot retry provider blockers without a production episode scope.")
    result = db.execute(
        text("""
        update production_jobs
        set error_code = null,
            error_message = null,
            retry_after = null
        where plan_id = :plan_id
          and stage = :stage
          and status = 'retry_wait'
          and error_code in ('PROVIDER_THROTTLED', 'BUDGET_BLOCKED')
          and (
            (target_type = 'production_episode' and target_id = :production_episode_id)
            or (
              target_type = 'production_segment'
              and target_id in (
                select segment.id
                from production_segments segment
                join production_shots shot on segment.shot_plan_id = shot.id
                join production_scenes scene on shot.scene_plan_id = scene.id
                where scene.episode_plan_id = :production_episode_id
              )
            )
          )
        """),
        {"plan_id": run.production_plan_id, "production_episode_id": run.production_episode_id, "stage": stage},
    )
    db.commit()
    if result.rowcount:
        _log("stage_provider_blockers_retry_enabled", stage=stage, cleared_jobs=result.rowcount)


def _run_stage_unless_done(
    db,
    run_id: str,
    *,
    stage: str,
    done_statuses: set[str],
    lease_prefix: str,
    batch_size: int,
    max_rounds: int,
    retry_provider_blockers: bool = False,
) -> None:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
    if run.status in done_statuses:
        _log("stage_skip", stage=stage, run_status=run.status)
        return
    _run_stage_until(
        db,
        run_id,
        stage=stage,
        done_statuses=done_statuses,
        lease_prefix=lease_prefix,
        batch_size=batch_size,
        max_rounds=max_rounds,
        retry_provider_blockers=retry_provider_blockers,
    )


def _next_retry_delay_seconds(db, plan_id: str, stage: str) -> int | None:
    rows = db.execute(
        text("""
        select retry_after
        from production_jobs
        where plan_id = :plan_id
          and stage = :stage
          and status in ('retry_wait', 'queued', 'leased', 'running')
        order by retry_after asc
        """),
        {"plan_id": plan_id, "stage": stage},
    ).fetchall()
    if not rows:
        return None
    now = datetime.now()
    retry_values = [row[0] for row in rows if row[0]]
    if not retry_values:
        return 5
    try:
        retry_at = datetime.fromisoformat(str(retry_values[0]))
    except ValueError:
        return 5
    return max(1, int((retry_at - now).total_seconds()) + 1)


def _approve_assets(db, run_id: str, asset_type: str) -> list[str]:
    assets = (
        db.query(VideoProductionAsset)
        .filter(
            VideoProductionAsset.run_id == run_id,
            VideoProductionAsset.asset_type == asset_type,
            VideoProductionAsset.status == "review_pending",
            VideoProductionAsset.is_latest.is_(True),
        )
        .order_by(VideoProductionAsset.created_at.asc())
        .all()
    )
    approved_ids = []
    for asset in assets:
        approve_asset(db, asset.id, reviewer_user_id="paid-smoke", comment="paid smoke auto approval")
        approved_ids.append(asset.id)
    _log("assets_approved", asset_type=asset_type, count=len(approved_ids))
    return approved_ids


def _main() -> None:
    if os.getenv(ALLOW_ENV) != "1":
        raise SystemExit(f"Set {ALLOW_ENV}=1 to run paid provider smoke.")
    os.environ.setdefault("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    args = _parse_args()

    db = SessionLocal()
    try:
        _prepare_expert_gates(db, args)
        if args.resume_run_id:
            run = db.query(VideoProductionRun).filter(VideoProductionRun.id == args.resume_run_id).one()
            episode = db.query(Episode).filter(Episode.id == run.episode_id).one()
            _log("resume", run_id=run.id, episode_id=episode.id, run_status=run.status)
        else:
            _log("create_start", duration=args.duration, budget=args.budget)
            result = asyncio.run(create_one_sentence_video(
                db,
                prompt=args.prompt,
                title=args.title,
                budget_limit=args.budget,
                target_duration_seconds=args.duration,
                run_type=REAL_SHORT_E2E,
                autostart_images=True,
            ))
            run = result["run"]
            episode = result["episode"]
            _log(
                "created",
                run_id=run.id,
                episode_id=episode.id,
                run_status=run.status,
                background_reference_pending=bool(result.get("background_reference_pending")),
                frame_count=(episode.storyboard_json or {}).get("frame_count"),
                materialized_frame_count=(episode.storyboard_json or {}).get("materialized_frame_count"),
            )

        run = _complete_background_reference_if_pending(db, run.id)
        _run_stage_unless_done(
            db,
            run.id,
            stage="image_generation",
            done_statuses=IMAGE_STAGE_DONE_STATUSES,
            lease_prefix="smoke-images",
            batch_size=args.worker_batch_size,
            max_rounds=args.max_worker_rounds,
            retry_provider_blockers=args.retry_provider_blockers,
        )
        _approve_assets(db, run.id, "image")

        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run.id).one()
        if run.status in VIDEO_STAGE_STARTED_STATUSES:
            _log("start_video_stage_skip", run_status=run.status)
        else:
            _log("start_video_stage", run_status=run.status)
            asyncio.run(start_video_stage(db, run.id))
        _run_stage_unless_done(
            db,
            run.id,
            stage="video_generation",
            done_statuses=VIDEO_STAGE_DONE_STATUSES,
            lease_prefix="smoke-videos",
            batch_size=args.worker_batch_size,
            max_rounds=args.max_worker_rounds,
            retry_provider_blockers=args.retry_provider_blockers,
        )
        _approve_assets(db, run.id, "video_segment")

        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run.id).one()
        if run.status in COMPOSE_STAGE_STARTED_STATUSES:
            _log("start_compose_stage_skip", run_status=run.status)
        else:
            _log("start_compose_stage", run_status=run.status)
            asyncio.run(start_compose_stage(db, run.id))
        _run_stage_unless_done(
            db,
            run.id,
            stage="episode_compose",
            done_statuses=COMPOSE_STAGE_DONE_STATUSES,
            lease_prefix="smoke-compose",
            batch_size=1,
            max_rounds=args.max_worker_rounds,
            retry_provider_blockers=args.retry_provider_blockers,
        )
        _approve_assets(db, run.id, "final_video")

        db.expire_all()
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run.id).one()
        episode = db.query(Episode).filter(Episode.id == episode.id).one()
        final_asset = (
            db.query(VideoProductionAsset)
            .filter(
                VideoProductionAsset.run_id == run.id,
                VideoProductionAsset.asset_type == "final_video",
                VideoProductionAsset.is_latest.is_(True),
            )
            .order_by(VideoProductionAsset.created_at.desc())
            .first()
        )
        generated_video = db.query(GeneratedVideo).filter(GeneratedVideo.pixelle_task_id == run.id).first()
        _log(
            "completed",
            ok=run.status == "completed",
            run_id=run.id,
            run_status=run.status,
            episode_status=episode.status,
            episode_video_url=episode.video_url,
            final_asset_id=final_asset.id if final_asset else None,
            final_storage_path=final_asset.storage_path if final_asset else None,
            final_checksum=final_asset.checksum if final_asset else None,
            final_size_bytes=final_asset.size_bytes if final_asset else None,
            generated_video_id=generated_video.id if generated_video else None,
        )
    except Exception as exc:
        db.rollback()
        _log("failed", error_type=exc.__class__.__name__, error=str(exc))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    _main()
