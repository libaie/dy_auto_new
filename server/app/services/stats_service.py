"""Daily stats tracking service — operation counts per account per day."""
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db_models import DailyStats, Account


# Task type -> daily_stats column mapping
_TASK_TYPE_TO_COLUMN = {
    "search_like": "likes",
    "nurture": "nurture_likes",
    "search_comment": "comments",
    "reply_comment": "replies",
    "search_dm": "dms",
    "follow": "follows",
    "collect": "collected",
}


class StatsService:
    def _today(self) -> str:
        return bj_now().strftime("%Y-%m-%d")

    def _get_or_create(self, db: Session, account_id: str, date: str) -> DailyStats:
        """Get or create daily stats row for an account+date."""
        stats = db.query(DailyStats).filter(
            and_(DailyStats.account_id == account_id, DailyStats.date == date)
        ).first()
        if not stats:
            stats = DailyStats(account_id=account_id, date=date)
            db.add(stats)
            db.flush()
        return stats

    def increment(self, db: Session, account_id: str, task_type: str, count: int = 1) -> None:
        """Increment operation count for a task type. Only flushes — caller must commit."""
        column = _TASK_TYPE_TO_COLUMN.get(task_type)
        if not column:
            return
        date = self._today()
        stats = self._get_or_create(db, account_id, date)
        current = getattr(stats, column, 0)
        setattr(stats, column, current + count)
        db.flush()

    def get_today_counts(self, db: Session, account_id: str) -> dict[str, int]:
        """Get today's operation counts for an account."""
        date = self._today()
        stats = self._get_or_create(db, account_id, date)
        return {
            "likes": stats.likes,
            "nurture_likes": stats.nurture_likes,
            "comments": stats.comments,
            "follows": stats.follows,
            "dms": stats.dms,
            "replies": stats.replies,
            "collected": stats.collected,
        }

    def check_quota(self, db: Session, account_id: str, task_type: str) -> bool:
        """Check if account has remaining quota for this task type today.

        Returns True if quota is available, False if limit reached.
        """
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return True  # no account found, don't block

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        # nurture 使用独立列 nurture_likes，与 search_like 分离
        if task_type == "nurture":
            limit = limits.get("nurture_likes", limits.get("likes", 999))
            used = counts.get("nurture_likes", 0)
            return used < limit

        # reply_comment 不阻塞 follow/DM，handler 内部优雅降级
        if task_type == "reply_comment":
            col = _TASK_TYPE_TO_COLUMN.get(task_type)
            if col:
                limit = limits.get(col, 999)
                used = counts.get(col, 0)
                return used < limit
            return True

        column = _TASK_TYPE_TO_COLUMN.get(task_type)
        if not column:
            return True  # unknown type, don't block

        limit = limits.get(column, 999)
        used = counts.get(column, 0)
        return used < limit

    def get_remaining_quotas(self, db: Session, account_id: str) -> dict[str, int]:
        """Get remaining quotas for all operation types."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {}

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        remaining = {}
        for key in ("likes", "nurture_likes", "comments", "follows", "dms", "replies", "collected"):
            limit = limits.get(key, 999)
            used = counts.get(key, 0)
            remaining[key] = max(0, limit - used)
        return remaining


stats_service = StatsService()
