# 账号分组 + 任务链 测试覆盖实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已实现的账号分组、任务链编排、养号 V2 功能补充完整的测试覆盖，确保业务连贯性和状态扭转一致性

**Architecture:** 所有功能代码已实现（db_models, routers, services, frontend）。本计划补充 3 个测试文件 + 1 个增强测试，覆盖 API 端点、服务层逻辑、状态机转换、跨模块集成。测试遵循现有模式：TestClient + in-memory SQLite + conftest fixtures。

**Tech Stack:** pytest, FastAPI TestClient, SQLAlchemy in-memory SQLite

**Spec:** `docs/superpowers/plans/2026-04-30-account-groups-task-chains.md`

---

## 文件结构

### 新增测试文件
- `server/tests/test_account_groups_api.py` — 账号分组 CRUD + 成员管理 API 测试
- `server/tests/test_chains_api.py` — 链模板 CRUD + 链实例生命周期 API 测试
- `server/tests/test_chain_service.py` — 链服务单元测试（互斥锁、推进逻辑、分组解析）

### 修改测试文件
- `server/tests/test_tasks_api.py` — 补充养号 V2 参数校验测试

---

## Task 1: 账号分组 API 测试

**Files:**
- Create: `server/tests/test_account_groups_api.py`

测试覆盖：
- 分组 CRUD（创建、列表、查询、更新、删除）
- 名称唯一性约束（409 冲突）
- 成员管理（添加、列表、移除）
- 添加不存在的账号（400 校验）
- 删除分组级联删除成员
- 认证要求

- [ ] **Step 1: 创建 test_account_groups_api.py**

```python
"""Account groups CRUD + member management API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestAccountGroupCRUD:
    """Group CRUD operations."""

    def test_create_group(self):
        resp = client.post("/api/account-groups", json={
            "name": "test-group-crud",
            "description": "测试分组",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-group-crud"
        assert data["description"] == "测试分组"
        assert data["member_count"] == 0
        assert "id" in data

    def test_create_group_duplicate_name(self):
        client.post("/api/account-groups", json={"name": "dup-group-test"})
        resp = client.post("/api/account-groups", json={"name": "dup-group-test"})
        assert resp.status_code == 409

    def test_list_groups(self):
        resp = client.get("/api/account-groups")
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_group(self):
        create = client.post("/api/account-groups", json={"name": "get-test-group"})
        group_id = create.json()["id"]

        resp = client.get(f"/api/account-groups/{group_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == group_id

    def test_get_nonexistent_group(self):
        resp = client.get("/api/account-groups/nonexistent")
        assert resp.status_code == 404

    def test_update_group(self):
        create = client.post("/api/account-groups", json={"name": "update-test-group"})
        group_id = create.json()["id"]

        resp = client.put(f"/api/account-groups/{group_id}", json={
            "name": "updated-name",
            "description": "新描述",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-name"
        assert resp.json()["description"] == "新描述"

    def test_update_group_duplicate_name(self):
        client.post("/api/account-groups", json={"name": "update-dup-a"})
        create_b = client.post("/api/account-groups", json={"name": "update-dup-b"})
        group_b_id = create_b.json()["id"]

        resp = client.put(f"/api/account-groups/{group_b_id}", json={"name": "update-dup-a"})
        assert resp.status_code == 409

    def test_update_nonexistent_group(self):
        resp = client.put("/api/account-groups/nonexistent", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_group(self):
        create = client.post("/api/account-groups", json={"name": "delete-test-group"})
        group_id = create.json()["id"]

        resp = client.delete(f"/api/account-groups/{group_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify deleted
        resp = client.get(f"/api/account-groups/{group_id}")
        assert resp.status_code == 404

    def test_delete_nonexistent_group(self):
        resp = client.delete("/api/account-groups/nonexistent")
        assert resp.status_code == 404

    def test_delete_group_cascades_members(self, db):
        """Deleting a group should remove all member associations."""
        from app.db_models import AccountGroup, AccountGroupMember, Account

        # Create account
        account = Account(id="cascade-test-acc", nickname="cascade", daily_limits={})
        db.add(account)
        db.commit()

        # Create group + member
        create = client.post("/api/account-groups", json={"name": "cascade-group"})
        group_id = create.json()["id"]
        client.post(f"/api/account-groups/{group_id}/members", json={"account_ids": ["cascade-test-acc"]})

        # Delete group
        client.delete(f"/api/account-groups/{group_id}")

        # Verify member association is gone
        remaining = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
        assert remaining == 0


class TestAccountGroupMembers:
    """Member management operations."""

    def test_add_members(self, db):
        from app.db_models import Account
        db.add(Account(id="member-add-acc", nickname="member-add", daily_limits={}))
        db.commit()

        create = client.post("/api/account-groups", json={"name": "member-add-group"})
        group_id = create.json()["id"]

        resp = client.post(f"/api/account-groups/{group_id}/members", json={
            "account_ids": ["member-add-acc"],
        })
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        assert "member-add-acc" in resp.json()["added"]

    def test_add_members_idempotent(self, db):
        from app.db_models import Account
        db.add(Account(id="member-idem-acc", nickname="idem", daily_limits={}))
        db.commit()

        create = client.post("/api/account-groups", json={"name": "member-idem-group"})
        group_id = create.json()["id"]

        client.post(f"/api/account-groups/{group_id}/members", json={"account_ids": ["member-idem-acc"]})
        resp = client.post(f"/api/account-groups/{group_id}/members", json={"account_ids": ["member-idem-acc"]})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0  # already exists, not added again

    def test_add_members_nonexistent_account(self):
        create = client.post("/api/account-groups", json={"name": "member-invalid-group"})
        group_id = create.json()["id"]

        resp = client.post(f"/api/account-groups/{group_id}/members", json={
            "account_ids": ["nonexistent-account-id"],
        })
        assert resp.status_code == 400

    def test_list_members(self, db):
        from app.db_models import Account
        db.add(Account(id="member-list-acc", nickname="list-member", daily_limits={}))
        db.commit()

        create = client.post("/api/account-groups", json={"name": "member-list-group"})
        group_id = create.json()["id"]
        client.post(f"/api/account-groups/{group_id}/members", json={"account_ids": ["member-list-acc"]})

        resp = client.get(f"/api/account-groups/{group_id}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["members"][0]["id"] == "member-list-acc"

    def test_list_members_with_status_filter(self, db):
        from app.db_models import Account
        db.add(Account(id="member-status-active", nickname="active", status="active", daily_limits={}))
        db.add(Account(id="member-status-banned", nickname="banned", status="banned", daily_limits={}))
        db.commit()

        create = client.post("/api/account-groups", json={"name": "member-status-group"})
        group_id = create.json()["id"]
        client.post(f"/api/account-groups/{group_id}/members", json={
            "account_ids": ["member-status-active", "member-status-banned"],
        })

        resp = client.get(f"/api/account-groups/{group_id}/members?status=active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["members"][0]["status"] == "active"

    def test_remove_members(self, db):
        from app.db_models import Account
        db.add(Account(id="member-remove-acc", nickname="remove", daily_limits={}))
        db.commit()

        create = client.post("/api/account-groups", json={"name": "member-remove-group"})
        group_id = create.json()["id"]
        client.post(f"/api/account-groups/{group_id}/members", json={"account_ids": ["member-remove-acc"]})

        resp = client.request("DELETE", f"/api/account-groups/{group_id}/members", json={
            "account_ids": ["member-remove-acc"],
        })
        assert resp.status_code == 200
        assert resp.json()["removed"] == 1

        # Verify removed
        resp = client.get(f"/api/account-groups/{group_id}/members")
        assert resp.json()["total"] == 0

    def test_list_members_nonexistent_group(self):
        resp = client.get("/api/account-groups/nonexistent/members")
        assert resp.status_code == 404

    def test_add_members_nonexistent_group(self):
        resp = client.post("/api/account-groups/nonexistent/members", json={"account_ids": ["x"]})
        assert resp.status_code == 404

    def test_auth_required(self):
        from app.deps import verify_admin_token
        app.dependency_overrides.pop(verify_admin_token, None)
        resp = client.get("/api/account-groups")
        assert resp.status_code == 401
        app.dependency_overrides[verify_admin_token] = lambda: "test-user"
```

- [ ] **Step 2: 运行测试验证**

```bash
cd server && python -m pytest tests/test_account_groups_api.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_account_groups_api.py
git commit -m "test: add account groups API test coverage"
```

---

## Task 2: 链模板 API 测试

**Files:**
- Create: `server/tests/test_chains_api.py`（模板部分）

测试覆盖：
- 模板 CRUD（创建、列表、查询、更新、删除）
- 步骤序号连续性校验（422）
- 活跃实例保护（修改步骤/删除模板时阻止）
- 步骤类型合法性校验

- [ ] **Step 1: 创建 test_chains_api.py — 模板测试部分**

```python
"""Chain templates and instances API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import TaskType

client = TestClient(app)

# --- Helper data ---

VALID_STEPS = [
    {"step_order": 1, "type": "nurture", "label": "养号", "params": {"duration": 30}},
    {"step_order": 2, "type": "search_comment", "label": "搜索评论", "params": {"keyword": "美食", "count": 3}},
]

VALID_STEPS_SINGLE = [
    {"step_order": 1, "type": "nurture", "label": "养号", "params": {"duration": 15}},
]


class TestChainTemplateCRUD:
    """Template CRUD operations."""

    def test_create_template(self):
        resp = client.post("/api/chains/templates", json={
            "name": "tpl-create-test",
            "description": "测试模板",
            "steps": VALID_STEPS,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "tpl-create-test"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["step_order"] == 1
        assert data["steps"][1]["step_order"] == 2

    def test_create_template_step_order_validation(self):
        """Steps must be numbered from 1 consecutively."""
        resp = client.post("/api/chains/templates", json={
            "name": "tpl-bad-order",
            "steps": [
                {"step_order": 1, "type": "nurture", "params": {}},
                {"step_order": 3, "type": "nurture", "params": {}},  # gap: missing 2
            ],
        })
        assert resp.status_code == 422

    def test_create_template_no_steps(self):
        resp = client.post("/api/chains/templates", json={
            "name": "tpl-no-steps",
            "steps": [],
        })
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_list_templates(self):
        resp = client.get("/api/chains/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "total" in data

    def test_get_template(self):
        create = client.post("/api/chains/templates", json={
            "name": "tpl-get-test",
            "steps": VALID_STEPS_SINGLE,
        })
        tpl_id = create.json()["id"]

        resp = client.get(f"/api/chains/templates/{tpl_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tpl_id

    def test_get_nonexistent_template(self):
        resp = client.get("/api/chains/templates/nonexistent")
        assert resp.status_code == 404

    def test_update_template_name(self):
        create = client.post("/api/chains/templates", json={
            "name": "tpl-update-name",
            "steps": VALID_STEPS_SINGLE,
        })
        tpl_id = create.json()["id"]

        resp = client.put(f"/api/chains/templates/{tpl_id}", json={"name": "updated-name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-name"

    def test_update_template_steps(self):
        create = client.post("/api/chains/templates", json={
            "name": "tpl-update-steps",
            "steps": VALID_STEPS_SINGLE,
        })
        tpl_id = create.json()["id"]

        new_steps = [
            {"step_order": 1, "type": "search_like", "params": {"keyword": "test", "count": 5}},
        ]
        resp = client.put(f"/api/chains/templates/{tpl_id}", json={"steps": new_steps})
        assert resp.status_code == 200
        assert len(resp.json()["steps"]) == 1
        assert resp.json()["steps"][0]["type"] == "search_like"

    def test_update_nonexistent_template(self):
        resp = client.put("/api/chains/templates/nonexistent", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_template(self):
        create = client.post("/api/chains/templates", json={
            "name": "tpl-delete-test",
            "steps": VALID_STEPS_SINGLE,
        })
        tpl_id = create.json()["id"]

        resp = client.delete(f"/api/chains/templates/{tpl_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = client.get(f"/api/chains/templates/{tpl_id}")
        assert resp.status_code == 404

    def test_delete_nonexistent_template(self):
        resp = client.delete("/api/chains/templates/nonexistent")
        assert resp.status_code == 404

    def test_template_step_type_validation(self):
        """Invalid step types should be rejected."""
        resp = client.post("/api/chains/templates", json={
            "name": "tpl-bad-type",
            "steps": [{"step_order": 1, "type": "invalid_type", "params": {}}],
        })
        assert resp.status_code == 422  # Pydantic TaskType enum validation
```

- [ ] **Step 2: 运行模板测试**

```bash
cd server && python -m pytest tests/test_chains_api.py::TestChainTemplateCRUD -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_chains_api.py
git commit -m "test: add chain template API tests"
```

---

## Task 3: 链实例 API 测试

**Files:**
- Modify: `server/tests/test_chains_api.py`（追加实例测试）

测试覆盖：
- 批量创建实例（成功 + 跳过繁忙 + 跳过无效账号）
- 分组展开创建实例
- 列表实例（筛选、分页）
- 查询实例详情（含步骤任务时间线）
- 取消实例（取消所有 pending/running 任务）
- 重试失败实例
- 状态扭转一致性：pending → running → completed/failed/cancelled
- 活跃实例保护（阻止修改模板步骤/删除模板）

- [ ] **Step 1: 追加链实例测试类到 test_chains_api.py**

```python
from app.db_models import Account, Device, ChainInstance, Task as DBTask


def _create_test_account(db, acc_id, nickname="test", status="active"):
    """Helper to create a test account."""
    existing = db.query(Account).filter(Account.id == acc_id).first()
    if existing:
        return existing
    account = Account(id=acc_id, nickname=nickname, status=status, daily_limits={
        "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
    })
    db.add(account)
    db.commit()
    return account


def _create_test_template(name="test-tpl", steps=None):
    """Helper to create a chain template and return its ID."""
    if steps is None:
        steps = VALID_STEPS_SINGLE
    resp = client.post("/api/chains/templates", json={
        "name": name,
        "steps": steps,
    })
    return resp.json()["id"]


class TestChainInstanceLifecycle:
    """Chain instance creation, listing, detail, cancel, retry."""

    def test_create_instances_success(self, db):
        _create_test_account(db, "chain-acc-001")
        tpl_id = _create_test_template("inst-create-test")

        resp = client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-acc-001"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_count"] == 1
        assert "chain-acc-001" in data["created"]
        assert len(data["skipped_busy"]) == 0

    def test_create_instances_skip_busy(self, db):
        """Accounts with pending/running tasks should be skipped."""
        _create_test_account(db, "chain-busy-acc")
        tpl_id = _create_test_template("inst-busy-test")

        # First creation — should succeed
        resp1 = client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-busy-acc"],
        })
        assert resp1.json()["created_count"] == 1

        # Second creation — account is now busy, should be skipped
        resp2 = client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-busy-acc"],
        })
        assert resp2.json()["skipped_busy_count"] == 1
        assert resp2.json()["created_count"] == 0

    def test_create_instances_skip_invalid_account(self):
        tpl_id = _create_test_template("inst-invalid-acc")

        resp = client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["nonexistent-acc-id"],
        })
        assert resp.status_code == 200
        assert resp.json()["skipped_error_count"] == 1
        assert resp.json()["created_count"] == 0

    def test_create_instances_nonexistent_template(self):
        resp = client.post("/api/chains/instances", json={
            "template_id": "nonexistent-tpl",
            "account_ids": ["acc-001"],
        })
        assert resp.status_code == 404

    def test_create_instances_no_accounts(self):
        tpl_id = _create_test_template("inst-no-acc")
        resp = client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": [],
        })
        assert resp.status_code == 422

    def test_create_instances_from_groups(self, db):
        """Creating instances from group IDs should expand to member accounts."""
        from app.db_models import AccountGroup, AccountGroupMember

        _create_test_account(db, "chain-group-acc")
        tpl_id = _create_test_template("inst-group-test")

        # Create group + add member
        group_resp = client.post("/api/account-groups", json={"name": "chain-test-group"})
        group_id = group_resp.json()["id"]
        client.post(f"/api/account-groups/{group_id}/members", json={"account_ids": ["chain-group-acc"]})

        resp = client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "group_ids": [group_id],
        })
        assert resp.status_code == 200
        assert resp.json()["created_count"] == 1

    def test_list_instances(self, db):
        _create_test_account(db, "chain-list-acc")
        tpl_id = _create_test_template("inst-list-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-list-acc"],
        })

        resp = client.get("/api/chains/instances")
        assert resp.status_code == 200
        data = resp.json()
        assert "instances" in data
        assert data["total"] >= 1

    def test_list_instances_filter_by_status(self, db):
        _create_test_account(db, "chain-filter-acc")
        tpl_id = _create_test_template("inst-filter-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-filter-acc"],
        })

        resp = client.get("/api/chains/instances?status=running")
        assert resp.status_code == 200
        # All created instances start as running
        assert resp.json()["total"] >= 1

    def test_get_instance_detail(self, db):
        _create_test_account(db, "chain-detail-acc")
        tpl_id = _create_test_template("inst-detail-test")
        create_resp = client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-detail-acc"],
        })

        # Get instance ID from list
        list_resp = client.get("/api/chains/instances?account_id=chain-detail-acc")
        inst_id = list_resp.json()["instances"][0]["id"]

        resp = client.get(f"/api/chains/instances/{inst_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == inst_id
        assert data["template_name"] == "inst-detail-test"
        assert "tasks" in data
        assert len(data["tasks"]) >= 1
        assert data["tasks"][0]["step_order"] == 1

    def test_get_nonexistent_instance(self):
        resp = client.get("/api/chains/instances/nonexistent")
        assert resp.status_code == 404

    def test_cancel_instance(self, db):
        _create_test_account(db, "chain-cancel-acc")
        tpl_id = _create_test_template("inst-cancel-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-cancel-acc"],
        })

        list_resp = client.get("/api/chains/instances?account_id=chain-cancel-acc")
        inst_id = list_resp.json()["instances"][0]["id"]

        resp = client.post(f"/api/chains/instances/{inst_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify instance is cancelled
        detail = client.get(f"/api/chains/instances/{inst_id}")
        assert detail.json()["status"] == "cancelled"

    def test_cancel_already_completed_instance(self, db):
        """Cannot cancel a completed instance."""
        _create_test_account(db, "chain-cancel-done-acc")
        tpl_id = _create_test_template("inst-cancel-done-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-cancel-done-acc"],
        })

        list_resp = client.get("/api/chains/instances?account_id=chain-cancel-done-acc")
        inst_id = list_resp.json()["instances"][0]["id"]

        # Manually set to completed
        from app.database import get_db
        gen = app.dependency_overrides[get_db]()
        session = next(gen)
        inst = session.query(ChainInstance).filter(ChainInstance.id == inst_id).first()
        inst.status = "completed"
        session.commit()
        gen.close()

        resp = client.post(f"/api/chains/instances/{inst_id}/cancel")
        assert resp.status_code == 400

    def test_cancel_nonexistent_instance(self):
        resp = client.post("/api/chains/instances/nonexistent/cancel")
        assert resp.status_code == 404

    def test_retry_failed_instance(self, db):
        _create_test_account(db, "chain-retry-acc")
        tpl_id = _create_test_template("inst-retry-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-retry-acc"],
        })

        list_resp = client.get("/api/chains/instances?account_id=chain-retry-acc")
        inst_id = list_resp.json()["instances"][0]["id"]

        # Get the task and mark it failed
        detail = client.get(f"/api/chains/instances/{inst_id}")
        task_id = detail.json()["tasks"][0]["id"]

        from app.database import get_db
        gen = app.dependency_overrides[get_db]()
        session = next(gen)
        task = session.query(DBTask).filter(DBTask.id == task_id).first()
        task.status = "failed"
        task.completed_at = task.created_at
        inst = session.query(ChainInstance).filter(ChainInstance.id == inst_id).first()
        inst.status = "failed"
        session.commit()
        gen.close()

        resp = client.post(f"/api/chains/instances/{inst_id}/retry")
        assert resp.status_code == 200
        assert resp.json()["status"] == "retrying"
        assert resp.json()["step"] == 1

    def test_retry_non_failed_instance(self, db):
        """Cannot retry a running instance."""
        _create_test_account(db, "chain-retry-running-acc")
        tpl_id = _create_test_template("inst-retry-running-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-retry-running-acc"],
        })

        list_resp = client.get("/api/chains/instances?account_id=chain-retry-running-acc")
        inst_id = list_resp.json()["instances"][0]["id"]

        resp = client.post(f"/api/chains/instances/{inst_id}/retry")
        assert resp.status_code == 400  # not in failed state

    def test_delete_template_blocked_by_active_instances(self, db):
        """Cannot delete a template that has active instances."""
        _create_test_account(db, "chain-protect-acc")
        tpl_id = _create_test_template("inst-protect-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-protect-acc"],
        })

        resp = client.delete(f"/api/chains/templates/{tpl_id}")
        assert resp.status_code == 400
        assert "活跃实例" in resp.json()["detail"]

    def test_update_template_steps_blocked_by_active_instances(self, db):
        """Cannot modify template steps when active instances exist."""
        _create_test_account(db, "chain-protect-steps-acc")
        tpl_id = _create_test_template("inst-protect-steps-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-protect-steps-acc"],
        })

        resp = client.put(f"/api/chains/templates/{tpl_id}", json={
            "steps": [{"step_order": 1, "type": "search_like", "params": {"keyword": "x", "count": 1}}],
        })
        assert resp.status_code == 400
        assert "活跃实例" in resp.json()["detail"]

    def test_instance_state_transitions(self, db):
        """Verify the full state machine: pending -> running -> completed."""
        _create_test_account(db, "chain-state-acc")
        tpl_id = _create_test_template("inst-state-test")
        client.post("/api/chains/instances", json={
            "template_id": tpl_id,
            "account_ids": ["chain-state-acc"],
        })

        list_resp = client.get("/api/chains/instances?account_id=chain-state-acc")
        inst_id = list_resp.json()["instances"][0]["id"]

        # After creation, instance should be running (step 1 task created)
        detail = client.get(f"/api/chains/instances/{inst_id}")
        assert detail.json()["status"] == "running"
        assert detail.json()["current_step"] == 1

        # Simulate task completion -> chain should advance
        task_id = detail.json()["tasks"][0]["id"]
        from app.services.task_service import task_service
        from app.models import TaskStatus
        from app.database import get_db
        gen = app.dependency_overrides[get_db]()
        session = next(gen)
        task_service.report_result(session, task_id, TaskStatus.COMPLETED, {"success_count": 1})
        gen.close()

        # Single-step template -> chain should be completed
        detail2 = client.get(f"/api/chains/instances/{inst_id}")
        assert detail2.json()["status"] == "completed"
```

- [ ] **Step 2: 运行完整链测试**

```bash
cd server && python -m pytest tests/test_chains_api.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_chains_api.py
git commit -m "test: add chain instance lifecycle API tests"
```

---

## Task 4: 链服务单元测试

**Files:**
- Create: `server/tests/test_chain_service.py`

测试覆盖：
- `is_account_busy` — 有/无 pending/running 任务
- `create_chain_instances` — 正常创建、跳过繁忙、跳过无效、模板不存在
- `resolve_accounts_from_groups` — 分组展开、去重、仅 active 账号
- `advance_chain` — 完成当前步推进下一步、最后一步完成链、失败标记链失败、无链实例的任务不处理
- `_create_step_task` — 步骤类型校验
- 互斥锁 TOCTOU 防护

- [ ] **Step 1: 创建 test_chain_service.py**

```python
"""Chain service unit tests — business logic coverage."""
import pytest
from app.models import TaskType, TaskStatus
from app.db_models import (
    Account, Device, ChainTemplate, ChainInstance, Task as DBTask,
    AccountGroup, AccountGroupMember,
)
from app.services.chain_service import chain_service
from app.database import get_db
from app.main import app


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


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


def _make_device(db, device_id, bound_account_id=None):
    dev = Device(id=device_id, name=device_id, bound_account_id=bound_account_id)
    db.add(dev)
    db.commit()
    return dev


class TestIsAccountBusy:
    """is_account_busy checks."""

    def test_busy_with_pending_task(self, db):
        _make_account(db, "busy-pending-acc")
        task = DBTask(type="nurture", account_id="busy-pending-acc", status="pending")
        db.add(task)
        db.commit()

        assert chain_service.is_account_busy(db, "busy-pending-acc") is True

    def test_busy_with_running_task(self, db):
        _make_account(db, "busy-running-acc")
        task = DBTask(type="nurture", account_id="busy-running-acc", status="running")
        db.add(task)
        db.commit()

        assert chain_service.is_account_busy(db, "busy-running-acc") is True

    def test_not_busy_with_completed_task(self, db):
        _make_account(db, "busy-completed-acc")
        task = DBTask(type="nurture", account_id="busy-completed-acc", status="completed")
        db.add(task)
        db.commit()

        assert chain_service.is_account_busy(db, "busy-completed-acc") is False

    def test_not_busy_no_tasks(self, db):
        _make_account(db, "busy-none-acc")
        assert chain_service.is_account_busy(db, "busy-none-acc") is False


class TestCreateChainInstances:
    """create_chain_instances logic."""

    def test_create_single_instance(self, db):
        _make_account(db, "svc-create-acc")
        tpl = _make_template(db, "svc-create-tpl")

        results = chain_service.create_chain_instances(db, tpl.id, ["svc-create-acc"])
        assert len(results["created"]) == 1
        assert results["created"][0] == "svc-create-acc"
        assert len(results["skipped_busy"]) == 0

    def test_skip_busy_account(self, db):
        _make_account(db, "svc-busy-acc")
        task = DBTask(type="nurture", account_id="svc-busy-acc", status="pending")
        db.add(task)
        db.commit()
        tpl = _make_template(db, "svc-busy-tpl")

        results = chain_service.create_chain_instances(db, tpl.id, ["svc-busy-acc"])
        assert len(results["created"]) == 0
        assert "svc-busy-acc" in results["skipped_busy"]

    def test_skip_invalid_account(self, db):
        tpl = _make_template(db, "svc-invalid-tpl")

        results = chain_service.create_chain_instances(db, tpl.id, ["nonexistent-acc"])
        assert len(results["created"]) == 0
        assert "nonexistent-acc" in results["skipped_error"]

    def test_nonexistent_template(self, db):
        with pytest.raises(ValueError, match="模板不存在"):
            chain_service.create_chain_instances(db, "nonexistent-tpl", ["acc-001"])

    def test_mixed_results(self, db):
        """Mix of valid, busy, and invalid accounts."""
        _make_account(db, "svc-mix-valid")
        _make_account(db, "svc-mix-busy")
        task = DBTask(type="nurture", account_id="svc-mix-busy", status="running")
        db.add(task)
        db.commit()
        tpl = _make_template(db, "svc-mix-tpl")

        results = chain_service.create_chain_instances(db, tpl.id, [
            "svc-mix-valid", "svc-mix-busy", "nonexistent",
        ])
        assert len(results["created"]) == 1
        assert len(results["skipped_busy"]) == 1
        assert len(results["skipped_error"]) == 1

    def test_invalid_step_type_in_template(self, db):
        """Template with invalid step type should be rejected."""
        _make_account(db, "svc-badtype-acc")
        tpl = _make_template(db, "svc-badtype-tpl", steps=[
            {"step_order": 1, "type": "invalid_type", "params": {}},
        ])

        with pytest.raises(ValueError, match="无效的步骤类型"):
            chain_service.create_chain_instances(db, tpl.id, ["svc-badtype-acc"])

    def test_multi_step_template(self, db):
        """Multi-step template creates step 1 task and sets instance to running."""
        _make_account(db, "svc-multi-acc")
        tpl = _make_template(db, "svc-multi-tpl", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 5}},
            {"step_order": 2, "type": "search_comment", "params": {"keyword": "test", "count": 3}},
        ])

        results = chain_service.create_chain_instances(db, tpl.id, ["svc-multi-acc"])
        assert len(results["created"]) == 1

        # Verify instance state
        inst = db.query(ChainInstance).filter(ChainInstance.account_id == "svc-multi-acc").first()
        assert inst is not None
        assert inst.status == "running"
        assert inst.current_step == 1
        assert inst.total_steps == 2

        # Verify step 1 task created
        tasks = db.query(DBTask).filter(DBTask.chain_instance_id == inst.id).all()
        assert len(tasks) == 1
        assert tasks[0].step_order == 1
        assert tasks[0].status == "pending"


class TestResolveAccountsFromGroups:
    """Group expansion logic."""

    def test_resolve_single_group(self, db):
        _make_account(db, "grp-resolve-acc")
        group = AccountGroup(name="grp-resolve-test")
        db.add(group)
        db.flush()
        db.add(AccountGroupMember(group_id=group.id, account_id="grp-resolve-acc"))
        db.commit()

        result = chain_service.resolve_accounts_from_groups(db, [group.id])
        assert "grp-resolve-acc" in result

    def test_resolve_deduplicates(self, db):
        """Same account in multiple groups should appear once."""
        _make_account(db, "grp-dedup-acc")
        g1 = AccountGroup(name="grp-dedup-1")
        g2 = AccountGroup(name="grp-dedup-2")
        db.add_all([g1, g2])
        db.flush()
        db.add(AccountGroupMember(group_id=g1.id, account_id="grp-dedup-acc"))
        db.add(AccountGroupMember(group_id=g2.id, account_id="grp-dedup-acc"))
        db.commit()

        result = chain_service.resolve_accounts_from_groups(db, [g1.id, g2.id])
        assert result.count("grp-dedup-acc") == 1

    def test_resolve_only_active(self, db):
        """Banned accounts should be excluded."""
        _make_account(db, "grp-active-acc", status="active")
        _make_account(db, "grp-banned-acc", status="banned")
        group = AccountGroup(name="grp-status-test")
        db.add(group)
        db.flush()
        db.add(AccountGroupMember(group_id=group.id, account_id="grp-active-acc"))
        db.add(AccountGroupMember(group_id=group.id, account_id="grp-banned-acc"))
        db.commit()

        result = chain_service.resolve_accounts_from_groups(db, [group.id])
        assert "grp-active-acc" in result
        assert "grp-banned-acc" not in result

    def test_resolve_empty_groups(self, db):
        result = chain_service.resolve_accounts_from_groups(db, ["nonexistent-group"])
        assert result == []


class TestAdvanceChain:
    """advance_chain state transitions."""

    def test_advance_to_next_step(self, db):
        _make_account(db, "advance-next-acc")
        tpl = _make_template(db, "advance-next-tpl", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 5}},
            {"step_order": 2, "type": "search_comment", "params": {"keyword": "test", "count": 3}},
        ])
        results = chain_service.create_chain_instances(db, tpl.id, ["advance-next-acc"])
        inst = db.query(ChainInstance).filter(ChainInstance.account_id == "advance-next-acc").first()
        task = db.query(DBTask).filter(DBTask.chain_instance_id == inst.id, DBTask.step_order == 1).first()

        chain_service.advance_chain(db, task.id, "completed", {"success_count": 1})

        inst = db.query(ChainInstance).filter(ChainInstance.id == inst.id).first()
        assert inst.current_step == 2
        assert inst.status == "running"

        # Step 2 task should be created
        tasks = db.query(DBTask).filter(DBTask.chain_instance_id == inst.id).order_by(DBTask.step_order).all()
        assert len(tasks) == 2
        assert tasks[1].step_order == 2
        assert tasks[1].status == "pending"

    def test_advance_completes_chain(self, db):
        """Last step completion should mark chain as completed."""
        _make_account(db, "advance-done-acc")
        tpl = _make_template(db, "advance-done-tpl", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 5}},
        ])
        chain_service.create_chain_instances(db, tpl.id, ["advance-done-acc"])
        inst = db.query(ChainInstance).filter(ChainInstance.account_id == "advance-done-acc").first()
        task = db.query(DBTask).filter(DBTask.chain_instance_id == inst.id).first()

        chain_service.advance_chain(db, task.id, "completed", {"success_count": 1})

        inst = db.query(ChainInstance).filter(ChainInstance.id == inst.id).first()
        assert inst.status == "completed"
        assert inst.completed_at is not None

    def test_advance_marks_failure(self, db):
        """Task failure should mark chain as failed."""
        _make_account(db, "advance-fail-acc")
        tpl = _make_template(db, "advance-fail-tpl")
        chain_service.create_chain_instances(db, tpl.id, ["advance-fail-acc"])
        inst = db.query(ChainInstance).filter(ChainInstance.account_id == "advance-fail-acc").first()
        task = db.query(DBTask).filter(DBTask.chain_instance_id == inst.id).first()

        chain_service.advance_chain(db, task.id, "failed", {"error": "something"})

        inst = db.query(ChainInstance).filter(ChainInstance.id == inst.id).first()
        assert inst.status == "failed"
        assert inst.completed_at is not None

    def test_advance_non_chain_task_is_noop(self, db):
        """Tasks without chain_instance_id should be ignored."""
        _make_account(db, "advance-noop-acc")
        task = DBTask(type="nurture", account_id="advance-noop-acc", status="completed")
        db.add(task)
        db.commit()

        # Should not raise
        chain_service.advance_chain(db, task.id, "completed")

    def test_advance_nonexistent_task_is_noop(self, db):
        chain_service.advance_chain(db, "nonexistent-task", "completed")


class TestCreateStepTask:
    """_create_step_task validation."""

    def test_invalid_step_type_raises(self, db):
        _make_account(db, "step-badtype-acc")
        tpl = ChainTemplate(name="step-badtype-tpl", steps=[
            {"step_order": 1, "type": "nurture", "params": {}},
        ])
        db.add(tpl)
        db.flush()
        inst = ChainInstance(template_id=tpl.id, account_id="step-badtype-acc",
                             current_step=1, total_steps=1, status="running")
        db.add(inst)
        db.flush()

        # Override template step with invalid type for this test
        tpl.steps = [{"step_order": 1, "type": "bad_type", "params": {}}]
        db.flush()

        with pytest.raises(ValueError, match="无效的步骤类型"):
            chain_service._create_step_task(db, inst, 1, tpl)

    def test_missing_step_order_raises(self, db):
        _make_account(db, "step-missing-acc")
        tpl = ChainTemplate(name="step-missing-tpl", steps=[
            {"step_order": 1, "type": "nurture", "params": {}},
        ])
        db.add(tpl)
        db.flush()
        inst = ChainInstance(template_id=tpl.id, account_id="step-missing-acc",
                             current_step=1, total_steps=1, status="running")
        db.add(inst)
        db.flush()

        with pytest.raises(ValueError, match="Step 5 not found"):
            chain_service._create_step_task(db, inst, 5, tpl)
```

- [ ] **Step 2: 运行服务测试**

```bash
cd server && python -m pytest tests/test_chain_service.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_chain_service.py
git commit -m "test: add chain service unit tests"
```

---

## Task 5: 养号 V2 参数校验测试

**Files:**
- Modify: `server/tests/test_tasks_api.py`（追加 V2 测试）

测试覆盖：
- V2 sub_tasks 格式创建任务
- V2 参数校验（sub_tasks 为空、count 超限、无效 type）
- 旧版 duration 格式仍然兼容
- 链实例关联任务（chain_instance_id + step_order）

- [ ] **Step 1: 追加养号 V2 测试到 test_tasks_api.py**

```python
class TestNurtureV2Params:
    """Nurture V2 (sub_tasks) parameter validation."""

    def test_create_nurture_v2_task(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [
                    {"type": "browse", "count": 5},
                    {"type": "like", "count": 3},
                ],
                "completion_mode": "all",
                "duration": 30,
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["params"]["sub_tasks"][0]["type"] == "browse"
        assert data["params"]["completion_mode"] == "all"

    def test_nurture_v2_empty_sub_tasks_rejected(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [],
                "duration": 30,
            },
        })
        assert resp.status_code == 422

    def test_nurture_v2_invalid_sub_task_type(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [{"type": "invalid_type", "count": 1}],
                "duration": 30,
            },
        })
        assert resp.status_code == 422

    def test_nurture_v2_count_exceeds_limit(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [{"type": "browse", "count": 200}],  # max is 100
                "duration": 30,
            },
        })
        assert resp.status_code == 422

    def test_nurture_v2_invalid_completion_mode(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [{"type": "browse", "count": 1}],
                "completion_mode": "invalid",
            },
        })
        assert resp.status_code == 422

    def test_nurture_legacy_still_works(self):
        """Legacy duration-only format should still be accepted."""
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {"duration": 30},
        })
        assert resp.status_code == 200
        assert resp.json()["params"]["duration"] == 30

    def test_nurture_v2_with_content_template_id(self):
        """V2 sub_tasks can reference content templates."""
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [
                    {"type": "comment", "count": 2, "content_template_id": "some-template-id"},
                ],
                "duration": 15,
            },
        })
        assert resp.status_code == 200


class TestChainTaskAssociation:
    """Tasks created via chain should have chain_instance_id and step_order."""

    def test_chain_task_has_instance_fields(self, db):
        from app.db_models import Account, ChainTemplate
        from app.services.chain_service import chain_service

        # Setup
        existing = db.query(Account).filter(Account.id == "chain-task-acc").first()
        if not existing:
            db.add(Account(id="chain-task-acc", nickname="chain-task", daily_limits={
                "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
            }))
            db.commit()

        tpl = ChainTemplate(name="chain-task-tpl", steps=[
            {"step_order": 1, "type": "nurture", "params": {"duration": 5}},
        ])
        db.add(tpl)
        db.commit()

        chain_service.create_chain_instances(db, tpl.id, ["chain-task-acc"])

        # Find the task
        from app.db_models import Task as DBTask
        task = db.query(DBTask).filter(DBTask.account_id == "chain-task-acc", DBTask.chain_instance_id.isnot(None)).first()
        assert task is not None
        assert task.chain_instance_id is not None
        assert task.step_order == 1
```

- [ ] **Step 2: 运行增强后的任务测试**

```bash
cd server && python -m pytest tests/test_tasks_api.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_tasks_api.py
git commit -m "test: add nurture V2 params and chain task association tests"
```

---

## Task 6: 全量回归验证

- [ ] **Step 1: 运行全部测试**

```bash
cd server && python -m pytest tests/ -v --tb=short
```

Expected: 全部 PASS，无新增失败

- [ ] **Step 2: 验证测试计数**

```bash
cd server && python -m pytest tests/ --co -q | tail -5
```

Expected: 测试数量从 ~190 增长到 ~240+（新增约 50+ 个测试）

- [ ] **Step 3: Commit（如有修复）**

如有测试失败需要修复代码，修复后提交。

---

## 业务连贯性覆盖矩阵

| 业务流程 | 涉及模块 | 测试任务 |
|---------|---------|---------|
| 创建分组 → 添加成员 → 按分组创建链实例 | account_groups → chains → chain_service | Task 1 + Task 3 + Task 4 |
| 链实例创建 → 步骤1执行 → 推进步骤2 → 完成 | chain_service → task_service | Task 4 (TestAdvanceChain) |
| 链实例创建 → 步骤1失败 → 重试 → 恢复 | chains (retry) → chain_service | Task 3 (test_retry) |
| 链实例创建 → 取消 → 所有任务取消 | chains (cancel) | Task 3 (test_cancel) |
| 模板修改/删除 → 活跃实例保护 | chains (update/delete) | Task 2 + Task 3 |
| 养号 V2 → sub_tasks → 设备执行 | tasks → models → device | Task 5 |
| 账号互斥 → 并发创建链实例跳过繁忙 | chain_service (lock) | Task 4 (TestCreateChainInstances) |

## 状态扭转一致性覆盖

| 状态转换 | 触发条件 | 测试 |
|---------|---------|------|
| instance: pending → running | create_chain_instances | Task 4 (test_multi_step_template) |
| instance: running → running | advance_chain (next step) | Task 4 (test_advance_to_next_step) |
| instance: running → completed | advance_chain (last step) | Task 4 (test_advance_completes_chain) |
| instance: running → failed | advance_chain (task failed) | Task 4 (test_advance_marks_failure) |
| instance: running → cancelled | cancel_instance | Task 3 (test_cancel_instance) |
| instance: failed → running | retry_instance | Task 3 (test_retry_failed_instance) |
| task: pending → running | get_pending_task (claim) | existing test_task_service.py |
| task: running → completed | report_result | existing + Task 5 |
| task: running → failed → pending | report_result (retry) | existing test_task_service.py |
| task: pending/running → cancelled | cancel_task | existing + Task 3 |
