"""Device status lifecycle background workers."""
import asyncio
import logging
import os
from datetime import timedelta

from app.config import bj_now
from app.database import SessionLocal


async def offline_checker():
    """Mark stale devices offline and recover stuck tasks.

    Heartbeats are collected in memory by the websocket manager and flushed to
    the database each cycle. Failed heartbeat flushes are requeued so the next
    cycle can retry without losing liveness information.
    """
    from app.db_models import Device
    from app.ws_manager import pair_ws_manager

    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            now = bj_now()

            # 1. Flush in-memory heartbeats to DB
            mem_heartbeats = pair_ws_manager.drain_heartbeats()
            if mem_heartbeats:
                try:
                    for device_id, seen_at in mem_heartbeats.items():
                        dev = db.query(Device).filter(Device.id == device_id).first()
                        if dev:
                            dev.last_seen_at = seen_at
                            dev.status = "online"
                    db.commit()
                except Exception:
                    # Re-merge on failure so next cycle retries.
                    _hb_log = logging.getLogger("app.heartbeat")
                    _hb_log.warning("heartbeat flush failed, re-queuing %d", len(mem_heartbeats), exc_info=True)
                    for device_id, seen_at in mem_heartbeats.items():
                        if device_id not in pair_ws_manager._device_last_seen:
                            pair_ws_manager._device_last_seen[device_id] = seen_at

            # 2. Check liveness: both in-memory (already drained, checked above)
            #    and DB last_seen_at. Stale if >2 min without heartbeat.
            online_devices = db.query(Device).filter(Device.status == "online").all()
            cutoff_dt = now - timedelta(seconds=120)
            stale_ids = [
                d.id for d in online_devices
                if d.last_seen_at is None or d.last_seen_at < cutoff_dt
            ]

            if stale_ids:
                db.query(Device).filter(Device.id.in_(stale_ids)).update(
                    {"status": "offline"}, synchronize_session=False
                )
                db.commit()

                for device_id in stale_ids:
                    await pair_ws_manager.broadcast_to_admins({
                        "event": "device_status_changed",
                        "device_id": device_id,
                        "status": "offline",
                    })

            # 3. Stuck task detection: tasks running >10 min on ONLINE devices -> reset
            #    Device is online (heartbeat active) but task thread stuck/dead.
            #    Offline-device tasks are handled by get_pending_task() stale recovery.
            stuck_minutes = int(os.getenv("TASK_STALE_MINUTES", "10"))
            stuck_cutoff = now - timedelta(seconds=stuck_minutes * 60)
            from app.db_models import Task as DBTask, ChannelItem as DBChannelItem
            online_ids = [d.id for d in online_devices]  # reuse from liveness check above
            stuck_tasks = db.query(DBTask).filter(
                DBTask.status == "running",
                DBTask.started_at.isnot(None),
                DBTask.started_at < stuck_cutoff,
                DBTask.device_id.in_(online_ids),  # only online devices; offline handled by get_pending_task
            ).all()
            if stuck_tasks:
                from app.services.task_service import MAX_RETRIES
                for task in stuck_tasks:
                    task.retry_count += 1
                    if task.retry_count >= MAX_RETRIES:
                        task.status = "failed"
                        task.completed_at = now
                        # Task is terminal; channel item must also be terminal.
                        # Only reset "assigned" items (not completed/failed).
                        db.query(DBChannelItem).filter(
                            DBChannelItem.task_id == task.id,
                            DBChannelItem.status == "assigned",
                        ).update(
                            {"status": "failed", "assigned_device_id": None, "assigned_at": None, "task_id": None},
                            synchronize_session=False,
                        )
                    else:
                        # Cancel task; channel item reset below creates fresh task on re-claim.
                        # Must NOT set to PENDING (would create duplicate direct-queue retry).
                        # Keep device_id so the online device can receive the cancel via poll.
                        # _handleCancelledTask on the device will ack and clear device_id.
                        task.status = "cancelled"
                        task.completed_at = now
                        # Only reset assigned items for re-dispatch; completed/failed are terminal.
                        db.query(DBChannelItem).filter(
                            DBChannelItem.task_id == task.id,
                            DBChannelItem.status == "assigned",
                        ).update(
                            {"status": "pending", "assigned_device_id": None, "assigned_at": None, "task_id": None},
                            synchronize_session=False,
                        )
                db.commit()
        except Exception:
            logging.getLogger("app.offline_checker").warning("checker cycle failed", exc_info=True)
        finally:
            db.close()
