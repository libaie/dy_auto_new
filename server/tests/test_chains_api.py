"""Chain template and instance API tests."""
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from app.main import app
from app.db_models import Account, ChainInstance, Task as DBTask

client = TestClient(app)


# ── helpers ──────────────────────────────────────────────────────────────────


def _create_test_account(db, acc_id, nickname="test", status="active"):
    existing = db.query(Account).filter(Account.id == acc_id).first()
    if existing:
        return existing
    account = Account(
        id=acc_id,
        nickname=nickname,
        status=status,
        daily_limits={
            "likes": 50,
            "comments": 20,
            "follows": 20,
            "dms": 10,
            "replies": 15,
        },
    )
    db.add(account)
    db.commit()
    return account


def _create_test_template(name="test-tpl", steps=None):
    if steps is None:
        steps = [
            {"step_order": 1, "type": "nurture", "label": "养号", "params": {"duration": 15}}
        ]
    resp = client.post(
        "/api/chains/templates", json={"name": name, "steps": steps}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _get_instance_id(db, acc_id):
    """Get the chain instance ID for a given account.

    The create-instances API returns account IDs in ``created``, not instance
    IDs.  This helper queries the DB directly.  We call ``db.rollback()``
    first to clear any stale transaction snapshot so the query sees data
    committed by the API sessions (which share the same StaticPool connection).
    """
    db.rollback()
    inst = (
        db.query(ChainInstance)
        .filter(ChainInstance.account_id == acc_id)
        .order_by(ChainInstance.created_at.desc())
        .first()
    )
    assert inst is not None, f"No chain instance found for account {acc_id}"
    return inst.id


# ── constants ────────────────────────────────────────────────────────────────


VALID_STEPS = [
    {"step_order": 1, "type": "nurture", "label": "养号", "params": {"duration": 30}},
    {
        "step_order": 2,
        "type": "search_comment",
        "label": "搜索评论",
        "params": {"keyword": "美食", "count": 3},
    },
]
VALID_STEPS_SINGLE = [
    {"step_order": 1, "type": "nurture", "label": "养号", "params": {"duration": 15}},
]


# ═════════════════════════════════════════════════════════════════════════════
# TestChainTemplateCRUD
# ═════════════════════════════════════════════════════════════════════════════


class TestChainTemplateCRUD:
    """Chain template CRUD endpoint tests."""

    def test_create_template(self):
        uid = uuid.uuid4().hex[:8]
        resp = client.post(
            "/api/chains/templates",
            json={"name": f"tpl-create-{uid}", "steps": VALID_STEPS},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"tpl-create-{uid}"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["step_order"] == 1
        assert data["steps"][1]["type"] == "search_comment"
        assert "id" in data

    def test_create_template_step_order_validation(self):
        """Steps with gap (1, 3) should return 422."""
        uid = uuid.uuid4().hex[:8]
        bad_steps = [
            {"step_order": 1, "type": "nurture", "label": "养号", "params": {"duration": 15}},
            {"step_order": 3, "type": "nurture", "label": "养号2", "params": {"duration": 15}},
        ]
        resp = client.post(
            "/api/chains/templates",
            json={"name": f"tpl-gap-{uid}", "steps": bad_steps},
        )
        assert resp.status_code == 422

    def test_create_template_no_steps(self):
        """Empty steps list should return 422 (Pydantic min_length=1)."""
        uid = uuid.uuid4().hex[:8]
        resp = client.post(
            "/api/chains/templates",
            json={"name": f"tpl-nosteps-{uid}", "steps": []},
        )
        assert resp.status_code == 422

    def test_list_templates(self):
        resp = client.get("/api/chains/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "total" in data
        assert isinstance(data["templates"], list)

    def test_get_template(self):
        uid = uuid.uuid4().hex[:8]
        tpl_id = _create_test_template(f"tpl-get-{uid}", VALID_STEPS_SINGLE)
        resp = client.get(f"/api/chains/templates/{tpl_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tpl_id
        assert data["name"] == f"tpl-get-{uid}"
        assert len(data["steps"]) == 1

    def test_get_nonexistent_template(self):
        resp = client.get("/api/chains/templates/nonexistent-id-999")
        assert resp.status_code == 404

    def test_update_template_name(self):
        uid = uuid.uuid4().hex[:8]
        tpl_id = _create_test_template(f"tpl-updname-{uid}", VALID_STEPS_SINGLE)
        resp = client.put(
            f"/api/chains/templates/{tpl_id}",
            json={"name": f"tpl-updname-new-{uid}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"tpl-updname-new-{uid}"

    def test_update_template_steps(self):
        uid = uuid.uuid4().hex[:8]
        tpl_id = _create_test_template(f"tpl-updsteps-{uid}", VALID_STEPS_SINGLE)
        new_steps = [
            {"step_order": 1, "type": "nurture", "label": "新养号", "params": {"duration": 45}},
            {
                "step_order": 2,
                "type": "search_like",
                "label": "搜索点赞",
                "params": {"keyword": "测试", "count": 5},
            },
        ]
        resp = client.put(
            f"/api/chains/templates/{tpl_id}",
            json={"steps": new_steps},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["steps"]) == 2
        assert data["steps"][0]["label"] == "新养号"

    def test_update_nonexistent_template(self):
        resp = client.put(
            "/api/chains/templates/nonexistent-id-999",
            json={"name": "nope"},
        )
        assert resp.status_code == 404

    def test_delete_template(self):
        uid = uuid.uuid4().hex[:8]
        tpl_id = _create_test_template(f"tpl-del-{uid}", VALID_STEPS_SINGLE)
        resp = client.delete(f"/api/chains/templates/{tpl_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        # Verify gone
        resp2 = client.get(f"/api/chains/templates/{tpl_id}")
        assert resp2.status_code == 404

    def test_delete_nonexistent_template(self):
        resp = client.delete("/api/chains/templates/nonexistent-id-999")
        assert resp.status_code == 404

    def test_template_step_type_validation(self):
        """Invalid step type should return 422 (Pydantic TaskType enum)."""
        uid = uuid.uuid4().hex[:8]
        bad_steps = [
            {"step_order": 1, "type": "invalid_type_xyz", "label": "bad", "params": {}},
        ]
        resp = client.post(
            "/api/chains/templates",
            json={"name": f"tpl-badtype-{uid}", "steps": bad_steps},
        )
        assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# TestChainInstanceLifecycle
# ═════════════════════════════════════════════════════════════════════════════


class TestChainInstanceLifecycle:
    """Chain instance lifecycle endpoint tests."""

    def test_create_instances_success(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-inst-ok-{uid}"
        _create_test_account(db, acc_id, nickname=f"inst-ok-{uid}")
        tpl_id = _create_test_template(f"tpl-inst-ok-{uid}", VALID_STEPS_SINGLE)
        resp = client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_count"] == 1
        assert data["skipped_busy_count"] == 0
        assert acc_id in data["created"]

    def test_create_instances_skip_busy(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-busy-{uid}"
        _create_test_account(db, acc_id, nickname=f"busy-{uid}")
        tpl_id = _create_test_template(f"tpl-busy-{uid}", VALID_STEPS_SINGLE)
        # First creation — should succeed
        resp1 = client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        assert resp1.status_code == 200
        assert resp1.json()["created_count"] == 1
        # Second creation — account is busy now
        resp2 = client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        assert resp2.status_code == 200
        assert resp2.json()["skipped_busy_count"] == 1
        assert acc_id in resp2.json()["skipped_busy"]

    def test_create_instances_skip_invalid_account(self, db):
        uid = uuid.uuid4().hex[:8]
        tpl_id = _create_test_template(f"tpl-invacc-{uid}", VALID_STEPS_SINGLE)
        resp = client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": ["nonexistent-acc-999"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["skipped_error_count"] == 1
        assert "nonexistent-acc-999" in data["skipped_error"]

    def test_create_instances_nonexistent_template(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-notpl-{uid}"
        _create_test_account(db, acc_id, nickname=f"notpl-{uid}")
        resp = client.post(
            "/api/chains/instances",
            json={"template_id": "nonexistent-tpl-999", "account_ids": [acc_id]},
        )
        assert resp.status_code == 404

    def test_create_instances_no_accounts(self, db):
        uid = uuid.uuid4().hex[:8]
        tpl_id = _create_test_template(f"tpl-noacc-{uid}", VALID_STEPS_SINGLE)
        resp = client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": []},
        )
        assert resp.status_code == 422

    def test_create_instances_from_groups(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-grp-{uid}"
        _create_test_account(db, acc_id, nickname=f"grp-{uid}")
        tpl_id = _create_test_template(f"tpl-grp-{uid}", VALID_STEPS_SINGLE)
        # Create group
        grp_resp = client.post(
            "/api/account-groups",
            json={"name": f"test-group-{uid}", "description": "test"},
        )
        assert grp_resp.status_code == 200
        group_id = grp_resp.json()["id"]
        # Add member
        add_resp = client.post(
            f"/api/account-groups/{group_id}/members",
            json={"account_ids": [acc_id]},
        )
        assert add_resp.status_code == 200
        # Create instances via group_ids
        resp = client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "group_ids": [group_id]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_count"] == 1
        assert acc_id in data["created"]

    def test_list_instances(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-lstinst-{uid}"
        _create_test_account(db, acc_id, nickname=f"lstinst-{uid}")
        tpl_id = _create_test_template(f"tpl-lstinst-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        resp = client.get("/api/chains/instances")
        assert resp.status_code == 200
        data = resp.json()
        assert "instances" in data
        assert "total" in data
        assert isinstance(data["instances"], list)

    def test_list_instances_filter_by_status(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-fltst-{uid}"
        _create_test_account(db, acc_id, nickname=f"fltst-{uid}")
        tpl_id = _create_test_template(f"tpl-fltst-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        resp = client.get("/api/chains/instances", params={"status": "running"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["instances"], list)
        # All returned instances should be running
        for inst in data["instances"]:
            assert inst["status"] == "running"

    def test_get_instance_detail(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-det-{uid}"
        _create_test_account(db, acc_id, nickname=f"det-{uid}")
        tpl_id = _create_test_template(f"tpl-det-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        inst_id = _get_instance_id(db, acc_id)
        resp = client.get(f"/api/chains/instances/{inst_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == inst_id
        assert data["account_id"] == acc_id
        assert "tasks" in data
        assert len(data["tasks"]) >= 1

    def test_get_nonexistent_instance(self):
        resp = client.get("/api/chains/instances/nonexistent-inst-999")
        assert resp.status_code == 404

    def test_cancel_instance(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-cancel-{uid}"
        _create_test_account(db, acc_id, nickname=f"cancel-{uid}")
        tpl_id = _create_test_template(f"tpl-cancel-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        inst_id = _get_instance_id(db, acc_id)
        resp = client.post(f"/api/chains/instances/{inst_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        # Verify via detail
        detail = client.get(f"/api/chains/instances/{inst_id}")
        assert detail.json()["status"] == "cancelled"

    def test_cancel_already_completed_instance(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-cnlc-{uid}"
        _create_test_account(db, acc_id, nickname=f"cnlc-{uid}")
        tpl_id = _create_test_template(f"tpl-cnlc-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        inst_id = _get_instance_id(db, acc_id)
        # Manually set to completed
        inst = db.query(ChainInstance).filter(ChainInstance.id == inst_id).first()
        inst.status = "completed"
        db.commit()
        resp = client.post(f"/api/chains/instances/{inst_id}/cancel")
        assert resp.status_code == 400

    def test_cancel_nonexistent_instance(self):
        resp = client.post("/api/chains/instances/nonexistent-inst-999/cancel")
        assert resp.status_code == 404

    def test_retry_failed_instance(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-retry-{uid}"
        _create_test_account(db, acc_id, nickname=f"retry-{uid}")
        tpl_id = _create_test_template(f"tpl-retry-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        inst_id = _get_instance_id(db, acc_id)
        # Get task from detail
        detail = client.get(f"/api/chains/instances/{inst_id}")
        task_id = detail.json()["tasks"][0]["id"]
        # Manually set task and instance to failed
        db.rollback()  # refresh session view
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        task.status = "failed"
        task.completed_at = datetime.now(timezone.utc)
        inst = db.query(ChainInstance).filter(ChainInstance.id == inst_id).first()
        inst.status = "failed"
        db.commit()
        # Retry
        resp = client.post(f"/api/chains/instances/{inst_id}/retry")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "retrying"
        assert data["id"] == inst_id

    def test_retry_non_failed_instance(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-rnf-{uid}"
        _create_test_account(db, acc_id, nickname=f"rnf-{uid}")
        tpl_id = _create_test_template(f"tpl-rnf-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        inst_id = _get_instance_id(db, acc_id)
        # Instance is running, not failed
        resp = client.post(f"/api/chains/instances/{inst_id}/retry")
        assert resp.status_code == 400

    def test_delete_template_blocked_by_active_instances(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-dtblk-{uid}"
        _create_test_account(db, acc_id, nickname=f"dtblk-{uid}")
        tpl_id = _create_test_template(f"tpl-dtblk-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        resp = client.delete(f"/api/chains/templates/{tpl_id}")
        assert resp.status_code == 400
        assert "活跃实例" in resp.json()["detail"]

    def test_update_template_steps_blocked_by_active_instances(self, db):
        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-stblk-{uid}"
        _create_test_account(db, acc_id, nickname=f"stblk-{uid}")
        tpl_id = _create_test_template(f"tpl-stblk-{uid}", VALID_STEPS_SINGLE)
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        new_steps = [
            {"step_order": 1, "type": "nurture", "label": "更新", "params": {"duration": 60}},
        ]
        resp = client.put(
            f"/api/chains/templates/{tpl_id}",
            json={"steps": new_steps},
        )
        assert resp.status_code == 400
        assert "活跃实例" in resp.json()["detail"]

    def test_instance_state_transitions(self, db):
        """Full lifecycle: create -> running -> task complete -> chain completed."""
        from app.services.task_service import task_service
        from app.models import TaskStatus

        uid = uuid.uuid4().hex[:8]
        acc_id = f"acc-lifecycle-{uid}"
        _create_test_account(db, acc_id, nickname=f"lifecycle-{uid}")
        tpl_id = _create_test_template(
            f"tpl-lifecycle-{uid}", VALID_STEPS_SINGLE
        )
        client.post(
            "/api/chains/instances",
            json={"template_id": tpl_id, "account_ids": [acc_id]},
        )
        inst_id = _get_instance_id(db, acc_id)
        # Should be running (single step)
        detail = client.get(f"/api/chains/instances/{inst_id}")
        assert detail.json()["status"] == "running"
        task_id = detail.json()["tasks"][0]["id"]
        # Report task completion — should advance chain to completed
        db.rollback()  # refresh session to see the task
        task_service.report_result(db, task_id, TaskStatus.COMPLETED, {"success_count": 1})
        detail2 = client.get(f"/api/chains/instances/{inst_id}")
        assert detail2.json()["status"] == "completed"
