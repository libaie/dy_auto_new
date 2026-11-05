"""Shared server deadline matching the device watchdog's minute-based contract."""
import math
import os
from datetime import timedelta


def normalized_nurture_minutes(params):
    """Accept positive finite numeric minutes; use the handler default otherwise."""
    value = (params or {}).get('duration')
    try:
        minutes = float(value) if not isinstance(value, bool) else 0
    except (TypeError, ValueError, OverflowError):
        minutes = 0
    return minutes if math.isfinite(minutes) and minutes > 0 else (60.0 if isinstance((params or {}).get("sub_tasks"), list) else 30.0)


def task_timeout(task):
    try:
        configured = float(os.getenv('TASK_STALE_MINUTES', '10'))
    except (TypeError, ValueError):
        configured = 10
    if not math.isfinite(configured) or configured < 10:
        configured = 10
    minutes = max(10, configured)
    if task.type == 'nurture':
        minutes = max(minutes, normalized_nurture_minutes(task.params) + 2)
    return timedelta(minutes=minutes)


def task_expired(task, now):
    return task.started_at is not None and now - task.started_at >= task_timeout(task)
