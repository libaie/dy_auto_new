"""Short database write fences for production worker claims."""
from contextlib import contextmanager

from sqlalchemy import event, update
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProductionJob
from app.services.production_errors import ProductionRepairableError


class ProductionLeaseLostError(ValueError):
    pass


@contextmanager
def worker_write_scope(db: Session, job_id: str, worker_lease: tuple | None):
    """Fence a complete provider write phase, including helper-internal commits.

    A conditional no-op update locks the job row until the outer transaction ends.
    Helper sessions join through savepoints, so their commit/rollback cannot release
    that fence. This scope is never held across an external await. Calls outside a
    worker retain the existing standalone helper transaction behavior.
    """
    if worker_lease is None:
        yield db
        return

    # End any read snapshot retained across the provider await.
    db.rollback()
    now = bj_now()
    locked = db.query(ProductionJob).filter(
        ProductionJob.id == job_id,
        ProductionJob.status.in_(("leased", "running")),
        ProductionJob.lease_id == worker_lease[0],
        ProductionJob.leased_until == worker_lease[1],
        ProductionJob.leased_until > now,
    ).update({"updated_at": ProductionJob.updated_at}, synchronize_session=False)
    if locked != 1:
        db.rollback()
        raise ProductionLeaseLostError("Production job lease no longer belongs to this worker")

    write_db = Session(bind=db.connection(), join_transaction_mode="create_savepoint")
    try:
        yield write_db
        write_db.commit()
    except ProductionRepairableError:
        # Preserve completed repair writes, but discard any unfinished savepoint.
        write_db.rollback()
        write_db.close()
        db.commit()
        raise
    except BaseException:
        write_db.close()
        db.rollback()
        raise
    else:
        write_db.close()
        db.commit()



def ensure_worker_lease_for_write(db: Session) -> None:
    claim = db.info.get("production_worker_claim")
    if claim is None:
        return
    transaction = db.get_transaction()
    if transaction is not None and db.info.get("production_fenced_transaction") is transaction:
        return
    job_id, lease = claim
    connection = db.connection()
    locked = connection.execute(update(ProductionJob).where(
        ProductionJob.id == job_id,
        ProductionJob.status.in_(("leased", "running")),
        ProductionJob.lease_id == lease[0],
        ProductionJob.leased_until == lease[1],
        ProductionJob.leased_until > bj_now(),
    ).values(updated_at=ProductionJob.updated_at)).rowcount
    if locked != 1:
        raise ProductionLeaseLostError("Production job lease no longer belongs to this worker")
    db.info["production_fenced_transaction"] = db.get_transaction()


@contextmanager
def guarded_worker_session(db: Session, job_id: str, lease: tuple):
    """Acquire the fence on the first write of each transaction, after external I/O.

    Used by existing asset/audit helpers that perform reads and network calls before
    writing. Every helper commit releases the fence; the next write reacquires it.
    Autoflush is disabled so a read before network I/O cannot flush pending changes.
    """
    db.rollback()
    guarded = Session(bind=db.get_bind(), autoflush=False)
    guarded.info["production_worker_claim"] = (job_id, lease)
    def before_flush(session, flush_context, instances):
        ensure_worker_lease_for_write(session)
    def before_execute(state):
        if state.is_update or state.is_delete or state.is_insert:
            ensure_worker_lease_for_write(state.session)
    event.listen(guarded, "before_flush", before_flush)
    event.listen(guarded, "do_orm_execute", before_execute)
    try:
        yield guarded
        guarded.commit()
    finally:
        guarded.close()
        db.expire_all()
