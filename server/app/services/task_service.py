"""Task scheduling service — backed by SQLAlchemy database."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update, or_, and_, null

from app.db_models import Task as DBTask, Device as DBDevice
from app.models import TaskType, TaskStatus, Task as PydanticTask
from app.services.stats_service import stats_service

MAX_RETRIES = 3


def _db_task_to_pydantic(task: DBTask) -> PydanticTask:
    """Convert SQLAlchemy Task to Pydantic Task for API responses."""
    return PydanticTask(
        id=task.id,
        type=TaskType(task.type),
        account_id=task.account_id,
        device_id=task.device_id or "",
        params=task.params or {},
        status=TaskStatus(task.status),
        scheduled_at=task.scheduled_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        result=task.result,
        retry_count=task.retry_count,
        chain_instance_id=task.chain_instance_id,
        step_order=task.step_order,
    )


class TaskService:
    """Task scheduling service — DB-backed."""

    def create_task(
        self,
        db: Session,
        task_type: TaskType,
        account_id: str,
        params: dict,
        scheduled_at: Optional[datetime] = None,
        device_id: Optional[str] = None,
    ) -> PydanticTask:
        db_task = DBTask(
            type=task_type.value,
            account_id=account_id,
            device_id=device_id,
            params=params,
            status=TaskStatus.PENDING.value,
            scheduled_at=scheduled_at,
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def get_task(self, db: Session, task_id: str) -> Optional[PydanticTask]:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            return None
        return _db_task_to_pydantic(db_task)

    def get_pending_task(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Claim a pending task using optimistic locking, respecting daily quotas and device routing.

        Routing rules:
        - Directed task (task.device_id set) -> only that device can claim it
        - Bound device (device.bound_account_id set) -> only tasks for that account
        - Unbound device -> only tasks with no device_id AND whose account is not bound to any device
        """
        # --- Channel claim (priority path) ---
        from app.services.channel_service import channel_service
        channel_result = channel_service.claim_channel_item(db, device_id)
        if channel_result:
            task_pydantic, _channel_item_id = channel_result
            db.commit()
            return task_pydantic

        # 1. Look up the polling device's bound account
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        bound_account_id = device.bound_account_id if device else None

        # 2. Build routing filter
        if bound_account_id:
            # Bound device: can claim directed tasks OR tasks for its bound account
            route_filter = or_(
                DBTask.device_id == device_id,
                and_(DBTask.device_id.is_(None), DBTask.account_id == bound_account_id),
            )
        else:
            # Unbound device: can claim directed tasks OR orphan tasks
            # (tasks with no device_id whose account is not bound to any device)
            bound_account_ids = db.query(DBDevice.bound_account_id).filter(
                DBDevice.bound_account_id.isnot(None)
            ).scalar_subquery()
            route_filter = or_(
                DBTask.device_id == device_id,
                and_(DBTask.device_id.is_(None), ~DBTask.account_id.in_(bound_account_ids)),
            )

        # 3. Recover stuck RUNNING tasks (device crashed while executing)
        from datetime import timedelta
        stale_threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3)
        stale_running = db.query(DBTask).filter(
            DBTask.status == TaskStatus.RUNNING.value,
            DBTask.started_at.isnot(None),
            DBTask.started_at < stale_threshold,
        ).all()
        for stale in stale_running:
            stale.status = TaskStatus.PENDING.value
            stale.device_id = None
            stale.started_at = None
        if stale_running:
            db.flush()

        # 4. Find candidate tasks with routing and scheduled_at applied
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        candidates = db.query(DBTask).filter(
            DBTask.status == TaskStatus.PENDING.value,
            route_filter,
            or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
        ).order_by(DBTask.created_at.asc()).limit(10).all()

        if not candidates:
            return None

        # 5. Filter by daily quota and claim via atomic optimistic locking
        # Subquery: accounts that already have a RUNNING task
        busy_account_ids = db.query(DBTask.account_id).filter(
            DBTask.status == TaskStatus.RUNNING.value,
        ).distinct().scalar_subquery()

        for db_task in candidates:
            if stats_service.check_quota(db, db_task.account_id, db_task.type):
                # Atomic claim: only succeeds if no other task for this account is RUNNING
                result = db.execute(
                    update(DBTask)
                    .where(
                        DBTask.id == db_task.id,
                        DBTask.status == TaskStatus.PENDING.value,
                        ~DBTask.account_id.in_(busy_account_ids),
                    )
                    .values(status=TaskStatus.RUNNING.value, device_id=device_id, started_at=datetime.now(timezone.utc))
                )
                db.commit()

                if result.rowcount == 0:
                    continue

                db.refresh(db_task)
                return _db_task_to_pydantic(db_task)

        return None

    def report_result(
        self,
        db: Session,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        ui_snapshot: Optional[dict] = None,
    ) -> tuple[PydanticTask, Optional[dict]]:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            raise ValueError(f"Task {task_id} not found")

        # Task already in terminal state — ignore late reports
        if db_task.status in (TaskStatus.CANCELLED.value, TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
            return _db_task_to_pydantic(db_task), None

        # Check channel association early (affects retry logic)
        from app.db_models import ChannelItem
        from app.services.channel_service import channel_service
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()

        if status == TaskStatus.COMPLETED:
            db_task.status = TaskStatus.COMPLETED.value
            db_task.result = result
            db_task.completed_at = datetime.now(timezone.utc)
            # Record operation count
            success_count = (result or {}).get("success_count", 1)
            stats_service.increment(db, db_task.account_id, db_task.type, count=success_count)
        elif status == TaskStatus.FAILED:
            db_task.retry_count += 1
            # Channel tasks: skip retry, fail immediately (channel redistributes naturally)
            if channel_item or db_task.retry_count >= MAX_RETRIES:
                db_task.status = TaskStatus.FAILED.value
                db_task.result = result
                db_task.completed_at = datetime.now(timezone.utc)
            else:
                db_task.status = TaskStatus.PENDING.value  # re-queue for retry
                db_task.device_id = None
                db_task.started_at = None

        # Advance chain if this task is part of one
        if db_task.chain_instance_id and db_task.status in ("completed", "failed"):
            from app.services.chain_service import chain_service
            chain_service.advance_chain(db, task_id, db_task.status, result)

        # Update channel item status
        channel_broadcast_info = None
        if channel_item and db_task.status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
            channel_broadcast_info = channel_service.complete_item(db, channel_item.id,
                "completed" if db_task.status == TaskStatus.COMPLETED.value else "failed")

        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task), channel_broadcast_info

    def list_tasks(self, db: Session, status: Optional[TaskStatus] = None, skip: int = 0, limit: int = 50) -> list[PydanticTask]:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == status.value)
        db_tasks = query.order_by(DBTask.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_task_to_pydantic(t) for t in db_tasks]

    def count_tasks(self, db: Session, status: Optional[TaskStatus] = None) -> int:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == status.value)
        return query.count()

    def cancel_task(self, db: Session, task_id: str):
        """Cancel a pending or running task. Resets associated channel item if any."""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status in (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value):
            raise ValueError(f"Cannot cancel task in status: {task.status}")
        task.status = TaskStatus.CANCELLED.value
        task.completed_at = datetime.now(timezone.utc)

        # Reset associated channel item so it can be re-dispatched
        from app.db_models import ChannelItem
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()
        if channel_item:
            channel_item.status = "pending"
            channel_item.assigned_device_id = None
            channel_item.assigned_at = None
            channel_item.task_id = None

        db.commit()
        db.refresh(task)
        return _db_task_to_pydantic(task)

    def check_cancelled_running(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Check if device has a running task that was cancelled."""
        task = (
            db.query(DBTask)
            .filter(DBTask.device_id == device_id, DBTask.status == TaskStatus.CANCELLED.value)
            .order_by(DBTask.created_at.desc())
            .first()
        )
        return _db_task_to_pydantic(task) if task else None


# Module-level singleton — services are stateless, DB sessions come from get_db
task_service = TaskService()
