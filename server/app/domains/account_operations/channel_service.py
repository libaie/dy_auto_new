"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 channel_service 相关业务规则、状态转换和外部系统边界。
"""

from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy import update, and_, exists, select, or_
from sqlalchemy.orm import Session

from app.db.models.account_operations import Account, AccountGroup, AccountGroupMember, Channel, ChannelItem
from app.db.models import Task as DBTask, Device as DBDevice
from app.models import TaskStatus


def _busy_account_ids(db: Session) -> set[str]:
    """Return account IDs currently locked by any assigned item or running task."""
    busy = set()
    for (aid,) in db.query(ChannelItem.account_id).filter(
        ChannelItem.status == "assigned"
    ).distinct().all():
        busy.add(aid)
    for (aid,) in db.query(DBTask.account_id).filter(
        DBTask.status == TaskStatus.RUNNING.value
    ).distinct().all():
        busy.add(aid)
    return busy


MAX_KEYWORDS = 500


def _unique_nonempty(values: list) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _inject_nurture_keyword_matrix(params: dict, keyword: str) -> dict:
    if not isinstance(params, dict) or params.get("sub_tasks") is None:
        return params
    matrix = params.get("keyword_matrix") or []
    if not isinstance(matrix, list):
        matrix = []
    params["keyword_matrix"] = _unique_nonempty([keyword] + matrix)
    return params


def _resolve_nurture_subtask_templates(db: Session, params: dict, keyword: str) -> dict:
    sub_tasks = params.get("sub_tasks")
    if not isinstance(sub_tasks, list):
        return params
    try:
        from app.domains.content_collection.content_service import content_service as cs
    except Exception:
        return params
    for sub_task in sub_tasks:
        if not isinstance(sub_task, dict) or sub_task.get("type") != "comment":
            continue
        template_id = sub_task.get("content_template_id")
        if not template_id or sub_task.get("content"):
            continue
        try:
            tpl_body = cs.get_template_body(db, template_id)
            if tpl_body:
                sub_task["content"] = cs.substitute_variables(tpl_body, {"keyword": keyword or ""})
        except Exception:
            pass
    return params


def _get_active_accounts(db: Session, group_id: str) -> list[Account]:
    """Get active accounts in a group."""
    members = db.query(AccountGroupMember).filter(
        AccountGroupMember.group_id == group_id
    ).all()
    account_ids = [m.account_id for m in members]
    if not account_ids:
        return []
    accounts = db.query(Account).filter(
        Account.id.in_(account_ids),
        Account.status == "active",
    ).all()
    return accounts


class ChannelService:

    def create_channel(
        self,
        db: Session,
        group_id: str,
        task_type: str,
        account_mode: str,
        keywords: list[str],
        params_template: dict,
        account_id: Optional[str] = None,
        cooldown_seconds: int = 300,
        delay_range: list[int] = None,
        user_id: Optional[str] = None,
    ) -> Channel:
        if len(keywords) > MAX_KEYWORDS:
            raise ValueError(f"关键词最多 {MAX_KEYWORDS} 个，当前 {len(keywords)} 个")

        if delay_range is None:
            delay_range = [3000, 8000]

        # Validate group exists
        group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
        if not group:
            raise ValueError(f"分组 {group_id} 不存在")

        # Get active accounts for distribution
        active_accounts = _get_active_accounts(db, group_id)
        if not active_accounts:
            raise ValueError("该分组内没有活跃账号")

        if account_mode == "single_account":
            if not account_id:
                raise ValueError("single_account 模式下 account_id 必填")
            acc = db.query(Account).filter(
                Account.id == account_id, Account.status == "active"
            ).first()
            if not acc:
                raise ValueError(f"账号 {account_id} 不存在或非 active 状态")
            item_accounts = [account_id] * len(keywords)
        else:
            item_accounts = self._round_robin_assign(db, keywords, active_accounts)

        ch = Channel(
            group_id=group_id,
            task_type=task_type,
            status="active",
            account_mode=account_mode,
            account_id=account_id,
            user_id=user_id,
            params_template=params_template,
            cooldown_seconds=cooldown_seconds,
            delay_range=delay_range,
            max_keywords=MAX_KEYWORDS,
        )
        db.add(ch)
        db.flush()

        for i, keyword in enumerate(keywords):
            item = ChannelItem(
                channel_id=ch.id,
                keyword=keyword,
                account_id=item_accounts[i],
                status="pending",
                queue_position=i,
            )
            db.add(item)

        db.commit()
        db.refresh(ch)
        return ch

    def _round_robin_assign(
        self, db: Session, keywords: list[str], accounts: list[Account]
    ) -> list[str]:
        """Assign accounts to keywords using round-robin, preferring least-used today."""
        if not accounts:
            raise ValueError("无可用账号")

        from app.domains.reporting.stats_service import stats_service

        account_usage = []
        for acc in accounts:
            counts = stats_service.get_today_counts(db, acc.id)
            total = sum(counts.values())
            account_usage.append((acc, total))
        account_usage.sort(key=lambda x: x[1])

        sorted_accounts = [acc for acc, _ in account_usage]
        result = []
        for i in range(len(keywords)):
            acc = sorted_accounts[i % len(sorted_accounts)]
            result.append(acc.id)
        return result

    def claim_channel_item(self, db: Session, device_id: str):
        """Claim a pending channel item. Returns (PydanticTask, channel_item_id) or None."""
        from app.domains.task_operations.task_service import _db_task_to_pydantic
        from app.domains.reporting.stats_service import stats_service
        from app.models import TaskType, TaskStatus

        now = bj_now()

        # Stale recovery: reset items assigned > 5 min ago
        # Skip items whose device is still online (slow but alive).
        # Also reset the associated RUNNING task to PENDING to prevent
        # duplicate execution when the item is re-claimed.
        from datetime import timedelta
        stale_threshold = now - timedelta(seconds=300)
        online_threshold = now - timedelta(seconds=120)
        online_device_ids = {
            d[0] for d in db.query(DBDevice.id).filter(
                DBDevice.last_seen_at.isnot(None),
                DBDevice.last_seen_at >= online_threshold,
            ).all()
        }
        stale_items = db.query(ChannelItem).filter(
            ChannelItem.status == "assigned",
            ChannelItem.assigned_at.isnot(None),
            ChannelItem.assigned_at < stale_threshold,
            ~ChannelItem.assigned_device_id.in_(online_device_ids),
        ).all()
        stale_channel_ids = set()
        stale_task_ids = []
        for si in stale_items:
            if si.task_id:
                stale_task_ids.append(si.task_id)
            si.status = "pending"
            si.assigned_device_id = None
            si.assigned_at = None
            si.task_id = None
            stale_channel_ids.add(si.channel_id)
        if stale_items:
            db.flush()
            # Cancel orphaned tasks — channel will create fresh ones on re-claim.
            # Must NOT reset to PENDING (would create duplicate direct-queue retry).
            if stale_task_ids:
                import logging
                _stale_log = logging.getLogger("channel_service")
                _stale_log.info("Stale recovery: cancelling %d orphaned tasks for %d channel items",
                               len(stale_task_ids), len(stale_items))
                from app.models import TaskStatus as TS
                db.query(DBTask).filter(
                    DBTask.id.in_(stale_task_ids),
                    DBTask.status == TaskStatus.RUNNING.value,  # only cancel running tasks
                ).update(
                    {"status": TS.CANCELLED.value, "completed_at": bj_now()},
                    synchronize_session=False,
                )
            for cid in stale_channel_ids:
                self._reactivate_channel(db, cid)
        db.expire_all()

        # Orphan cleanup: reset assigned items whose linked task is already terminal
        # (cancelled/failed).  The regular stale-recovery above requires the device
        # to be offline, but these items are stuck even when the device IS online
        # because the task will never execute.  Without this the channel is deadlocked.
        orphan_items = db.query(ChannelItem).join(
            DBTask, ChannelItem.task_id == DBTask.id
        ).filter(
            ChannelItem.status == "assigned",
            ChannelItem.task_id.isnot(None),
            DBTask.status.in_([TaskStatus.CANCELLED.value, TaskStatus.FAILED.value]),
        ).all()
        if orphan_items:
            import logging
            _orphan_log = logging.getLogger("channel_service")
            _orphan_log.info("Orphan cleanup: resetting %d assigned items with terminal tasks",
                            len(orphan_items))
            orphan_channel_ids = set()
            for oi in orphan_items:
                oi.status = "pending"
                oi.assigned_device_id = None
                oi.assigned_at = None
                oi.task_id = None
                orphan_channel_ids.add(oi.channel_id)
            db.flush()
            for cid in orphan_channel_ids:
                self._reactivate_channel(db, cid)

        # Build routing filter based on device's bound_account_id
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        bound_account_id = device.bound_account_id if device else None
        device_user_id = device.user_id if device else None

        # Find active channels with pending items, scoped to device's user
        channel_query = db.query(Channel).filter(
            Channel.status == "active",
            Channel.deleted_at.is_(None),
        )
        if device_user_id:
            from sqlalchemy import or_ as ch_or
            channel_query = channel_query.filter(
                ch_or(Channel.user_id == device_user_id, Channel.user_id.is_(None))
            )
        active_channels = channel_query.all()

        # Self-heal: re-activate completed channels with remaining pending/assigned items.
        # cancelled/deleted are terminal states — never auto-resurrect.
        stuck_query = db.query(Channel).filter(
            Channel.status == "completed",
            Channel.deleted_at.is_(None),
        )
        if device_user_id:
            from sqlalchemy import or_ as ch_or2
            stuck_query = stuck_query.filter(
                ch_or2(Channel.user_id == device_user_id, Channel.user_id.is_(None))
            )
        stuck_channels = stuck_query.all()
        for sc in stuck_channels:
            has_pending = db.query(ChannelItem).filter(
                ChannelItem.channel_id == sc.id,
                ChannelItem.status.in_(["pending", "assigned"]),
            ).first()
            if has_pending:
                sc.status = "active"
                sc.completed_at = None
                active_channels.append(sc)
        if stuck_channels:
            db.flush()

        if not active_channels:
            return None

        channel_ids = [ch.id for ch in active_channels]
        channel_map = {ch.id: ch for ch in active_channels}

        # Build candidate query with account routing

        # Get pending items from active channels
        query = db.query(ChannelItem).filter(
            ChannelItem.channel_id.in_(channel_ids),
            ChannelItem.status == "pending",
        )
        if bound_account_id:
            query = query.filter(ChannelItem.account_id == bound_account_id)
        else:
            # Unbound device: exclude accounts bound to other devices
            bound_ids_subq = select(DBDevice.bound_account_id).where(
                DBDevice.bound_account_id.isnot(None)
            )
            query = query.filter(~ChannelItem.account_id.in_(bound_ids_subq))

        # Level 1: pre-filter accounts already busy (assigned/running) at SQL level
        busy_ids = _busy_account_ids(db)
        if busy_ids:
            query = query.filter(~ChannelItem.account_id.in_(busy_ids))

        candidates = query.order_by(ChannelItem.queue_position.asc()).limit(50).all()

        for item in candidates:
            ch = channel_map[item.channel_id]

            # Filter: account must be active
            account = db.query(Account).filter(Account.id == item.account_id).first()
            if not account or account.status != "active":
                continue

            # Filter: per-account concurrency (check both ChannelItem and Task tables)
            running_item = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "assigned",
                ChannelItem.channel_id.in_(channel_ids),
            ).first()
            if running_item:
                continue

            running_task = db.query(DBTask).filter(
                DBTask.account_id == item.account_id,
                DBTask.status == TaskStatus.RUNNING.value,
            ).first()
            if running_task:
                continue

            # Filter: cooldown（同一设备刚完成的不受限，反检测已控制节奏）
            last_completed = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "completed",
                ChannelItem.completed_at.isnot(None),
            ).order_by(ChannelItem.completed_at.desc()).first()
            if last_completed and ch.cooldown_seconds > 0:
                same_device = last_completed.assigned_device_id == device_id
                if not same_device:
                    elapsed = (now - last_completed.completed_at.replace(tzinfo=None)).total_seconds()
                    if elapsed < ch.cooldown_seconds:
                        continue

            # Filter: daily quota（reply_comment 只在 reply 配额耗尽时阻塞，follow/DM 由 handler 优雅降级）
            if not stats_service.check_quota(db, item.account_id, ch.task_type, ch.params_template):
                continue

            # Optimistic lock: claim the item + account-level atomic guard
            # The WHERE clause includes two subqueries that ensure the account
            # has no other assigned item or running task at the moment of UPDATE.
            result = db.execute(
                update(ChannelItem)
                .where(
                    ChannelItem.id == item.id,
                    ChannelItem.status == "pending",
                    # Account-level: no other assigned ChannelItem for this account
                    ~exists().where(
                        and_(
                            ChannelItem.account_id == item.account_id,
                            ChannelItem.status == "assigned",
                        )
                    ),
                    # Account-level: no running Task for this account
                    ~exists().where(
                        and_(
                            DBTask.account_id == item.account_id,
                            DBTask.status == TaskStatus.RUNNING.value,
                        )
                    ),
                )
                .values(
                    status="assigned",
                    assigned_device_id=device_id,
                    assigned_at=now,
                )
            )
            if result.rowcount == 0:
                continue

            # Flush-only Task creation (no commit)
            # Task is created as RUNNING to prevent get_pending_task from stealing it
            params = dict(ch.params_template or {})
            params["keyword"] = item.keyword
            if ch.task_type == "nurture":
                params = _inject_nurture_keyword_matrix(params, item.keyword)
                params = _resolve_nurture_subtask_templates(db, params, item.keyword)
            # Resolve dm_sequence_id into inline dm_messages (keep id for device cache/variants)
            seq_id = params.get("dm_sequence_id")
            if seq_id:
                try:
                    from app.db.models.content_collection import DMSequence
                    seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
                    if seq and seq.messages:
                        params["dm_messages"] = seq.messages
                        first = seq.messages[0]
                        if isinstance(first, dict):
                            params["content"] = first.get("content", "")
                    else:
                        params.pop("dm_sequence_id", None)
                except Exception:
                    params.pop("dm_sequence_id", None)

            # Resolve content_template_id with the item's keyword (sync, no AI)
            template_id = params.pop("content_template_id", None)
            if template_id:
                try:
                    from app.domains.content_collection.content_service import content_service as cs
                    tpl_body = cs.get_template_body(db, template_id)
                    if tpl_body:
                        params["content"] = cs.substitute_variables(
                            tpl_body, {"keyword": item.keyword}
                        )
                except Exception:
                    pass
            # 注入账号配额和服务端每日计数（设备端日志和服务端同步）
            if ch.task_type == "reply_comment":
                remaining = stats_service.get_remaining_quotas(db, item.account_id)
                limits = stats_service._get_limits(db, item.account_id)
                today_counts = stats_service.get_today_counts(db, item.account_id)
                if "max_follows" not in params:
                    params["max_follows"] = remaining.get("follows", 20)
                if "max_dms" not in params:
                    params["max_dms"] = remaining.get("dms", 10)
                # 服务端每日配额上限（-1=不限）
                params["server_daily_limit_reply"] = limits.get("replies", 200)
                params["server_daily_limit_follow"] = limits.get("follows", 100)
                params["server_daily_limit_dm"] = limits.get("dms", 75)
                # 服务端今日已完成计数
                params["server_today_reply"] = today_counts.get("replies", 0)
                params["server_today_follow"] = today_counts.get("follows", 0)
                params["server_today_dm"] = today_counts.get("dms", 0)
            # Convert max_age_days + max_age_unit → max_age_seconds for device precision
            _age_days = params.get("max_age_days")
            if _age_days is not None and _age_days != -1:
                _unit = params.get("max_age_unit") or "days"
                _mult = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}.get(_unit, 86400)
                params["max_age_seconds"] = _age_days * _mult
            elif _age_days == -1:
                params["max_age_seconds"] = -1
            params = stats_service.inject_task_quota_params(db, item.account_id, ch.task_type, params)
            import uuid
            task = DBTask(
                type=ch.task_type,
                account_id=item.account_id,
                device_id=device_id,
                user_id=ch.user_id,
                params=params,
                status=TaskStatus.RUNNING.value,
                started_at=now,
                lease_id=str(uuid.uuid4()),
            )
            db.add(task)
            db.flush()

            item.task_id = task.id
            db.flush()

            return (_db_task_to_pydantic(task), item.id)

        return None

    def complete_item(self, db: Session, item_id: str, status: str) -> dict:
        """Complete a channel item and check if channel is fully done.

        Returns {"channel_id": str, "stats": dict, "channel_completed": bool}
        for the caller to handle WS broadcast.
        """
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            return {}

        channel_id = item.channel_id

        item.status = status
        item.completed_at = bj_now()
        db.flush()

        channel_completed = False

        # Atomic completion check
        if status in ("completed", "failed"):
            db.execute(
                update(Channel)
                .where(
                    Channel.id == channel_id,
                    Channel.status == "active",
                    ~exists().where(
                        and_(
                            ChannelItem.channel_id == channel_id,
                            ChannelItem.status.notin_(["completed", "failed", "skipped"]),
                        )
                    ),
                )
                .values(status="completed", completed_at=bj_now())
            )
            db.flush()
            db.expire_all()
            ch = db.query(Channel).filter(Channel.id == channel_id).first()
            channel_completed = ch.status == "completed" if ch else False

        stats = self.get_channel_stats(db, channel_id)
        return {"channel_id": channel_id, "stats": stats, "channel_completed": channel_completed}

    def on_risk_control(self, db: Session, account_id: str):
        """Skip all pending channel items for a risk-controlled account."""
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.account_id == account_id,
                ChannelItem.status == "pending",
            )
            .values(status="skipped", completed_at=bj_now())
        )
        db.flush()
        db.expire_all()

    def update_channel_status(self, db: Session, channel_id: str, new_status: str, user_id: Optional[str] = None):
        """Update channel status with validation.

        On cancel: skips pending items AND cancels running tasks for assigned items
        so devices receive cancellation via their next poll (cancelled_task_id).
        """
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")

        valid_transitions = {
            "active": ["paused", "cancelled"],
            "paused": ["active", "cancelled"],
        }
        allowed = valid_transitions.get(ch.status, [])
        if new_status not in allowed:
            raise ValueError(f"不允许从 {ch.status} 转换到 {new_status}")

        ch.status = new_status
        if new_status in ("paused", "cancelled"):
            # Collect assigned task IDs BEFORE changing ChannelItem status
            assigned_task_ids = [
                row[0] for row in db.query(ChannelItem.task_id).filter(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status == "assigned",
                    ChannelItem.task_id.isnot(None),
                ).all()
            ]
            # Skip all pending items
            db.execute(
                update(ChannelItem)
                .where(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status == "pending",
                )
                .values(status="skipped", completed_at=bj_now())
            )
            # Skip assigned items — cancelled channel must leave no active items
            db.execute(
                update(ChannelItem)
                .where(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status == "assigned",
                )
                .values(status="skipped", completed_at=bj_now())
            )
            # Cancel running tasks for assigned items — devices pick this up
            # via check_cancelled_running in their next poll.
            # Keep device_id so the cancellation can be delivered; device acks
            # via report_result(CANCELLED) which clears it then.
            if assigned_task_ids:
                db.execute(
                    update(DBTask)
                    .where(
                        DBTask.id.in_(assigned_task_ids),
                        DBTask.status == TaskStatus.RUNNING.value,
                    )
                    .values(status=TaskStatus.CANCELLED.value, completed_at=bj_now())
                )
        db.commit()

    def soft_delete_channel(self, db: Session, channel_id: str, user_id: Optional[str] = None):
        """Soft delete a channel — cancels pending + assigned items."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        ch.deleted_at = bj_now()
        now = bj_now()
        # Collect assigned task IDs BEFORE changing ChannelItem status
        assigned_task_ids = [
            row[0] for row in db.query(ChannelItem.task_id).filter(
                ChannelItem.channel_id == channel_id,
                ChannelItem.status == "assigned",
                ChannelItem.task_id.isnot(None),
            ).all()
        ]
        # Skip pending items
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.channel_id == channel_id,
                ChannelItem.status == "pending",
            )
            .values(status="skipped", completed_at=now)
        )
        # Skip assigned items
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.channel_id == channel_id,
                ChannelItem.status == "assigned",
            )
            .values(status="skipped", completed_at=now)
        )
        # Cancel running tasks for assigned items.
        # Keep device_id so the cancellation can be delivered; device acks
        # via report_result(CANCELLED) which clears it then.
        if assigned_task_ids:
            db.execute(
                update(DBTask)
                .where(
                    DBTask.id.in_(assigned_task_ids),
                    DBTask.status == TaskStatus.RUNNING.value,
                )
                .values(status=TaskStatus.CANCELLED.value, completed_at=now)
            )
        db.commit()

    def append_items(self, db: Session, channel_id: str, keywords: list[str], user_id: Optional[str] = None):
        """Append new keywords to an active channel."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        if ch.status != "active":
            raise ValueError("只能向活跃通道追加关键词")

        existing_count = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).count()
        if existing_count + len(keywords) > ch.max_keywords:
            raise ValueError(f"超出最大关键词数 {ch.max_keywords}")

        if ch.account_mode == "single_account":
            account_ids = [ch.account_id] * len(keywords)
        else:
            active_accounts = _get_active_accounts(db, ch.group_id)
            account_ids = self._round_robin_assign(db, keywords, active_accounts)

        for i, keyword in enumerate(keywords):
            item = ChannelItem(
                channel_id=channel_id,
                keyword=keyword,
                account_id=account_ids[i],
                status="pending",
                queue_position=existing_count + i,
            )
            db.add(item)
        db.commit()

    def _reactivate_channel(self, db: Session, channel_id: str):
        """If channel is completed and has pending items, revert to active.
        cancelled/deleted are terminal — never auto-resurrect."""
        ch = db.query(Channel).filter(Channel.id == channel_id).first()
        if ch and ch.status == "completed":
            ch.status = "active"
            ch.completed_at = None
            db.flush()

    def edit_channel(
        self,
        db: Session,
        channel_id: str,
        group_id: Optional[str] = None,
        account_mode: Optional[str] = None,
        account_id: Optional[str] = None,
        params_template: Optional[dict] = None,
        cooldown_seconds: Optional[int] = None,
        sync_to_items: bool = False,
        user_id: Optional[str] = None,
    ) -> Channel:
        """Edit channel metadata. Only active/paused channels allowed."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        if ch.status not in ("active", "paused"):
            raise ValueError("只能编辑活跃或暂停状态的通道")

        if all(v is None for v in (group_id, account_mode, account_id, params_template, cooldown_seconds)):
            raise ValueError("至少提供一个要修改的字段")

        if group_id is not None:
            group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
            if not group:
                raise ValueError(f"分组 {group_id} 不存在")
            ch.group_id = group_id

        if account_mode is not None:
            ch.account_mode = account_mode

        if account_id is not None:
            acc = db.query(Account).filter(Account.id == account_id, Account.status == "active").first()
            if not acc:
                raise ValueError(f"账号 {account_id} 不存在或非 active 状态")
            effective_group_id = group_id if group_id is not None else ch.group_id
            member = db.query(AccountGroupMember).filter(
                AccountGroupMember.group_id == effective_group_id,
                AccountGroupMember.account_id == account_id,
            ).first()
            if not member:
                raise ValueError(f"账号 {account_id} 不属于分组 {effective_group_id}")
            ch.account_id = account_id

        if params_template is not None:
            ch.params_template = params_template

        if cooldown_seconds is not None:
            ch.cooldown_seconds = cooldown_seconds

        # Sync to pending/assigned items when requested
        if sync_to_items:
            if account_id is not None:
                db.query(ChannelItem).filter(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status.in_(["pending", "assigned"]),
                ).update({"account_id": account_id}, synchronize_session=False)
            elif group_id is not None and ch.account_mode == "round_robin":
                active_accounts = _get_active_accounts(db, ch.group_id)
                if active_accounts:
                    pending_items = db.query(ChannelItem).filter(
                        ChannelItem.channel_id == channel_id,
                        ChannelItem.status.in_(["pending", "assigned"]),
                    ).order_by(ChannelItem.queue_position).all()
                    account_ids = self._round_robin_assign(
                        db, [i.keyword for i in pending_items], active_accounts
                    )
                    with db.begin_nested():
                        for i, item in enumerate(pending_items):
                            item.account_id = account_ids[i]

        db.commit()
        db.refresh(ch)
        return ch

    def edit_item(
        self,
        db: Session,
        item_id: str,
        account_id: Optional[str] = None,
        assigned_device_id: Optional[str] = None,
        keyword: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ChannelItem:
        """Edit a single channel item. Only pending items allowed."""
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} 不存在")
        if user_id:
            ch = db.query(Channel).filter(Channel.id == item.channel_id, Channel.user_id == user_id).first()
            if not ch:
                raise ValueError(f"Item {item_id} 不属于当前用户")
        if item.status != "pending":
            raise ValueError("只能编辑待处理的子项")

        if account_id is not None:
            acc = db.query(Account).filter(Account.id == account_id, Account.status == "active").first()
            if not acc:
                raise ValueError(f"账号 {account_id} 不存在或非 active 状态")
            ch = db.query(Channel).filter(
                Channel.id == item.channel_id,
                Channel.deleted_at.is_(None),
            ).first()
            if ch:
                member = db.query(AccountGroupMember).filter(
                    AccountGroupMember.group_id == ch.group_id,
                    AccountGroupMember.account_id == account_id,
                ).first()
                if not member:
                    raise ValueError(f"账号 {account_id} 不属于通道分组 {ch.group_id}")
            item.account_id = account_id

        if assigned_device_id is not None:
            dev = db.query(DBDevice).filter(DBDevice.id == assigned_device_id).first()
            if not dev:
                raise ValueError(f"设备 {assigned_device_id} 不存在")
            item.assigned_device_id = assigned_device_id

        if keyword is not None:
            if not keyword.strip():
                raise ValueError("关键词不能为空")
            item.keyword = keyword

        db.commit()
        db.refresh(item)
        return item

    def batch_edit_items(
        self,
        db: Session,
        item_ids: list[str],
        account_id: Optional[str] = None,
        assigned_device_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """Batch edit items. Failures don't block successes."""
        updated = 0
        skipped = []
        errors = []

        if account_id is not None:
            acc = db.query(Account).filter(Account.id == account_id, Account.status == "active").first()
            if not acc:
                return {"updated": 0, "skipped": [], "errors": [f"账号 {account_id} 不存在或非 active 状态"]}

        if assigned_device_id is not None:
            dev = db.query(DBDevice).filter(DBDevice.id == assigned_device_id).first()
            if not dev:
                return {"updated": 0, "skipped": [], "errors": [f"设备 {assigned_device_id} 不存在"]}

        # Load all items in one query instead of N per-item queries
        items = db.query(ChannelItem).filter(ChannelItem.id.in_(item_ids)).all()
        item_map = {i.id: i for i in items}

        # Pre-load channel ownership for user-scoping
        channel_ids = []
        if items:
            channel_ids = list(set(i.channel_id for i in items))

        if user_id and channel_ids:
            owned_channels = set(
                ch[0] for ch in db.query(Channel.id).filter(
                    Channel.id.in_(channel_ids),
                    Channel.user_id == user_id,
                ).all()
            )
        else:
            owned_channels = None

        # Pre-load channel-group mapping for group membership validation
        valid_group_ids = set()
        if account_id is not None and channel_ids:
            channels = db.query(Channel).filter(
                Channel.id.in_(channel_ids),
                Channel.deleted_at.is_(None),
            ).all()
            channel_group_map = {c.id: c.group_id for c in channels}
            group_ids = list(set(channel_group_map.values()))
            if group_ids:
                rows = db.query(AccountGroupMember.group_id).filter(
                    AccountGroupMember.group_id.in_(group_ids),
                    AccountGroupMember.account_id == account_id,
                ).all()
                valid_group_ids = set(r[0] for r in rows)
        else:
            channel_group_map = {}

        for item_id in item_ids:
            try:
                item = item_map.get(item_id)
                if not item:
                    errors.append(f"{item_id}: 不存在")
                    continue
                if owned_channels is not None and item.channel_id not in owned_channels:
                    skipped.append(item_id)
                    continue
                if item.status != "pending":
                    skipped.append(item_id)
                    continue
                if account_id is not None and valid_group_ids:
                    item_group = channel_group_map.get(item.channel_id)
                    if item_group and item_group not in valid_group_ids:
                        skipped.append(item_id)
                        continue

                if account_id is not None:
                    item.account_id = account_id
                if assigned_device_id is not None:
                    item.assigned_device_id = assigned_device_id

                updated += 1
            except Exception as e:
                errors.append(f"{item_id}: {str(e)}")

        db.commit()
        return {"updated": updated, "skipped": skipped, "errors": errors}

    def update_item_status(self, db: Session, item_id: str, new_status: str, user_id: Optional[str] = None):
        """Update a single channel item status (skip/requeue)."""
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} 不存在")
        if user_id:
            ch = db.query(Channel).filter(Channel.id == item.channel_id, Channel.user_id == user_id).first()
            if not ch:
                raise ValueError(f"Item {item_id} 不属于当前用户")

        valid = {"pending": ["skipped"], "failed": ["pending"]}
        allowed = valid.get(item.status, [])
        if new_status not in allowed:
            raise ValueError(f"不允许从 {item.status} 转换到 {new_status}")

        item.status = new_status
        if new_status == "pending":
            item.assigned_device_id = None
            item.task_id = None
            item.completed_at = None
            self._reactivate_channel(db, item.channel_id)
        db.commit()

    def get_channel(self, db: Session, channel_id: str, user_id: Optional[str] = None) -> Optional[Channel]:
        query = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.deleted_at.is_(None),
        )
        if user_id:
            query = query.filter(Channel.user_id == user_id)
        return query.first()

    def list_channels(self, db: Session, user_id: Optional[str] = None) -> list[Channel]:
        query = db.query(Channel).filter(Channel.deleted_at.is_(None))
        if user_id:
            query = query.filter(Channel.user_id == user_id)
        return query.order_by(Channel.created_at.desc()).all()

    def get_channel_stats(self, db: Session, channel_id: str) -> dict:
        items = db.query(ChannelItem).filter(
            ChannelItem.channel_id == channel_id
        ).all()
        stats = {
            "total": len(items),
            "pending": 0,
            "assigned": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in items:
            if item.status in stats:
                stats[item.status] += 1
        return stats

    def get_channels_stats_batch(self, db: Session, channel_ids: list[str]) -> dict[str, dict]:
        """Batch query stats for multiple channels. Returns {channel_id: stats_dict}."""
        from sqlalchemy import func
        if not channel_ids:
            return {}
        rows = db.query(
            ChannelItem.channel_id,
            ChannelItem.status,
            func.count(ChannelItem.id).label("cnt"),
        ).filter(
            ChannelItem.channel_id.in_(channel_ids),
        ).group_by(ChannelItem.channel_id, ChannelItem.status).all()

        result = {cid: {"total": 0, "pending": 0, "assigned": 0, "completed": 0, "failed": 0, "skipped": 0} for cid in channel_ids}
        for channel_id, status, cnt in rows:
            result[channel_id]["total"] += cnt
            if status in result[channel_id]:
                result[channel_id][status] = cnt
        return result


channel_service = ChannelService()
