"""Chain service unit tests."""
import pytest
from app.db.models import (
    Account, ChainTemplate, ChainInstance, Task as DBTask,
    AccountGroup, AccountGroupMember,
)
from app.domains.account_operations.chain_service import chain_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_account(db, acc_id, status="active"):
    existing = db.query(Account).filter(Account.id == acc_id).first()
    if existing:
        return existing
    acc = Account(id=acc_id, nickname=acc_id, status=status, daily_limits={
        "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
    })
    db.add(acc)
    db.commit()
    return acc


def _make_template(db, name="svc-tpl", steps=None):
    if steps is None:
        steps = [{"step_order": 1, "type": "nurture", "params": {"duration": 10}}]
    tpl = ChainTemplate(name=name, steps=steps)
    db.add(tpl)
    db.commit()
    return tpl


# ---------------------------------------------------------------------------
# TestIsAccountBusy
# ---------------------------------------------------------------------------

class TestIsAccountBusy:
    def test_busy_with_pending_task(self, db):
        acc = _make_account(db, "cs-busy-pending")
        task = DBTask(type="nurture", account_id=acc.id, status="pending")
        db.add(task)
        db.commit()
        assert chain_service.is_account_busy(db, acc.id) is True

    def test_busy_with_running_task(self, db):
        acc = _make_account(db, "cs-busy-running")
        task = DBTask(type="nurture", account_id=acc.id, status="running")
        db.add(task)
        db.commit()
        assert chain_service.is_account_busy(db, acc.id) is True

    def test_not_busy_with_completed_task(self, db):
        acc = _make_account(db, "cs-not-busy-completed")
        task = DBTask(type="nurture", account_id=acc.id, status="completed")
        db.add(task)
        db.commit()
        assert chain_service.is_account_busy(db, acc.id) is False

    def test_not_busy_no_tasks(self, db):
        acc = _make_account(db, "cs-not-busy-no-tasks")
        assert chain_service.is_account_busy(db, acc.id) is False


# ---------------------------------------------------------------------------
# TestCreateChainInstances
# ---------------------------------------------------------------------------

class TestCreateChainInstances:
    def test_create_single_instance(self, db):
        acc = _make_account(db, "cs-create-single")
        tpl = _make_template(db, name="cs-tpl-single")
        results = chain_service.create_chain_instances(db, tpl.id, [acc.id])
        assert acc.id in results["created"]
        assert len(results["skipped_busy"]) == 0
        assert len(results["skipped_error"]) == 0
        instance = db.query(ChainInstance).filter(
            ChainInstance.template_id == tpl.id,
            ChainInstance.account_id == acc.id,
        ).first()
        assert instance is not None
        assert instance.status == "running"

    def test_skip_busy_account(self, db):
        acc = _make_account(db, "cs-skip-busy")
        task = DBTask(type="nurture", account_id=acc.id, status="pending")
        db.add(task)
        db.commit()
        tpl = _make_template(db, name="cs-tpl-busy")
        results = chain_service.create_chain_instances(db, tpl.id, [acc.id])
        assert acc.id in results["skipped_busy"]
        assert len(results["created"]) == 0

    def test_skip_invalid_account(self, db):
        tpl = _make_template(db, name="cs-tpl-invalid")
        results = chain_service.create_chain_instances(db, tpl.id, ["nonexistent-acc"])
        assert "nonexistent-acc" in results["skipped_error"]
        assert len(results["created"]) == 0

    def test_nonexistent_template(self, db):
        _make_account(db, "cs-no-tpl")
        with pytest.raises(ValueError, match="模板不存在"):
            chain_service.create_chain_instances(db, "nonexistent-tpl", ["cs-no-tpl"])

    def test_mixed_results(self, db):
        valid_acc = _make_account(db, "cs-mixed-valid")
        busy_acc = _make_account(db, "cs-mixed-busy")
        task = DBTask(type="nurture", account_id=busy_acc.id, status="pending")
        db.add(task)
        db.commit()
        tpl = _make_template(db, name="cs-tpl-mixed")
        results = chain_service.create_chain_instances(
            db, tpl.id, [valid_acc.id, busy_acc.id, "nonexistent-acc"]
        )
        assert len(results["created"]) == 1
        assert len(results["skipped_busy"]) == 1
        assert len(results["skipped_error"]) == 1
        assert valid_acc.id in results["created"]
        assert busy_acc.id in results["skipped_busy"]
        assert "nonexistent-acc" in results["skipped_error"]

    def test_invalid_step_type_in_template(self, db):
        acc = _make_account(db, "cs-bad-type")
        tpl = _make_template(db, name="cs-tpl-bad-type", steps=[
            {"step_order": 1, "type": "invalid_type", "params": {}},
        ])
        with pytest.raises(ValueError, match="无效的步骤类型"):
            chain_service.create_chain_instances(db, tpl.id, [acc.id])

    def test_multi_step_template(self, db):
        acc = _make_account(db, "cs-multi-step")
        tpl = _make_template(db, name="cs-tpl-multi", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 10}},
            {"step_order": 2, "type": "search_comment", "params": {"keyword": "test"}},
        ])
        results = chain_service.create_chain_instances(db, tpl.id, [acc.id])
        assert acc.id in results["created"]
        instance = db.query(ChainInstance).filter(
            ChainInstance.template_id == tpl.id,
            ChainInstance.account_id == acc.id,
        ).first()
        assert instance is not None
        assert instance.status == "running"
        assert instance.current_step == 1
        assert instance.total_steps == 2
        task = db.query(DBTask).filter(
            DBTask.chain_instance_id == instance.id,
        ).first()
        assert task is not None
        assert task.step_order == 1
        assert task.status == "pending"


# ---------------------------------------------------------------------------
# TestResolveAccountsFromGroups
# ---------------------------------------------------------------------------

class TestResolveAccountsFromGroups:
    def test_resolve_single_group(self, db):
        acc = _make_account(db, "cs-resolve-single")
        group = AccountGroup(name="cs-grp-single")
        db.add(group)
        db.flush()
        member = AccountGroupMember(group_id=group.id, account_id=acc.id)
        db.add(member)
        db.commit()
        result = chain_service.resolve_accounts_from_groups(db, [group.id])
        assert acc.id in result

    def test_resolve_deduplicates(self, db):
        acc = _make_account(db, "cs-resolve-dedup")
        grp1 = AccountGroup(name="cs-grp-dedup1")
        grp2 = AccountGroup(name="cs-grp-dedup2")
        db.add_all([grp1, grp2])
        db.flush()
        db.add(AccountGroupMember(group_id=grp1.id, account_id=acc.id))
        db.add(AccountGroupMember(group_id=grp2.id, account_id=acc.id))
        db.commit()
        result = chain_service.resolve_accounts_from_groups(db, [grp1.id, grp2.id])
        assert result.count(acc.id) == 1

    def test_resolve_only_active(self, db):
        active_acc = _make_account(db, "cs-resolve-active", status="active")
        banned_acc = _make_account(db, "cs-resolve-banned", status="banned")
        group = AccountGroup(name="cs-grp-active")
        db.add(group)
        db.flush()
        db.add(AccountGroupMember(group_id=group.id, account_id=active_acc.id))
        db.add(AccountGroupMember(group_id=group.id, account_id=banned_acc.id))
        db.commit()
        result = chain_service.resolve_accounts_from_groups(db, [group.id])
        assert active_acc.id in result
        assert banned_acc.id not in result

    def test_resolve_empty_groups(self, db):
        result = chain_service.resolve_accounts_from_groups(db, ["nonexistent-group"])
        assert result == []


# ---------------------------------------------------------------------------
# TestAdvanceChain
# ---------------------------------------------------------------------------

class TestAdvanceChain:
    def test_advance_to_next_step(self, db):
        acc = _make_account(db, "cs-advance-next")
        tpl = _make_template(db, name="cs-tpl-advance", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 10}},
            {"step_order": 2, "type": "search_comment", "params": {"keyword": "test"}},
        ])
        chain_service.create_chain_instances(db, tpl.id, [acc.id])
        instance = db.query(ChainInstance).filter(
            ChainInstance.template_id == tpl.id,
            ChainInstance.account_id == acc.id,
        ).first()
        step1_task = db.query(DBTask).filter(
            DBTask.chain_instance_id == instance.id,
            DBTask.step_order == 1,
        ).first()
        chain_service.advance_chain(db, step1_task.id, "completed", {"success_count": 1})
        db.commit()
        db.refresh(instance)
        assert instance.current_step == 2
        assert instance.status == "running"
        step2_task = db.query(DBTask).filter(
            DBTask.chain_instance_id == instance.id,
            DBTask.step_order == 2,
        ).first()
        assert step2_task is not None
        assert step2_task.status == "pending"

    def test_advance_completes_chain(self, db):
        acc = _make_account(db, "cs-advance-complete")
        tpl = _make_template(db, name="cs-tpl-complete", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 10}},
        ])
        chain_service.create_chain_instances(db, tpl.id, [acc.id])
        instance = db.query(ChainInstance).filter(
            ChainInstance.template_id == tpl.id,
            ChainInstance.account_id == acc.id,
        ).first()
        task = db.query(DBTask).filter(
            DBTask.chain_instance_id == instance.id,
            DBTask.step_order == 1,
        ).first()
        chain_service.advance_chain(db, task.id, "completed", {"success_count": 1})
        db.commit()
        db.refresh(instance)
        assert instance.status == "completed"
        assert instance.completed_at is not None

    def test_advance_marks_failure(self, db):
        acc = _make_account(db, "cs-advance-fail")
        tpl = _make_template(db, name="cs-tpl-fail", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 10}},
        ])
        chain_service.create_chain_instances(db, tpl.id, [acc.id])
        instance = db.query(ChainInstance).filter(
            ChainInstance.template_id == tpl.id,
            ChainInstance.account_id == acc.id,
        ).first()
        task = db.query(DBTask).filter(
            DBTask.chain_instance_id == instance.id,
            DBTask.step_order == 1,
        ).first()
        chain_service.advance_chain(db, task.id, "failed", {"error": "something went wrong"})
        db.commit()
        db.refresh(instance)
        assert instance.status == "failed"
        assert instance.completed_at is not None

    def test_advance_non_chain_task_is_noop(self, db):
        acc = _make_account(db, "cs-advance-noop")
        task = DBTask(type="nurture", account_id=acc.id, status="pending")
        db.add(task)
        db.commit()
        chain_service.advance_chain(db, task.id, "completed")
        db.commit()
        db.refresh(task)
        assert task.status == "pending"

    def test_advance_nonexistent_task_is_noop(self, db):
        chain_service.advance_chain(db, "nonexistent-task-id", "completed")
        db.commit()


# ---------------------------------------------------------------------------
# TestCreateStepTask
# ---------------------------------------------------------------------------

class TestCreateStepTask:
    def test_invalid_step_type_raises(self, db):
        acc = _make_account(db, "cs-step-bad-type")
        tpl = _make_template(db, name="cs-tpl-step-bad", steps=[
            {"step_order": 1, "type": "invalid_type", "params": {}},
        ])
        instance = ChainInstance(
            template_id=tpl.id, account_id=acc.id,
            current_step=1, total_steps=1, status="running",
        )
        db.add(instance)
        db.flush()
        with pytest.raises(ValueError, match="无效的步骤类型"):
            chain_service._create_step_task(db, instance, 1, tpl)

    def test_missing_step_order_raises(self, db):
        acc = _make_account(db, "cs-step-missing")
        tpl = _make_template(db, name="cs-tpl-step-missing", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 10}},
        ])
        instance = ChainInstance(
            template_id=tpl.id, account_id=acc.id,
            current_step=1, total_steps=1, status="running",
        )
        db.add(instance)
        db.flush()
        with pytest.raises(ValueError, match="Step 5 not found"):
            chain_service._create_step_task(db, instance, 5, tpl)
