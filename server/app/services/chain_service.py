"""Chain orchestration service — step-by-step task release."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import (
    ChainTemplate, ChainInstance, Task as DBTask, Device, Account,
    AccountGroupMember,
)


class ChainService:
    def is_account_busy(self, db: Session, account_id: str) -> bool:
        """Check if account has pending or running tasks."""
        count = db.query(DBTask).filter(
            DBTask.account_id == account_id,
            DBTask.status.in_(["pending", "running"]),
        ).count()
        return count > 0

    def create_chain_instances(
        self,
        db: Session,
        template_id: str,
        account_ids: list[str],
    ) -> dict:
        """Create chain instances for each account, skipping busy ones."""
        template = db.query(ChainTemplate).filter(ChainTemplate.id == template_id).first()
        if not template:
            raise ValueError("模板不存在")

        total_steps = len(template.steps)
        results = {"created": [], "skipped_busy": [], "skipped_error": []}

        for account_id in account_ids:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                results["skipped_error"].append(account_id)
                continue

            if self.is_account_busy(db, account_id):
                results["skipped_busy"].append(account_id)
                continue

            instance = ChainInstance(
                template_id=template_id,
                account_id=account_id,
                current_step=1,
                total_steps=total_steps,
                status="pending",
            )
            db.add(instance)
            db.flush()

            self._create_step_task(db, instance, 1, template)
            instance.status = "running"
            instance.started_at = datetime.now(timezone.utc)
            results["created"].append(account_id)

        db.commit()

        self._push_pending_tasks(db, results["created"])

        return results

    def resolve_accounts_from_groups(self, db: Session, group_ids: list[str]) -> list[str]:
        """Expand group IDs to unique active account IDs."""
        account_ids = (
            db.query(AccountGroupMember.account_id)
            .join(Account, Account.id == AccountGroupMember.account_id)
            .filter(
                AccountGroupMember.group_id.in_(group_ids),
                Account.status == "active",
            )
            .distinct()
            .all()
        )
        return [a[0] for a in account_ids]

    def advance_chain(self, db: Session, task_id: str, status: str, result: dict = None):
        """Advance chain to next step after task completion/failure."""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task or not task.chain_instance_id:
            return

        chain = db.query(ChainInstance).filter(
            ChainInstance.id == task.chain_instance_id
        ).first()
        if not chain:
            return

        if status == "completed":
            next_step = task.step_order + 1
            if next_step > chain.total_steps:
                chain.status = "completed"
                chain.completed_at = datetime.now(timezone.utc)
            else:
                chain.current_step = next_step
                chain.status = "running"
                if not chain.started_at:
                    chain.started_at = datetime.now(timezone.utc)
                template = db.query(ChainTemplate).filter(ChainTemplate.id == chain.template_id).first()
                if template:
                    self._create_step_task(db, chain, next_step, template)
                    db.flush()
                    self._push_step_task(db, chain)
        elif status == "failed":
            chain.status = "failed"
            chain.completed_at = datetime.now(timezone.utc)

    def _create_step_task(self, db: Session, chain: ChainInstance, step_order: int, template: ChainTemplate):
        """Create a Task for the given step. Caller is responsible for commit/flush."""
        step = next((s for s in template.steps if s["step_order"] == step_order), None)
        if not step:
            raise ValueError(f"Step {step_order} not found in template")

        task = DBTask(
            type=step["type"],
            account_id=chain.account_id,
            params=step.get("params", {}),
            status="pending",
            chain_instance_id=chain.id,
            step_order=step_order,
        )
        db.add(task)

    def _push_pending_tasks(self, db: Session, account_ids: list[str]):
        """Push pending tasks for chain instances to bound devices."""
        from app.ws_manager import pair_ws_manager
        import asyncio

        for account_id in account_ids:
            device = db.query(Device).filter(Device.bound_account_id == account_id).first()
            if not device:
                continue
            task = (
                db.query(DBTask)
                .filter(DBTask.account_id == account_id, DBTask.status == "pending", DBTask.chain_instance_id.isnot(None))
                .order_by(DBTask.created_at.desc())
                .first()
            )
            if task:
                asyncio.ensure_future(pair_ws_manager.send_to_device(device.id, {
                    "event": "task",
                    "task": _task_to_push_dict(task),
                }))

    def _push_step_task(self, db: Session, chain: ChainInstance):
        """Push the current step task to the bound device."""
        from app.ws_manager import pair_ws_manager
        import asyncio

        device = db.query(Device).filter(Device.bound_account_id == chain.account_id).first()
        if not device:
            return
        task = (
            db.query(DBTask)
            .filter(DBTask.chain_instance_id == chain.id, DBTask.status == "pending")
            .order_by(DBTask.step_order.desc())
            .first()
        )
        if task:
            asyncio.ensure_future(pair_ws_manager.send_to_device(device.id, {
                "event": "task",
                "task": _task_to_push_dict(task),
            }))


def _task_to_push_dict(task: DBTask) -> dict:
    return {
        "id": task.id,
        "type": task.type,
        "account_id": task.account_id,
        "device_id": task.device_id or "",
        "params": task.params or {},
        "status": task.status,
        "chain_instance_id": task.chain_instance_id,
        "step_order": task.step_order,
    }


chain_service = ChainService()
