"""Daily stats tracking service — operation counts per account per day."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db_models import DailyStats, Account


# Task type -> daily_stats column mapping
_TASK_TYPE_TO_COLUMN = {
    "search_like": "likes",
    "nurture": "likes",       # nurture 中的 like 操作计入 likes
    "search_comment": "comments",
    "reply_comment": "replies",
    "search_dm": "dms",
    "follow": "follows",
}


class StatsService:
    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

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
            "comments": stats.comments,
            "follows": stats.follows,
            "dms": stats.dms,
            "replies": stats.replies,
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
        for key in ("likes", "comments", "follows", "dms", "replies"):
            limit = limits.get(key, 999)
            used = counts.get(key, 0)
            remaining[key] = max(0, limit - used)
        return remaining


stats_service = StatsService()
