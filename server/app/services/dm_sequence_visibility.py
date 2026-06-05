"""Visibility rules for sending DM sequence templates to devices."""

from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_models import DMSequence, Device, Task
from app.models import TaskStatus


def _extract_sequence_id(params: Optional[dict]) -> Optional[str]:
    if not isinstance(params, dict):
        return None
    seq_id = params.get("dm_sequence_id")
    return str(seq_id) if seq_id else None


def _task_sequence_ids_for_device(db: Session, device_id: Optional[str]) -> set[str]:
    if not device_id:
        return set()

    rows = db.query(Task.params).filter(
        Task.device_id == device_id,
        Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]),
    ).all()
    ids: set[str] = set()
    for (params,) in rows:
        seq_id = _extract_sequence_id(params)
        if seq_id:
            ids.add(seq_id)
    return ids


def get_device_visible_dm_sequences(
    db: Session,
    device_id: Optional[str],
    extra_sequence_ids: Iterable[str] | None = None,
) -> list[DMSequence]:
    """Return shared/user-scoped DM sequences plus sequences referenced by this device's tasks."""
    requested_ids = _task_sequence_ids_for_device(db, device_id)
    if extra_sequence_ids:
        requested_ids.update(str(seq_id) for seq_id in extra_sequence_ids if seq_id)

    query = db.query(DMSequence)
    if not device_id:
        # No authenticated device — only return shared (non-user-scoped) sequences
        return query.filter(DMSequence.user_id.is_(None)).all()

    device = db.query(Device).filter(Device.id == device_id).first()
    device_user_id = device.user_id if device else None

    visibility = [DMSequence.user_id.is_(None)]
    if device_user_id:
        visibility.append(DMSequence.user_id == device_user_id)
    if requested_ids:
        visibility.append(DMSequence.id.in_(requested_ids))

    return query.filter(or_(*visibility)).all()
