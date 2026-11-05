"""Task scheduling service — backed by SQLAlchemy database."""
from datetime import datetime, timezone, timedelta
from app.config import bj_now
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update, or_, and_, null, String, select

from app.db_models import Task as DBTask, Device as DBDevice, Account
from app.models import TaskType, TaskStatus, Task as PydanticTask
from app.services.stats_service import stats_service

MAX_RETRIES = 3
TASK_TARGET_DEVICE_PARAM = "_target_device_id"


def _task_params_with_target(params, device_id=None) -> dict:
    """Copy business params and set only the server's explicit routing target."""
    copied = dict(params or {})
    copied.pop(TASK_TARGET_DEVICE_PARAM, None)
    if device_id:
        copied[TASK_TARGET_DEVICE_PARAM] = device_id
    return copied


def _db_task_to_pydantic(task: DBTask, params_override: Optional[dict] = None) -> PydanticTask:
    """Convert SQLAlchemy Task to Pydantic Task for API responses."""
    return PydanticTask(
        id=task.id,
        type=TaskType(task.type),
        account_id=task.account_id,
        device_id=task.device_id or "",
        # The routing reservation is server state, never a device parameter.
        params=_task_params_with_target(params_override if params_override is not None else task.params),
        status=TaskStatus(task.status),
        created_at=task.created_at,
        scheduled_at=task.scheduled_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        result=task.result,
        retry_count=task.retry_count,
        chain_instance_id=task.chain_instance_id,
        step_order=task.step_order,
        lease_id=task.lease_id,
    )


class TaskService:
    """Task scheduling service — DB-backed."""

    def _retry_attempt(self, db: Session, task: DBTask, result=None, now=None,
                       keep_cancel_delivery=False):
        """Spend one persisted retry budget, preserving a single dispatch path."""
        from app.db_models import ChannelItem
        from app.services.channel_service import channel_service
        now = now or bj_now()
        item = db.query(ChannelItem).filter(
            ChannelItem.task_id == task.id, ChannelItem.status == "assigned"
        ).first()
        task.retry_count = max(task.retry_count or 0, item.retry_count if item else 0) + 1
        task.result = result
        task.completed_at = now
        if item:
            item.retry_count = task.retry_count
            task.status = "failed" if task.retry_count >= MAX_RETRIES else "cancelled"
            if not keep_cancel_delivery:
                task.device_id = None
                task.lease_id = None
            item.assigned_device_id = None
            item.assigned_at = None
            item.task_id = None
            if task.retry_count >= MAX_RETRIES:
                channel_service.complete_item(db, item.id, "failed")
            else:
                item.status = "pending"
                item.completed_at = None
                channel_service._reactivate_channel(db, item.channel_id)
        elif task.retry_count >= MAX_RETRIES:
            task.status = "failed"
            task.device_id = None
            task.lease_id = None
        else:
            task.status = "pending"
            target_id = (task.params or {}).get(TASK_TARGET_DEVICE_PARAM)
            target = db.get(DBDevice, target_id) if isinstance(target_id, str) and target_id else None
            task.device_id = target.id if target else None
            if not target:
                task.params = _task_params_with_target(task.params)
            task.started_at = None
            task.completed_at = None
            task.lease_id = None
        db.flush()

    def recover_stale_tasks(self, db: Session, now=None):
        """Recover expired attempts for checker and both dispatch paths.

        Device heartbeats measure liveness, not task progress. A legitimate long
        task keeps its duration allowance even when its device loses contact.
        """
        from datetime import timedelta
        from app.services.task_deadline import task_expired
        now = now or bj_now()
        tasks = db.query(DBTask).filter(
            DBTask.status == "running", DBTask.started_at.isnot(None)
        ).all()
        recovered = []
        for task in tasks:
            if not task_expired(task, now):
                continue
            device = db.get(DBDevice, task.device_id) if task.device_id else None
            online = bool(device and device.last_seen_at and
                          device.last_seen_at >= now - timedelta(minutes=2))
            # Conditional UPDATE owns recovery; concurrent poll/checker workers
            # must not spend the same attempt twice.
            claimed = db.execute(update(DBTask).where(
                DBTask.id == task.id, DBTask.status == "running",
                DBTask.lease_id == task.lease_id,
            ).values(status="queued"))
            if not claimed.rowcount:
                continue
            self._retry_attempt(db, task, now=now, keep_cancel_delivery=online)
            if task.chain_instance_id and task.status == TaskStatus.FAILED.value:
                from app.services.chain_service import chain_service
                chain_service.advance_chain(db, task.id, task.status, task.result)
            recovered.append(task.id)
        if recovered:
            db.commit()
        return recovered

    def create_task(
        self,
        db: Session,
        task_type: TaskType,
        account_id: str,
        params: dict,
        scheduled_at: Optional[datetime] = None,
        device_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> PydanticTask:
        db_task = DBTask(
            type=task_type.value,
            account_id=account_id,
            device_id=device_id,
            user_id=user_id,
            params=_task_params_with_target(params, device_id),
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
        self.recover_stale_tasks(db)

        # --- Channel claim (priority path) ---
        from app.services.channel_service import channel_service
        channel_result = channel_service.claim_channel_item(db, device_id)
        if channel_result:
            task_pydantic, _channel_item_id = channel_result
            db.commit()
            return task_pydantic

        # 1. Look up the polling device's bound account and user
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        bound_account_id = device.bound_account_id if device else None
        device_user_id = device.user_id if device else None

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

        # 4. Find candidate tasks with routing, user scope, and scheduled_at applied
        now = bj_now()
        candidate_query = db.query(DBTask).join(Account, Account.id == DBTask.account_id).filter(
            Account.status == "active",
            DBTask.status == TaskStatus.PENDING.value,
            route_filter,
            or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
        )
        if device_user_id:
            candidate_query = candidate_query.filter(
                or_(DBTask.user_id == device_user_id, DBTask.user_id.is_(None))
            )
        candidates = candidate_query.order_by(DBTask.created_at.asc(), DBTask.id.asc()).all()

        if not candidates:
            return None

        # 5. Filter by daily quota and claim via atomic optimistic locking
        # Subquery: accounts that already have a RUNNING task
        busy_account_ids = db.query(DBTask.account_id).filter(
            or_(DBTask.status == TaskStatus.RUNNING.value,
                and_(DBTask.status == TaskStatus.CANCELLED.value, DBTask.device_id.isnot(None),
                     DBTask.completed_at >= bj_now() - timedelta(minutes=5))),
        ).distinct().scalar_subquery()

        for db_task in candidates:
            # Check task quota (reply_comment 不阻塞 follow/DM，handler 内部优雅降级)
            if not stats_service.check_quota(db, db_task.account_id, db_task.type, db_task.params):
                continue
            # Atomic claim: only succeeds if no other task for this account is RUNNING
            import uuid
            _lease_id = str(uuid.uuid4())
            # Capture the pending routing choice before device_id becomes the
            # executor. This also handles existing directed pending records;
            # automatically routed tasks must never reserve their first worker.
            dispatch_params = _task_params_with_target(db_task.params, db_task.device_id)
            result = db.execute(
                update(DBTask)
                .where(
                    DBTask.id == db_task.id,
                    DBTask.status == TaskStatus.PENDING.value,
                    DBTask.account_id.in_(select(Account.id).where(Account.status == "active")),
                    ~DBTask.account_id.in_(busy_account_ids),
                )
                .values(status=TaskStatus.RUNNING.value, device_id=device_id,
                        started_at=bj_now(), lease_id=_lease_id, params=dispatch_params)
            )
            db.commit()

            if result.rowcount == 0:
                continue

            db.refresh(db_task)
            params = stats_service.inject_task_quota_params(db, db_task.account_id, db_task.type, db_task.params)
            return _db_task_to_pydantic(db_task, params_override=params)

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

        # Pre-load channel association (used by both the ack path and retry logic)
        from app.db_models import ChannelItem
        from app.services.channel_service import channel_service
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()

        # Device ack'ing a server-initiated cancel — clean up device_id
        # and reset channel item so the keyword can be re-dispatched.
        # Must happen BEFORE the "already terminal" guard below.
        if db_task.status == TaskStatus.CANCELLED.value and status == TaskStatus.CANCELLED:
            db_task.device_id = None
            # Only reset assigned items — skipped/cancelled channel items
            # must stay terminal (channel-level cancel already handled them).
            if channel_item and channel_item.status == "assigned":
                channel_item.status = "pending"
                channel_item.assigned_device_id = None
                channel_item.assigned_at = None
                channel_item.task_id = None
                channel_service._reactivate_channel(db, channel_item.channel_id)
            import logging
            _logger = logging.getLogger("task_service")
            _logger.info("Device ack'ed cancellation for task %s — device_id cleared, channel item reset",
                         task_id)
            db_task.lease_id = None
            db.commit()
            db.refresh(db_task)
            return _db_task_to_pydantic(db_task), None

        # Task already in terminal state — ignore late reports
        if db_task.status in (TaskStatus.CANCELLED.value, TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
            import logging
            _logger = logging.getLogger("task_service")
            _logger.warning("Late report discarded: task %s already in terminal state %s (reported status=%s)",
                            task_id, db_task.status, status.value if hasattr(status, 'value') else status)
            return _db_task_to_pydantic(db_task), None

        if status == TaskStatus.COMPLETED:
            db_task.status = TaskStatus.COMPLETED.value
            db_task.result = result
            db_task.completed_at = bj_now()
            # 统计由设备端增量上报 (POST /api/device/stats/increment)
            # 每个子操作完成后实时上报，避免中途崩溃丢失数据 + 防止双重计数
        elif status == TaskStatus.CANCELLED:
            # Device self-cancelled (not server-initiated).
            # Only reset assigned ChannelItem — skipped/cancelled items stay terminal.
            db_task.status = TaskStatus.CANCELLED.value
            db_task.result = result
            db_task.completed_at = bj_now()
            db_task.device_id = None
            if channel_item and channel_item.status == "assigned":
                channel_item.status = "pending"
                channel_item.assigned_device_id = None
                channel_item.assigned_at = None
                channel_item.task_id = None
                channel_service._reactivate_channel(db, channel_item.channel_id)
        elif status == TaskStatus.FAILED:
            self._retry_attempt(db, db_task, result=result)

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

    def list_tasks(self, db: Session, status=None, task_type: str = None, search: str = None,
                   sort_by: str = "created_at", sort_order: str = "desc",
                   skip: int = 0, limit: int = 50, current_user_id: str = None) -> list[PydanticTask]:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == (status.value if hasattr(status, 'value') else status))
        if task_type:
            query = query.filter(DBTask.type == task_type)
        if search:
            pattern = f"%{search}%"
            query = query.filter(or_(
                DBTask.account_id.like(pattern),
                DBTask.device_id.like(pattern),
                DBTask.params.like(pattern),
            ))
        if current_user_id:
            query = query.filter(DBTask.user_id == current_user_id)
        col = getattr(DBTask, sort_by, DBTask.created_at)
        order = col.desc() if sort_order == "desc" else col.asc()
        db_tasks = query.order_by(order).offset(skip).limit(limit).all()
        return [_db_task_to_pydantic(t) for t in db_tasks]

    def count_tasks(self, db: Session, status=None, task_type: str = None, search: str = None, current_user_id: str = None) -> int:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == (status.value if hasattr(status, 'value') else status))
        if task_type:
            query = query.filter(DBTask.type == task_type)
        if search:
            pattern = f"%{search}%"
            query = query.filter(or_(
                DBTask.account_id.like(pattern),
                DBTask.device_id.like(pattern),
                DBTask.params.like(pattern),
            ))
        if current_user_id:
            query = query.filter(DBTask.user_id == current_user_id)
        return query.count()

    def cancel_task(self, db: Session, task_id: str):
        """Cancel a pending or running task.

        Keeps device_id so the cancellation can be delivered to the running
        device (via poll check_cancelled_running or WebSocket).  ChannelItem
        reset and device_id clear are deferred to report_result(CANCELLED),
        which the device calls after ack'ing the cancel.
        """
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status in (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value, TaskStatus.FAILED.value):
            raise ValueError(f"Cannot cancel task in status: {task.status}")
        task.status = TaskStatus.CANCELLED.value
        task.completed_at = bj_now()
        # Keep device_id — check_cancelled_running and WS both need it for
        # cancellation delivery.  Reset ChannelItem immediately so the channel
        # can re-dispatch without waiting for the device to ack.
        from app.db_models import ChannelItem
        from app.services.channel_service import channel_service as ch_svc
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()
        if channel_item and channel_item.status == "assigned":
            channel_item.status = "pending"
            channel_item.assigned_device_id = None
            channel_item.assigned_at = None
            channel_item.task_id = None
            db.flush()
            ch_svc._reactivate_channel(db, channel_item.channel_id)

        db.commit()
        db.refresh(task)
        return _db_task_to_pydantic(task)

    def delete_task(self, db: Session, task_id: str) -> bool:
        """Delete a task. Only non-running tasks can be deleted. Resets ChannelItem."""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status == TaskStatus.RUNNING.value:
            raise ValueError("Cannot delete a running task. Cancel it first.")

        # Reset associated ChannelItem so the keyword can be re-dispatched
        from app.db_models import ChannelItem, CollectedComment, CollectedUser, Conversation, GeneratedVideo, StatsEvent
        from app.services.channel_service import channel_service as ch_svc
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()
        if channel_item:
            channel_item.status = "pending"
            channel_item.assigned_device_id = None
            channel_item.assigned_at = None
            channel_item.task_id = None
            db.flush()
            ch_svc._reactivate_channel(db, channel_item.channel_id)

        # Null out FK references from child tables to avoid FK constraint error on delete
        for model in (CollectedComment, CollectedUser, Conversation, GeneratedVideo):
            db.query(model).filter(model.task_id == task_id).update(
                {"task_id": None}, synchronize_session=False
            )

        db.query(StatsEvent).filter(StatsEvent.task_id == task_id).delete(synchronize_session=False)
        db.delete(task)
        db.commit()
        return True

    def delete_tasks_batch(self, db: Session, task_ids: list[str]) -> int:
        """Delete multiple tasks in batch. Returns count of deleted tasks."""
        if not task_ids:
            return 0
        from app.db_models import ChannelItem
        # Only delete non-running tasks; running tasks are protected
        deletable = db.query(DBTask.id).filter(
            DBTask.id.in_(task_ids),
            DBTask.status != TaskStatus.RUNNING.value,
        ).all()
        deletable_ids = [t[0] for t in deletable]
        if not deletable_ids:
            return 0
        # Reset channel items only for tasks that will actually be deleted
        from app.services.channel_service import channel_service as ch_svc
        channel_items = db.query(ChannelItem).filter(ChannelItem.task_id.in_(deletable_ids)).all()
        ch_ids = set()
        for ci in channel_items:
            ci.status = "pending"
            ci.assigned_device_id = None
            ci.assigned_at = None
            ci.task_id = None
            ch_ids.add(ci.channel_id)
        if channel_items:
            db.flush()
            for cid in ch_ids:
                ch_svc._reactivate_channel(db, cid)
        # Null out FK references from child tables
        from app.db_models import CollectedComment, CollectedUser, Conversation, GeneratedVideo
        for model in (CollectedComment, CollectedUser, Conversation, GeneratedVideo):
            db.query(model).filter(model.task_id.in_(deletable_ids)).update(
                {"task_id": None}, synchronize_session=False
            )
        from app.db_models import StatsEvent
        db.query(StatsEvent).filter(StatsEvent.task_id.in_(deletable_ids)).delete(synchronize_session=False)
        result = db.query(DBTask).filter(
            DBTask.id.in_(deletable_ids),
        ).delete(synchronize_session=False)
        db.commit()
        return result

    def check_cancelled_running(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Check if device has a running task that was recently cancelled.

        Only returns tasks cancelled within the last 5 minutes — older ones are
        treated as acknowledged to prevent the same stale cancellation from
        being returned on every poll.
        """
        from datetime import timedelta
        cutoff = bj_now() - timedelta(minutes=5)
        task = (
            db.query(DBTask)
            .filter(
                DBTask.device_id == device_id,
                DBTask.status == TaskStatus.CANCELLED.value,
                DBTask.completed_at >= cutoff,
            )
            .order_by(DBTask.completed_at.desc())
            .first()
        )
        return _db_task_to_pydantic(task) if task else None


# Module-level singleton — services are stateless, DB sessions come from get_db
task_service = TaskService()
