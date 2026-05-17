"""Channel service -- create, claim, complete, stale recovery, risk control."""
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy import update, and_, exists, select
from sqlalchemy.orm import Session

from app.db_models import (
    Channel, ChannelItem, Account, AccountGroup, AccountGroupMember,
    Task as DBTask, Device as DBDevice,
)
from app.models import TaskStatus


MAX_KEYWORDS = 500


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

        from app.services.stats_service import stats_service

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
        from app.services.task_service import _db_task_to_pydantic
        from app.services.stats_service import stats_service
        from app.models import TaskType, TaskStatus

        now = bj_now()

        # Stale recovery: reset items assigned > 5 min ago
        # Skip items whose device is still online (slow but alive).
        # Also reset the associated RUNNING task to PENDING to prevent
        # duplicate execution when the item is re-claimed.
        from datetime import timedelta
        import os
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
            # Reset orphaned RUNNING tasks so they don't linger for 10 min
            if stale_task_ids:
                from app.models import TaskStatus as TS
                db.query(DBTask).filter(
                    DBTask.id.in_(stale_task_ids),
                    DBTask.status == TS.RUNNING.value,
                ).update(
                    {"status": TS.PENDING.value, "device_id": None, "started_at": None},
                    synchronize_session=False,
                )
            for cid in stale_channel_ids:
                self._reactivate_channel(db, cid)
        db.expire_all()

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

        # Self-heal: re-activate completed/cancelled channels that still have pending items
        stuck_query = db.query(Channel).filter(
            Channel.status.in_(["completed", "cancelled"]),
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
            if not stats_service.check_quota(db, item.account_id, ch.task_type):
                continue

            # Optimistic lock: claim the item
            result = db.execute(
                update(ChannelItem)
                .where(ChannelItem.id == item.id, ChannelItem.status == "pending")
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
            # Resolve content_template_id with the item's keyword (sync, no AI)
            template_id = params.pop("content_template_id", None)
            if template_id:
                try:
                    from app.services.content_service import content_service as cs
                    tpl_body = cs.get_template_body(db, template_id)
                    if tpl_body:
                        params["content"] = cs.substitute_variables(
                            tpl_body, {"keyword": item.keyword}
                        )
                except Exception:
                    pass
            # 注入账号剩余配额（reply_comment 设备端需要关注和私信上限）
            if ch.task_type == "reply_comment":
                remaining = stats_service.get_remaining_quotas(db, item.account_id)
                if "max_follows" not in params:
                    params["max_follows"] = remaining.get("follows", 20)
                if "max_dms" not in params:
                    params["max_dms"] = remaining.get("dms", 10)
            task = DBTask(
                type=ch.task_type,
                account_id=item.account_id,
                device_id=device_id,
                user_id=ch.user_id,
                params=params,
                status=TaskStatus.RUNNING.value,
                started_at=now,
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
        """Update channel status with validation."""
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
        if new_status == "cancelled":
            db.execute(
                update(ChannelItem)
                .where(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status == "pending",
                )
                .values(status="skipped", completed_at=bj_now())
            )
        db.commit()

    def soft_delete_channel(self, db: Session, channel_id: str, user_id: Optional[str] = None):
        """Soft delete a channel."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        ch.deleted_at = bj_now()
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.channel_id == channel_id,
                ChannelItem.status == "pending",
            )
            .values(status="skipped", completed_at=bj_now())
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
        """If channel is completed/cancelled but now has pending items, revert to active."""
        ch = db.query(Channel).filter(Channel.id == channel_id).first()
        if ch and ch.status in ("completed", "cancelled"):
            ch.status = "active"
            ch.completed_at = None
            db.flush()

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
