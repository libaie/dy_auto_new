"""Statistics API — dashboard, daily stats, realtime metrics."""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.config import bj_now

from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Account, Device, Task, DailyStats
from app.domains.reporting.stats_service import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard_summary(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Dashboard overview — account/device/task counts and status distribution."""
    # Account stats
    total_accounts = db.query(Account).count()
    active_accounts = db.query(Account).filter(Account.status == "active").count()
    risk_accounts = db.query(Account).filter(Account.status == "risk_controlled").count()

    # Device stats
    total_devices = db.query(Device).count()
    online_devices = db.query(Device).filter(Device.status == "online").count()

    # Task stats
    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    running_tasks = db.query(Task).filter(Task.status == "running").count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()
    failed_tasks = db.query(Task).filter(Task.status == "failed").count()
    cancelled_tasks = db.query(Task).filter(Task.status == "cancelled").count()

    return {
        "accounts": {
            "total": total_accounts,
            "active": active_accounts,
            "risk_controlled": risk_accounts,
        },
        "devices": {
            "total": total_devices,
            "online": online_devices,
        },
        "tasks": {
            "total": total_tasks,
            "pending": pending_tasks,
            "running": running_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "cancelled": cancelled_tasks,
        },
    }


@router.get("/daily")
def daily_stats(
    date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Daily operation stats for all accounts."""
    if not date:
        date = bj_now().strftime("%Y-%m-%d")

    rows = db.query(DailyStats).filter(DailyStats.date == date).all()
    if not rows:
        return {"date": date, "accounts": []}

    # Batch-load accounts to avoid N+1 query
    account_ids = [row.account_id for row in rows]
    accounts_map = {}
    for a in db.query(Account).filter(Account.id.in_(account_ids)).all():
        accounts_map[a.id] = {"nickname": a.nickname, "daily_limits": a.daily_limits or {}}

    default_limits = {"likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15}

    accounts = [{
        "account_id": row.account_id,
        "nickname": accounts_map.get(row.account_id, {}).get("nickname", "unknown"),
        "daily_limits": accounts_map.get(row.account_id, {}).get("daily_limits") or default_limits,
        "likes": row.likes,
        "comments": row.comments,
        "follows": row.follows,
        "dms": row.dms,
        "replies": row.replies,
    } for row in rows]

    return {"date": date, "accounts": accounts}


@router.get("/accounts/{account_id}")
def account_stats(
    account_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Stats for a specific account — today's counts and remaining quotas."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    today_counts = stats_service.get_today_counts(db, account_id)
    remaining = stats_service.get_remaining_quotas(db, account_id)

    return {
        "account_id": account_id,
        "nickname": account.nickname,
        "today": today_counts,
        "remaining": remaining,
    }


@router.get("/realtime")
def realtime_stats(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Realtime metrics for dashboard auto-refresh."""
    online_devices = db.query(Device).filter(Device.status == "online").count()
    running_tasks = db.query(Task).filter(Task.status == "running").count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()

    return {
        "online_devices": online_devices,
        "running_tasks": running_tasks,
        "pending_tasks": pending_tasks,
    }
