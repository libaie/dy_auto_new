import asyncio
import time

from app.db.models import ProductionEpisode, ProductionJob, ProductionPlan, ProductionSegment, VideoProductionAsset
from app.domains.video_production.mock_scale_scheduler_service import create_mock_scale_run, advance_mock_scheduler
from app.domains.video_production.production_status import JOB_COMPLETED, JOB_LEASED, JOB_QUEUED
from app.domains.video_production.production_tree_service import get_run_tree
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE


def test_create_240_minute_mock_scale_run_links_plan_episode_and_jobs(db):
    result = create_mock_scale_run(
        db,
        prompt="A long-form mystery series about signal hunters.",
        title="Signal Hunters",
        target_duration_seconds=240 * 60,
    )

    run = result["run"]
    assert run.run_type == MOCK_SERIES_SCALE
    assert run.production_plan_id
    assert run.production_episode_id
    assert run.model_trace_json["provider_free"] is True
    assert run.model_trace_json["provider_calls"] == 0

    assert db.query(ProductionPlan).filter_by(id=run.production_plan_id).one()
    assert db.query(ProductionEpisode).filter_by(id=run.production_episode_id).one()

    segments = db.query(ProductionSegment).all()
    jobs = db.query(ProductionJob).all()
    assert 200 <= len(segments) <= 400
    assert len(jobs) == len(segments)
    assert {job.status for job in jobs} == {JOB_QUEUED}
    assert all(job.stage == "mock_segment_render" for job in jobs)
    assert all(job.provider_task_id == "mock:provider-free" for job in jobs)


def test_create_480_minute_mock_scale_run_is_accepted_and_bounded(db):
    started = time.perf_counter()
    result = create_mock_scale_run(
        db,
        prompt="A stress-scale mock series.",
        title="Stress Scale",
        target_duration_seconds=480 * 60,
    )
    elapsed = time.perf_counter() - started

    assert result["run"].run_type == MOCK_SERIES_SCALE
    assert db.query(ProductionSegment).count() > 0
    assert db.query(ProductionJob).count() > 0
    assert db.query(ProductionSegment).count() <= 600
    assert elapsed < 5


def test_advance_mock_scheduler_batches_until_complete_and_is_resumable(db):
    result = create_mock_scale_run(
        db,
        prompt="A resumable mock run.",
        title="Resume",
        target_duration_seconds=60 * 60,
    )
    run = result["run"]
    total_jobs = db.query(ProductionJob).count()

    first = advance_mock_scheduler(db, run.id, limit=7)
    assert first["processed"] == 7
    assert db.query(ProductionJob).filter_by(status=JOB_COMPLETED).count() == 7
    assert db.query(ProductionJob).filter_by(status=JOB_QUEUED).count() == total_jobs - 7

    processed = first["processed"]
    while processed < total_jobs:
        processed += advance_mock_scheduler(db, run.id, limit=11)["processed"]

    db.refresh(run)
    assert db.query(ProductionJob).filter_by(status=JOB_COMPLETED).count() == total_jobs
    assert run.status == "completed"
    assert run.current_stage == "completed"
    assert run.completed_at is not None

    completed_at = run.completed_at
    final = advance_mock_scheduler(db, run.id, limit=11)
    db.refresh(run)
    assert final["processed"] == 0
    assert db.query(ProductionJob).filter_by(status=JOB_COMPLETED).count() == total_jobs
    assert run.completed_at == completed_at


def test_advance_mock_scheduler_registers_segment_assets_for_production_tree(db):
    result = create_mock_scale_run(
        db,
        prompt="A production tree asset smoke run.",
        title="Tree Assets",
        target_duration_seconds=2 * 60,
    )
    run = result["run"]

    advanced = advance_mock_scheduler(db, run.id, limit=10)

    assert advanced["completed"] is True
    assets = db.query(VideoProductionAsset).filter_by(run_id=run.id).all()
    assert len(assets) == 2
    assert {asset.asset_type for asset in assets} == {"video_segment"}
    assert all(asset.production_segment_id for asset in assets)
    assert all(asset.status == "approved" for asset in assets)
    assert all(asset.copy_status == "persisted" for asset in assets)

    tree = get_run_tree(db, run.production_plan_id, run_id=run.id)
    segments = [
        segment
        for episode in tree["episodes"]
        for scene in episode["scenes"]
        for shot in scene["shots"]
        for segment in shot["segments"]
    ]
    assert len(segments) == 2
    assert all(segment["status"] == "completed" for segment in segments)
    assert all("mock_segment_render" in segment["jobs"] for segment in segments)
    assert all("video_segment" in segment["latest_assets"] for segment in segments)


def test_advance_mock_scheduler_does_not_count_stale_candidate(db, monkeypatch):
    from sqlalchemy.orm import Query

    result = create_mock_scale_run(
        db,
        prompt="A stale candidate race.",
        title="Race",
        target_duration_seconds=10 * 60,
    )
    run = result["run"]
    raced = {"done": False, "job_id": None}
    original_update = Query.update

    def race_first_claim(query, values, *args, **kwargs):
        if not raced["done"] and values.get("status") == JOB_LEASED:
            raced["done"] = True
            first_job = db.query(ProductionJob).filter(ProductionJob.status == JOB_QUEUED).order_by(ProductionJob.created_at.asc()).first()
            raced["job_id"] = first_job.id
            db.query(ProductionJob).filter(ProductionJob.id == first_job.id).update(
                {"status": JOB_LEASED},
                synchronize_session=False,
            )
            db.commit()
            return 0
        return original_update(query, values, *args, **kwargs)

    monkeypatch.setattr(Query, "update", race_first_claim)

    advanced = advance_mock_scheduler(db, run.id, limit=3)

    assert advanced["processed"] == 3
    assert db.query(ProductionJob).filter_by(status=JOB_COMPLETED).count() == 3
    assert db.query(ProductionJob).filter_by(status=JOB_LEASED).count() == 1


def test_advance_mock_scheduler_does_not_complete_run_while_job_is_leased(db):
    result = create_mock_scale_run(
        db,
        prompt="A leased job must keep the run open.",
        title="Leased Open",
        target_duration_seconds=3 * 60,
    )
    run = result["run"]
    plan = result["plan"]
    production_episode = result["production_episode"]
    leased_job = db.query(ProductionJob).order_by(ProductionJob.created_at.asc()).first()
    leased_job.status = JOB_LEASED
    db.commit()

    advanced = advance_mock_scheduler(db, run.id, limit=10)
    db.refresh(run)
    db.refresh(plan)
    db.refresh(production_episode)

    assert advanced["processed"] == 2
    assert advanced["completed"] is False
    assert advanced["remaining"] == 0
    assert advanced["open_jobs"] == 1
    assert run.status != "completed"
    assert plan.status != "completed"
    assert production_episode.status != "completed"

    leased_job.status = JOB_QUEUED
    db.commit()

    final = advance_mock_scheduler(db, run.id, limit=10)
    db.refresh(run)
    db.refresh(plan)
    db.refresh(production_episode)

    assert final["processed"] == 1
    assert final["completed"] is True
    assert final["open_jobs"] == 0
    assert run.status == "completed"
    assert plan.status == "completed"
    assert production_episode.status == "completed"


def test_one_sentence_mock_scale_routes_to_provider_free_service(db, monkeypatch):
    from app.domains.video_production.one_sentence_video_service import create_one_sentence_video

    async def fail_if_real_provider_path(*args, **kwargs):
        raise AssertionError("mock_series_scale entered real provider path")

    monkeypatch.setattr(
        "app.domains.video_production.production_run_service.start_episode_production",
        fail_if_real_provider_path,
    )

    result = asyncio.run(create_one_sentence_video(
        db,
        prompt="A long mock series for load testing.",
        title="Mock Load",
        target_duration_seconds=480 * 60,
        run_type=MOCK_SERIES_SCALE,
    ))

    assert result["run"].run_type == MOCK_SERIES_SCALE
    assert result["run"].model_trace_json["provider_calls"] == 0
    assert db.query(ProductionJob).count() > 0
