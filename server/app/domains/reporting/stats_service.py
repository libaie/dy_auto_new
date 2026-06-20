"""Daily stats tracking service for reporting and quota checks."""
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models.reporting import DailyStats
from app.db.models import Account


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

_NURTURE_TYPE_TO_COLUMN = {
    "like": "nurture_likes",
    "comment": "comments",
    "follow": "follows",
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

    def _get_limits(self, db: Session, account_id: str) -> dict[str, int]:
        """Get the daily limits for an account."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.daily_limits:
            return {}
        return dict(account.daily_limits)

    def _limit_for_column(self, limits: dict, column_key: str, default: int = 999) -> int:
        if column_key == "nurture_likes":
            return limits.get("nurture_likes", limits.get("likes", default))
        return limits.get(column_key, default)

    def _nurture_quota_columns(self, params: Optional[dict]) -> set[str]:
        if not isinstance(params, dict):
            return {"nurture_likes"}
        action_types: set[str] = set()
        sub_tasks = params.get("sub_tasks")
        if isinstance(sub_tasks, list):
            for sub_task in sub_tasks:
                if isinstance(sub_task, dict):
                    action_types.add(str(sub_task.get("type") or ""))
        else:
            actions = params.get("actions")
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, dict):
                        action_types.add(str(action.get("type") or ""))
            if not action_types:
                action_types.update(["like", "follow"])
        columns = {
            _NURTURE_TYPE_TO_COLUMN[action_type]
            for action_type in action_types
            if action_type in _NURTURE_TYPE_TO_COLUMN
        }
        return columns or {"nurture_likes"}

    def check_quota(self, db: Session, account_id: str, task_type: str, params: Optional[dict] = None) -> bool:
        """Check if account has remaining quota for this task type today.

        Returns True if quota is available, False if limit reached.
        Limit of -1 means unlimited (always returns True).
        """
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return True  # no account found, don't block

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        def _check_limit(column_key: str, default: int = 999) -> bool:
            limit = self._limit_for_column(limits, column_key, default)
            if limit == -1:
                return True
            used = counts.get(column_key, 0)
            return used < limit

        # nurture 使用独立列 nurture_likes，与 search_like 分离
        if task_type == "nurture":
            return all(_check_limit(column_key) for column_key in self._nurture_quota_columns(params))

        # reply_comment 不阻塞 follow/DM，handler 内部优雅降级
        if task_type == "reply_comment":
            col = _TASK_TYPE_TO_COLUMN.get(task_type)
            if col:
                return _check_limit(col, 999)
            return True

        column = _TASK_TYPE_TO_COLUMN.get(task_type)
        if not column:
            return True  # unknown type, don't block

        return _check_limit(column, 999)

    def get_remaining_quotas(self, db: Session, account_id: str) -> dict[str, int]:
        """Get remaining quotas for all operation types."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {}

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        remaining = {}
        for key in ("likes", "nurture_likes", "comments", "follows", "dms", "replies", "collected"):
            limit = self._limit_for_column(limits, key, 999)
            if limit == -1:
                remaining[key] = 999  # -1 = 不限
            else:
                used = counts.get(key, 0)
                remaining[key] = max(0, limit - used)
        return remaining

    def inject_task_quota_params(self, db: Session, account_id: str, task_type: str, params: dict) -> dict:
        params = dict(params or {})
        if task_type != "nurture":
            return params
        remaining = self.get_remaining_quotas(db, account_id)
        params["server_remaining_nurture_likes"] = remaining.get("nurture_likes", 999)
        params["server_remaining_comments"] = remaining.get("comments", 999)
        params["server_remaining_follows"] = remaining.get("follows", 999)
        return params


stats_service = StatsService()
