from datetime import timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query

from app.config import bj_now
from app.db_models import ProductionJob, ProductionPlan, Series
from app.services.production_queue_service import (
    claim_next_job,
    enqueue_job,
    fail_job,
    mark_job_completed,
    pause_plan_jobs,
    release_expired_leases,
    retry_job_without_attempt,
    resume_plan_jobs,
)
from app.services.production_status import (
    JOB_BLOCKED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
)


def _plan(db):
    series = Series(title="Queue Show", logline="Queue test", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", target_total_duration_seconds=60)
    db.add(plan)
    db.commit()
    return plan


def test_enqueue_job_is_idempotent(db):
    plan = _plan(db)
    first = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    second = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    assert first.id == second.id
    assert db.query(ProductionJob).count() == 1


def test_enqueue_job_returns_existing_after_integrity_error(db, monkeypatch):
    plan = _plan(db)
    existing = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    original_query = db.query
    original_commit = db.commit
    calls = {"query": 0, "commit": 0}

    class EmptyQuery:
        def filter(self, *args):
            return self

        def first(self):
            return None

    def query_once_without_existing(*entities, **kwargs):
        if entities == (ProductionJob,) and calls["query"] == 0:
            calls["query"] += 1
            return EmptyQuery()
        return original_query(*entities, **kwargs)

    def commit_once_with_integrity_error():
        calls["commit"] += 1
        if calls["commit"] == 1:
            raise IntegrityError("duplicate", None, None)
        return original_commit()

    monkeypatch.setattr(db, "query", query_once_without_existing)
    monkeypatch.setattr(db, "commit", commit_once_with_integrity_error)

    job = enqueue_job(db, plan.id, "segment", "seg-2", "image_generation", "seg-1:image:v1")

    assert job.id == existing.id
    assert db.query(ProductionJob).count() == 1


def test_claim_next_job_sets_lease(db):
    plan = _plan(db)
    enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    job = claim_next_job(db, lease_id="worker-a", lease_seconds=30)

    assert job is not None
    assert job.status == "leased"
    assert job.lease_id == "worker-a"
    assert job.leased_until is not None


def test_mark_queued_job_completed_is_rejected_by_default(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    with pytest.raises(ValueError, match="cannot be completed"):
        mark_job_completed(db, job.id, provider_task_id="provider-1")

    db.refresh(job)
    assert job.status == JOB_QUEUED
    assert job.completed_at is None


def test_mark_leased_job_completed_clears_lease(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = JOB_LEASED
    job.lease_id = "worker-a"
    job.leased_until = bj_now() + timedelta(seconds=30)
    job.retry_after = bj_now() + timedelta(seconds=60)
    db.commit()

    completed = mark_job_completed(db, job.id, expected_lease_id="worker-a")

    assert completed.status == JOB_COMPLETED
    assert completed.lease_id is None
    assert completed.leased_until is None
    assert completed.retry_after is None


def test_mark_leased_job_completed_rejects_wrong_lease(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    claimed = claim_next_job(db, lease_id="worker-a", plan_id=plan.id)

    assert claimed.id == job.id
    with pytest.raises(ValueError, match="cannot be completed"):
        mark_job_completed(db, job.id, expected_lease_id="worker-b")

    db.refresh(job)
    assert job.status == JOB_LEASED
    assert job.lease_id == "worker-a"
    assert job.completed_at is None


def test_mark_completed_job_completed_is_idempotent(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    claimed = claim_next_job(db, lease_id="worker-a", plan_id=plan.id)
    assert claimed.id == job.id
    first = mark_job_completed(db, job.id, provider_task_id="provider-1", expected_lease_id="worker-a")

    second = mark_job_completed(db, job.id, provider_task_id="provider-2")

    assert second.id == first.id
    assert second.status == JOB_COMPLETED
    assert second.provider_task_id == "provider-1"
    assert second.completed_at == first.completed_at


@pytest.mark.parametrize("status", [JOB_BLOCKED, JOB_FAILED])
def test_mark_blocked_or_failed_job_completed_is_rejected(db, status):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = status
    db.commit()

    with pytest.raises(ValueError, match="cannot be completed"):
        mark_job_completed(db, job.id)

    db.refresh(job)
    assert job.status == status
    assert job.completed_at is None


def test_allowed_statuses_cannot_expand_completion_boundary_to_failed(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = JOB_FAILED
    db.commit()

    with pytest.raises(ValueError, match="cannot be completed"):
        mark_job_completed(db, job.id, allowed_statuses=(JOB_FAILED,))

    db.refresh(job)
    assert job.status == JOB_FAILED
    assert job.completed_at is None


@pytest.mark.parametrize("status", [JOB_BLOCKED, JOB_FAILED, JOB_RETRY_WAIT])
def test_rejected_completion_rolls_back_unrelated_dirty_state(db, status):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = status
    db.commit()

    series = db.query(Series).filter(Series.id == plan.series_id).one()
    series.title = "Should Not Commit"

    with pytest.raises(ValueError, match="cannot be completed"):
        mark_job_completed(db, job.id)

    assert not db.dirty
    assert not db.new
    saved_title = db.query(Series.title).filter(Series.id == plan.series_id).scalar()
    assert saved_title == "Queue Show"


def test_mark_job_completed_rejects_unexpected_current_status(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = JOB_RETRY_WAIT
    job.retry_after = bj_now() + timedelta(seconds=60)
    db.commit()

    with pytest.raises(ValueError, match="cannot be completed"):
        mark_job_completed(db, job.id)

    db.refresh(job)
    assert job.status == JOB_RETRY_WAIT
    assert job.completed_at is None


def test_claim_next_job_continues_after_update_race(db, monkeypatch):
    plan = _plan(db)
    stolen = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1", priority=1)
    fallback = enqueue_job(db, plan.id, "segment", "seg-2", "image_generation", "seg-2:image:v1", priority=2)
    original_update = Query.update
    calls = {"count": 0}

    def race_once(query, values, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            db.execute(
                update(ProductionJob)
                .where(ProductionJob.id == stolen.id)
                .values(status="leased", lease_id="worker-b", leased_until=bj_now() + timedelta(seconds=30))
            )
            db.flush()
            return 0
        return original_update(query, values, *args, **kwargs)

    monkeypatch.setattr(Query, "update", race_once)

    job = claim_next_job(db, lease_id="worker-a", lease_seconds=30)

    assert job is not None
    assert job.id == fallback.id
    assert job.status == "leased"
    assert job.lease_id == "worker-a"


def test_release_expired_leases_returns_job_to_queue(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = "leased"
    job.lease_id = "worker-a"
    job.leased_until = bj_now() - timedelta(seconds=5)
    db.commit()

    released = release_expired_leases(db)

    assert released == 1
    db.refresh(job)
    assert job.status == "queued"
    assert job.lease_id is None


def test_fail_job_retryable_moves_to_retry_wait(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    fail_job(db, job.id, "RATE_LIMIT", "provider rate limited", retryable=True, retry_after_seconds=60)

    db.refresh(job)
    assert job.status == "retry_wait"
    assert job.retry_after is not None
    assert job.attempt_count == 1


def test_fail_job_non_retryable_moves_to_failed(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    fail_job(db, job.id, "BAD_REQUEST", "invalid prompt", retryable=False)

    db.refresh(job)
    assert job.status == "failed"
    assert job.retry_after is None
    assert job.attempt_count == 1


def test_fail_job_retryable_moves_to_failed_at_max_attempts(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1", max_attempts=1)

    fail_job(db, job.id, "RATE_LIMIT", "provider rate limited", retryable=True)

    db.refresh(job)
    assert job.status == "failed"
    assert job.retry_after is None
    assert job.attempt_count == 1


def test_fail_job_clears_lease(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = "leased"
    job.lease_id = "worker-a"
    job.leased_until = bj_now() + timedelta(seconds=30)
    db.commit()

    fail_job(db, job.id, "RATE_LIMIT", "provider rate limited", retryable=True)

    db.refresh(job)
    assert job.lease_id is None
    assert job.leased_until is None


def test_retry_job_without_attempt_returns_leased_job_to_retry_wait(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    claimed = claim_next_job(db, lease_id="worker-a", lease_seconds=30, plan_id=plan.id)
    assert claimed.id == job.id

    retried = retry_job_without_attempt(
        db,
        job.id,
        "PROVIDER_STAGE_TASK_SYNC_REQUIRED",
        "Provider task is still running.",
        retry_after_seconds=60,
        expected_lease_id="worker-a",
    )

    assert retried.status == JOB_RETRY_WAIT
    assert retried.attempt_count == 0
    assert retried.retry_after is not None
    assert retried.error_code == "PROVIDER_STAGE_TASK_SYNC_REQUIRED"
    assert retried.lease_id is None
    assert retried.leased_until is None


def test_pause_plan_jobs_blocks_queued_work(db):
    plan = _plan(db)
    enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    paused = pause_plan_jobs(db, plan.id, reason="budget_exceeded")

    assert paused == 1
    assert db.query(ProductionJob).one().status == "blocked"


def test_resume_plan_jobs_restores_job_that_can_complete(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    pause_plan_jobs(db, plan.id, reason="budget_exceeded")

    resumed = resume_plan_jobs(db, plan.id)
    claimed = claim_next_job(db, lease_id="worker-a", plan_id=plan.id)
    completed = mark_job_completed(db, job.id, expected_lease_id="worker-a")

    assert resumed == 1
    assert claimed.id == job.id
    assert completed.status == JOB_COMPLETED


def test_pause_plan_jobs_only_blocks_queued_and_retry_wait(db):
    plan = _plan(db)
    queued = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    retry_wait = enqueue_job(db, plan.id, "segment", "seg-2", "image_generation", "seg-2:image:v1")
    leased = enqueue_job(db, plan.id, "segment", "seg-3", "image_generation", "seg-3:image:v1")
    running = enqueue_job(db, plan.id, "segment", "seg-4", "image_generation", "seg-4:image:v1")
    completed = enqueue_job(db, plan.id, "segment", "seg-5", "image_generation", "seg-5:image:v1")
    retry_wait.status = "retry_wait"
    leased.status = "leased"
    running.status = "running"
    completed.status = "completed"
    db.commit()

    paused = pause_plan_jobs(db, plan.id, reason="budget_exceeded")

    assert paused == 2
    statuses = {job.target_id: job.status for job in db.query(ProductionJob).all()}
    assert statuses[queued.target_id] == "blocked"
    assert statuses[retry_wait.target_id] == "blocked"
    assert statuses[leased.target_id] == "leased"
    assert statuses[running.target_id] == "running"
    assert statuses[completed.target_id] == "completed"


def test_retry_wait_job_can_only_be_claimed_after_retry_after(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    fail_job(db, job.id, "RATE_LIMIT", "provider rate limited", retryable=True, retry_after_seconds=60)

    assert claim_next_job(db, lease_id="worker-a") is None
    job.retry_after = bj_now() - timedelta(seconds=1)
    db.commit()

    claimed = claim_next_job(db, lease_id="worker-a")
    assert claimed is not None
    assert claimed.id == job.id
    assert mark_job_completed(db, claimed.id).status == JOB_COMPLETED


def test_enqueue_job_rejects_blocked_plan(db):
    plan = _plan(db)
    plan.status = "blocked"
    db.commit()

    with pytest.raises(ValueError, match="not accepting jobs"):
        enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")


def test_claim_next_job_skips_blocked_plan(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    plan.status = "blocked"
    db.commit()

    claimed = claim_next_job(db, lease_id="worker-a")

    db.refresh(job)
    assert claimed is None
    assert job.status == "queued"
