"""设备运营业务域模块。

设备运营业务域，负责设备接入、脚本下发、轮询上报和状态生命周期。本文件负责 status_ws 相关业务规则、状态转换和外部系统边界。
"""

import asyncio

from fastapi import APIRouter, WebSocket
from sqlalchemy.orm import Session

from app.config import bj_now
from app.database import get_db
from app.ws_manager import pair_ws_manager

router = APIRouter()
async def _notify_pending_tasks(db: Session, device_id: str):
    """业务函数：处理 _notify_pending_tasks 对应的业务流程、校验或数据转换。"""
    """Check if there are pending tasks for this device and notify it via WS."""
    import logging
    logger = logging.getLogger(__name__)

    from app.db.models.device_operations import Device
    from app.db.models import Task as DBTask
    from app.models import TaskStatus
    from datetime import datetime, timezone
    from sqlalchemy import or_, and_

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        logger.info(f"[notify] 设备 {device_id} 不存在，跳过")
        return

    now = bj_now()
    device_user_id = device.user_id

    # Build routing filter (same logic as task_service.get_pending_task)
    if device.bound_account_id:
        route_filter = or_(
            DBTask.device_id == device_id,
            and_(DBTask.device_id.is_(None), DBTask.account_id == device.bound_account_id),
        )
        logger.info(f"[notify] 设备 {device_id} 绑定账号 {device.bound_account_id}，查询匹配任务...")
    else:
        bound_account_ids = db.query(Device.bound_account_id).filter(
            Device.bound_account_id.isnot(None)
        ).scalar_subquery()
        route_filter = or_(
            DBTask.device_id == device_id,
            and_(DBTask.device_id.is_(None), ~DBTask.account_id.in_(bound_account_ids)),
        )
        logger.info(f"[notify] 设备 {device_id} 未绑定账号，查询孤儿任务...")

    pending_task_query = db.query(DBTask).filter(
        DBTask.status == TaskStatus.PENDING.value,
        route_filter,
        or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
    )
    if device_user_id:
        pending_task_query = pending_task_query.filter(
            or_(DBTask.user_id == device_user_id, DBTask.user_id.is_(None))
        )
    pending_tasks = pending_task_query.all()

    # Also check pending channel items for this device
    from app.db.models import ChannelItem, Channel
    channel_subquery = db.query(Channel.id).filter(
        Channel.status == "active", Channel.deleted_at.is_(None)
    )
    if device_user_id:
        channel_subquery = channel_subquery.filter(
            or_(Channel.user_id == device_user_id, Channel.user_id.is_(None))
        )
    channel_item_query = db.query(ChannelItem).filter(
        ChannelItem.status == "pending",
        ChannelItem.channel_id.in_(channel_subquery),
    )
    if device.bound_account_id:
        channel_item_query = channel_item_query.filter(ChannelItem.account_id == device.bound_account_id)
    pending_channel_count = channel_item_query.count()

    logger.info(f"[notify] 设备 {device_id} 找到 {len(pending_tasks)} 个待执行任务, {pending_channel_count} 个待分发通道项")

    if pending_tasks or pending_channel_count > 0:
        sent = await pair_ws_manager.send_to_device(device_id, {"event": "new_task_available"})
        logger.info(f"[notify] 向设备 {device_id} 推送 new_task_available: {'成功' if sent else '失败'}")

@router.websocket("/ws/status")
async def ws_device_status(websocket: WebSocket):
    """业务函数：处理 ws_device_status 对应的业务流程、校验或数据转换。"""
    """Device maintains a persistent WS connection for status tracking.
    Server detects disconnect immediately → marks device offline → broadcasts to admins.

    Authentication: device sends {"type":"auth","device_id":"...","secret":"..."}
    as the first message after connect (not in URL).
    """
    from app.db.models.device_operations import Device
    from app.config import DEVICE_SECRET

    await websocket.accept()

    # Read auth message (first message after connect)
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except (asyncio.TimeoutError, Exception):
        await websocket.close(code=4001, reason="Auth timeout or invalid message")
        return

    device_id = auth_msg.get("device_id", "")
    secret = auth_msg.get("secret", "")

    if not secret or not device_id:
        await websocket.close(code=4001, reason="Missing device_id or secret")
        return

    db = next(get_db())
    try:
        if secret != DEVICE_SECRET:
            device = db.query(Device).filter(Device.device_secret == secret).first()
            if not device:
                await websocket.close(code=4001, reason="Invalid secret")
                return
            device_id = device.id

        # Register WS connection FIRST — before DB update — so _offline_checker
        # never sees "DB online but no WS" during the race window
        await pair_ws_manager.register_device_status(device_id, websocket)

        # Mark device online and capture IP
        from app.domains.device_operations.device_service import device_service
        ws_client_ip = websocket.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ws_client_ip:
            ws_client_ip = websocket.client.host if websocket.client else ""
        device_service.update_heartbeat(db, device_id, ip=ws_client_ip)
        await pair_ws_manager.broadcast_to_admins({
            "event": "device_status_changed",
            "device_id": device_id,
            "status": "online",
        })

        # Check for pending tasks and notify device
        await _notify_pending_tasks(db, device_id)

        import logging
        _ws_log = logging.getLogger("device_ws")
        from starlette.websockets import WebSocketDisconnect
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=120)
                    if msg == '{"event":"device_disconnect"}':
                        _ws_log.info("device %s disconnected (explicit), marking offline", device_id)
                        try:
                            dev = db.query(Device).filter(Device.id == device_id).first()
                            if dev:
                                dev.status = "offline"
                                dev.last_seen_at = bj_now()
                                db.commit()
                        except Exception:
                            _ws_log.warning("device %s offline mark failed", device_id, exc_info=True)
                        await pair_ws_manager.broadcast_to_admins({
                            "event": "device_status_changed",
                            "device_id": device_id,
                            "status": "offline",
                        })
                        break
                    if msg == "ping":
                        await websocket.send_text("pong")
                        # Record heartbeat in memory — _offline_checker flushes to DB
                        pair_ws_manager.record_heartbeat(device_id, bj_now())
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_text("ping")
                        msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                    except asyncio.TimeoutError:
                        _ws_log.warning("device %s unresponsive to ping", device_id)
                        break
                    except WebSocketDisconnect:
                        _ws_log.info("device %s disconnected during ping probe", device_id)
                        break
                    except Exception:
                        _ws_log.warning("device %s error during ping probe", device_id, exc_info=True)
                        break
                except WebSocketDisconnect as dis:
                    _ws_log.info("device %s disconnected (code=%s)", device_id, dis.code)
                    break
        except Exception:
            _ws_log.warning("device %s WS loop exited with error", device_id, exc_info=True)
        finally:
            # 只在本连接仍是活跃连接时才清理（避免重连竞态）
            # WS 断开不标记离线 — _offline_checker 通过心跳超时统一判定
            if pair_ws_manager._device_status_connections.get(device_id) is websocket:
                pair_ws_manager.unregister_device_status(device_id)
    finally:
        db.close()
