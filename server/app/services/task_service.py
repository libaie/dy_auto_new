from datetime import datetime
from typing import Optional

from app.models import Task, TaskType, TaskStatus

MAX_RETRIES = 3


class TaskService:
    """MVP task scheduling service -- in-memory storage, single-device mode"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def create_task(
        self,
        task_type: TaskType,
        account_id: str,
        params: dict,
        scheduled_at: Optional[datetime] = None,
    ) -> Task:
        task = Task(
            type=task_type,
            account_id=account_id,
            params=params,
            scheduled_at=scheduled_at,
        )
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_pending_task(self, device_id: str) -> Optional[Task]:
        """Claim a pending task (optimistic lock: atomic status update)"""
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.RUNNING
                task.device_id = device_id
                task.started_at = datetime.now()
                return task
        return None

    def report_result(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        ui_snapshot: Optional[dict] = None,
    ) -> Task:
        task = self._tasks[task_id]
        if status == TaskStatus.COMPLETED:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
        elif status == TaskStatus.FAILED:
            task.retry_count += 1
            if task.retry_count >= MAX_RETRIES:
                task.status = TaskStatus.FAILED
                task.result = result
                task.completed_at = datetime.now()
            else:
                task.status = TaskStatus.PENDING  # re-queue for retry
                task.device_id = ""
                task.started_at = None
        return task

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks


# Module-level singleton -- shared by device API and task management API
task_service = TaskService()
