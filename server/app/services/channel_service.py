"""Channel service -- create, claim, complete, stale recovery, risk control."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db_models import (
    Channel, ChannelItem, Account, AccountGroup, AccountGroupMember,
    Task as DBTask, Device as DBDevice,
)


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

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Stale recovery: reset items assigned > 10 min ago
        from datetime import timedelta
        stale_threshold = now - timedelta(seconds=600)
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.status == "assigned",
                ChannelItem.assigned_at.isnot(None),
                ChannelItem.assigned_at < stale_threshold,
            )
            .values(status="pending", assigned_device_id=None, assigned_at=None, task_id=None)
        )
        db.flush()
        db.expire_all()

        # Find active channels with pending items
        active_channels = db.query(Channel).filter(
            Channel.status == "active",
            Channel.deleted_at.is_(None),
        ).all()

        if not active_channels:
            return None

        channel_ids = [ch.id for ch in active_channels]
        channel_map = {ch.id: ch for ch in active_channels}

        # Build routing filter based on device's bound_account_id
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        bound_account_id = device.bound_account_id if device else None

        # Get pending items from active channels
        candidates = db.query(ChannelItem).filter(
            ChannelItem.channel_id.in_(channel_ids),
            ChannelItem.status == "pending",
        ).order_by(ChannelItem.queue_position.asc()).limit(10).all()

        for item in candidates:
            ch = channel_map[item.channel_id]

            # Filter: account must be active
            account = db.query(Account).filter(Account.id == item.account_id).first()
            if not account or account.status != "active":
                continue

            # Filter: routing (bound device can only claim its account's items)
            if bound_account_id and item.account_id != bound_account_id:
                continue

            # Filter: per-account concurrency
            running = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "assigned",
                ChannelItem.channel_id.in_(channel_ids),
            ).first()
            if running:
                continue

            # Filter: cooldown
            last_completed = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "completed",
                ChannelItem.completed_at.isnot(None),
            ).order_by(ChannelItem.completed_at.desc()).first()
            if last_completed and ch.cooldown_seconds > 0:
                elapsed = (now - last_completed.completed_at.replace(tzinfo=None)).total_seconds()
                if elapsed < ch.cooldown_seconds:
                    continue

            # Filter: daily quota
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
            params = dict(ch.params_template or {})
            params["keyword"] = item.keyword
            task = DBTask(
                type=ch.task_type,
                account_id=item.account_id,
                device_id=device_id,
                params=params,
                status=TaskStatus.PENDING.value,
            )
            db.add(task)
            db.flush()

            item.task_id = task.id
            db.flush()

            return (_db_task_to_pydantic(task), item.id)

        return None

    def get_channel(self, db: Session, channel_id: str) -> Optional[Channel]:
        return db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.deleted_at.is_(None),
        ).first()

    def list_channels(self, db: Session) -> list[Channel]:
        return db.query(Channel).filter(
            Channel.deleted_at.is_(None),
        ).order_by(Channel.created_at.desc()).all()

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


channel_service = ChannelService()
