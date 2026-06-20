"""Task scheduling service — backed by SQLAlchemy database."""
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update, or_, and_, null, String, select

from app.db_models import Task as DBTask, Device as DBDevice
from app.models import TaskType, TaskStatus, Task as PydanticTask
from app.domains.reporting.stats_service import stats_service

MAX_RETRIES = 3


def _db_task_to_pydantic(task: DBTask, params_override: Optional[dict] = None) -> PydanticTask:
    """Convert SQLAlchemy Task to Pydantic Task for API responses."""
    return PydanticTask(
        id=task.id,
        type=TaskType(task.type),
        account_id=task.account_id,
        device_id=task.device_id or "",
        params=params_override if params_override is not None else (task.params or {}),
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
        from app.domains.account_operations.channel_service import channel_service
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

        # 3. Recover stuck RUNNING tasks (device crashed while executing)
        # Only reclaim tasks from devices that haven't sent a heartbeat recently.
        from datetime import timedelta
        import os
        stale_minutes = int(os.getenv("TASK_STALE_MINUTES", "10"))
        stale_threshold = bj_now() - timedelta(minutes=stale_minutes)

        # Find devices that were recently seen (still online)
        online_device_ids = select(DBDevice.id).where(
            DBDevice.last_seen_at.isnot(None),
            DBDevice.last_seen_at >= stale_threshold,
        )

        stale_running = db.query(DBTask).filter(
            DBTask.status == TaskStatus.RUNNING.value,
            DBTask.started_at.isnot(None),
            DBTask.started_at < stale_threshold,
            ~DBTask.device_id.in_(online_device_ids),  # skip tasks on online devices
        ).all()
        # Query ChannelItems FIRST to distinguish channel-backed tasks from direct tasks.
        # Channel-backed tasks MUST be cancelled (not reset to PENDING) — otherwise
        # the old task enters the direct queue AND the ChannelItem generates a new
        # task, creating two execution paths for the same keyword/account.
        from app.db_models import ChannelItem
        from app.domains.account_operations.channel_service import channel_service as ch_svc
        stale_ids = [t.id for t in stale_running]
        stale_ch_items = db.query(ChannelItem).filter(ChannelItem.task_id.in_(stale_ids)).all()
        channel_backed_ids = {sci.task_id for sci in stale_ch_items}

        for stale in stale_running:
            stale.retry_count += 1
            if stale.retry_count >= MAX_RETRIES:
                stale.status = TaskStatus.FAILED.value
                stale.completed_at = bj_now()
                stale.device_id = None
                stale.lease_id = None
            elif stale.id in channel_backed_ids:
                # Channel-backed: cancel old task, let ChannelItem re-generate a fresh one.
                # Consistent with channel_service.claim_channel_item() stale recovery.
                stale.status = TaskStatus.CANCELLED.value
                stale.completed_at = bj_now()
                stale.device_id = None
                stale.lease_id = None
            else:
                # Direct task (no ChannelItem): reset to PENDING for re-dispatch.
                stale.status = TaskStatus.PENDING.value
                stale.device_id = None
                stale.started_at = None
                stale.lease_id = None

        if stale_running:
            db.flush()
            # Reset channel items based on the task's new status:
            # - FAILED (max retries) → channel item → "failed" (terminal)
            # - CANCELLED (retry)    → channel item → "pending" (re-dispatch)
            _task_status = {t.id: t.status for t in stale_running}
            stale_ch_ids = set()
            for sci in stale_ch_items:
                new_status = _task_status.get(sci.task_id)
                if new_status == TaskStatus.FAILED.value:
                    sci.status = "failed"
                    sci.assigned_device_id = None
                    sci.assigned_at = None
                    sci.task_id = None
                elif new_status == TaskStatus.CANCELLED.value:
                    sci.status = "pending"
                    sci.assigned_device_id = None
                    sci.assigned_at = None
                    sci.task_id = None
                    stale_ch_ids.add(sci.channel_id)
            if stale_ch_items:
                db.flush()
                for cid in stale_ch_ids:
                    ch_svc._reactivate_channel(db, cid)

        # 4. Find candidate tasks with routing, user scope, and scheduled_at applied
        now = bj_now()
        candidate_query = db.query(DBTask).filter(
            DBTask.status == TaskStatus.PENDING.value,
            route_filter,
            or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
        )
        if device_user_id:
            candidate_query = candidate_query.filter(
                or_(DBTask.user_id == device_user_id, DBTask.user_id.is_(None))
            )
        candidates = candidate_query.order_by(DBTask.created_at.asc()).limit(10).all()

        if not candidates:
            return None

        # 5. Filter by daily quota and claim via atomic optimistic locking
        # Subquery: accounts that already have a RUNNING task
        busy_account_ids = db.query(DBTask.account_id).filter(
            DBTask.status == TaskStatus.RUNNING.value,
        ).distinct().scalar_subquery()

        for db_task in candidates:
            # Check task quota (reply_comment 不阻塞 follow/DM，handler 内部优雅降级)
            if not stats_service.check_quota(db, db_task.account_id, db_task.type, db_task.params):
                continue
            # Atomic claim: only succeeds if no other task for this account is RUNNING
            import uuid
            _lease_id = str(uuid.uuid4())
            result = db.execute(
                update(DBTask)
                .where(
                    DBTask.id == db_task.id,
                    DBTask.status == TaskStatus.PENDING.value,
                    ~DBTask.account_id.in_(busy_account_ids),
                )
                .values(status=TaskStatus.RUNNING.value, device_id=device_id, started_at=bj_now(), lease_id=_lease_id)
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
        from app.domains.account_operations.channel_service import channel_service
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
            db_task.retry_count += 1
            if db_task.retry_count >= MAX_RETRIES:
                db_task.status = TaskStatus.FAILED.value
                db_task.result = result
                db_task.completed_at = bj_now()
            else:
                if channel_item:
                    # Channel-driven retry: increment item-level retry counter,
                    # reset to pending so claim_channel_item re-dispatches with
                    # proper routing/cooldown/quota. Old task cancelled to avoid
                    # orphan direct-queue pickup (single recovery path, no fork).
                    channel_item.retry_count += 1
                    if channel_item.retry_count >= MAX_RETRIES:
                        channel_item.status = "failed"
                        channel_item.completed_at = bj_now()
                        db_task.status = TaskStatus.FAILED.value
                        db_task.completed_at = bj_now()
                    else:
                        channel_item.status = "pending"
                        channel_item.assigned_device_id = None
                        channel_item.assigned_at = None
                        channel_item.task_id = None
                        db.flush()
                        channel_service._reactivate_channel(db, channel_item.channel_id)
                        db_task.status = TaskStatus.CANCELLED.value
                        db_task.completed_at = bj_now()
                else:
                    # Non-channel task: standard direct retry
                    db_task.status = TaskStatus.PENDING.value
                    db_task.device_id = None
                    db_task.started_at = None
                    db_task.lease_id = None

        # Advance chain if this task is part of one
        if db_task.chain_instance_id and db_task.status in ("completed", "failed"):
            from app.domains.account_operations.chain_service import chain_service
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
        from app.domains.account_operations.channel_service import channel_service as ch_svc
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
        from app.db.models.video_library import GeneratedVideo
        from app.db_models import ChannelItem, CollectedComment, CollectedUser, Conversation
        from app.domains.account_operations.channel_service import channel_service as ch_svc
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
        from app.domains.account_operations.channel_service import channel_service as ch_svc
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
        from app.db.models.video_library import GeneratedVideo
        from app.db_models import CollectedComment, CollectedUser, Conversation
        for model in (CollectedComment, CollectedUser, Conversation, GeneratedVideo):
            db.query(model).filter(model.task_id.in_(deletable_ids)).update(
                {"task_id": None}, synchronize_session=False
            )
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
