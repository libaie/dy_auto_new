"""Task scheduling service — backed by SQLAlchemy database."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update

from app.db_models import Task as DBTask
from app.models import TaskType, TaskStatus, Task as PydanticTask

MAX_RETRIES = 3


def _db_task_to_pydantic(task: DBTask) -> PydanticTask:
    """Convert SQLAlchemy Task to Pydantic Task for API responses."""
    return PydanticTask(
        id=task.id,
        type=TaskType(task.type),
        account_id=task.account_id,
        device_id=task.device_id or "",
        params=task.params or {},
        status=TaskStatus(task.status),
        scheduled_at=task.scheduled_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        result=task.result,
        retry_count=task.retry_count,
    )


class TaskService:
    """Task scheduling service — DB-backed."""

    def create_task(
        self,
        db: Session,
        task_type: TaskType,
        account_id: str,
        params: dict,
        scheduled_at: Optional[datetime] = None,
    ) -> PydanticTask:
        db_task = DBTask(
            type=task_type.value,
            account_id=account_id,
            params=params,
            status=TaskStatus.PENDING.value,
            scheduled_at=scheduled_at,
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def get_task(self, db: Session, task_id: str) -> Optional[PydanticTask]:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            return None
        return _db_task_to_pydantic(db_task)

    def get_pending_task(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Claim a pending task using optimistic locking (UPDATE ... WHERE status='pending')."""
        # Find oldest pending task
        db_task = db.query(DBTask).filter(
            DBTask.status == TaskStatus.PENDING.value,
        ).order_by(DBTask.created_at.asc()).first()

        if not db_task:
            return None

        # Optimistic lock: atomically claim via UPDATE with WHERE clause
        result = db.execute(
            update(DBTask)
            .where(DBTask.id == db_task.id, DBTask.status == TaskStatus.PENDING.value)
            .values(status=TaskStatus.RUNNING.value, device_id=device_id, started_at=datetime.now())
        )
        db.commit()

        if result.rowcount == 0:
            # Another device claimed it first — retry
            return self.get_pending_task(db, device_id)

        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def report_result(
        self,
        db: Session,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        ui_snapshot: Optional[dict] = None,
    ) -> PydanticTask:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            raise ValueError(f"Task {task_id} not found")

        if status == TaskStatus.COMPLETED:
            db_task.status = TaskStatus.COMPLETED.value
            db_task.result = result
            db_task.completed_at = datetime.now()
        elif status == TaskStatus.FAILED:
            db_task.retry_count += 1
            if db_task.retry_count >= MAX_RETRIES:
                db_task.status = TaskStatus.FAILED.value
                db_task.result = result
                db_task.completed_at = datetime.now()
            else:
                db_task.status = TaskStatus.PENDING.value  # re-queue for retry
                db_task.device_id = None
                db_task.started_at = None

        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def list_tasks(self, db: Session, status: Optional[TaskStatus] = None, skip: int = 0, limit: int = 50) -> list[PydanticTask]:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == status.value)
        db_tasks = query.order_by(DBTask.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_task_to_pydantic(t) for t in db_tasks]

    def count_tasks(self, db: Session, status: Optional[TaskStatus] = None) -> int:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == status.value)
        return query.count()


# Module-level singleton — services are stateless, DB sessions come from get_db
task_service = TaskService()
