"""Account groups API tests — CRUD + member management."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import Account, AccountGroup, AccountGroupMember


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

class TestAccountGroupCRUD:

    def test_create_group(self, client):
        resp = client.post("/api/account-groups", json={
            "name": "测试分组A",
            "description": "分组描述",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试分组A"
        assert data["description"] == "分组描述"
        assert data["member_count"] == 0
        assert "id" in data

    def test_create_group_duplicate_name(self, client):
        client.post("/api/account-groups", json={"name": "dup-group"})
        resp = client.post("/api/account-groups", json={"name": "dup-group"})
        assert resp.status_code == 409

    def test_list_groups(self, client):
        client.post("/api/account-groups", json={"name": "list-test-1"})
        client.post("/api/account-groups", json={"name": "list-test-2"})
        resp = client.get("/api/account-groups")
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert "total" in data
        assert data["total"] >= 2

    def test_get_group(self, client):
        create = client.post("/api/account-groups", json={
            "name": "get-test",
            "description": "desc",
        })
        group_id = create.json()["id"]
        resp = client.get(f"/api/account-groups/{group_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-test"

    def test_get_nonexistent_group(self, client):
        resp = client.get("/api/account-groups/nonexistent-id")
        assert resp.status_code == 404

    def test_update_group(self, client):
        create = client.post("/api/account-groups", json={"name": "upd-old"})
        gid = create.json()["id"]
        resp = client.put(f"/api/account-groups/{gid}", json={
            "name": "upd-new",
            "description": "new desc",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "upd-new"
        assert resp.json()["description"] == "new desc"

    def test_update_group_duplicate_name(self, client):
        client.post("/api/account-groups", json={"name": "upd-dup-a"})
        b = client.post("/api/account-groups", json={"name": "upd-dup-b"})
        bid = b.json()["id"]
        resp = client.put(f"/api/account-groups/{bid}", json={"name": "upd-dup-a"})
        assert resp.status_code == 409

    def test_update_nonexistent_group(self, client):
        resp = client.put("/api/account-groups/no-such-id", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_group(self, client):
        create = client.post("/api/account-groups", json={"name": "del-test"})
        gid = create.json()["id"]
        resp = client.delete(f"/api/account-groups/{gid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        # Verify gone
        resp2 = client.get(f"/api/account-groups/{gid}")
        assert resp2.status_code == 404

    def test_delete_nonexistent_group(self, client):
        resp = client.delete("/api/account-groups/no-such-id")
        assert resp.status_code == 404

    def test_delete_group_cascades_members(self, client, db):
        """Deleting a group should remove its AccountGroupMember rows."""
        # Create a group
        create = client.post("/api/account-groups", json={"name": "cascade-test"})
        gid = create.json()["id"]
        # Seed acc-001 exists; add it as member
        client.post(f"/api/account-groups/{gid}/members", json={"account_ids": ["acc-001"]})
        # Confirm member exists in DB directly
        count_before = db.query(AccountGroupMember).filter(
            AccountGroupMember.group_id == gid,
        ).count()
        assert count_before == 1
        # Delete group
        client.delete(f"/api/account-groups/{gid}")
        # Members should be gone (cascade)
        count_after = db.query(AccountGroupMember).filter(
            AccountGroupMember.group_id == gid,
        ).count()
        assert count_after == 0

    def test_auth_required(self, client, real_auth):
        """Without auth token, endpoints should return 401."""
        resp = client.get("/api/account-groups")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Member management tests
# ---------------------------------------------------------------------------

class TestAccountGroupMembers:

    def test_add_members(self, client):
        create = client.post("/api/account-groups", json={"name": "member-add"})
        gid = create.json()["id"]
        resp = client.post(f"/api/account-groups/{gid}/members", json={
            "account_ids": ["acc-001"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert "acc-001" in data["added"]

    def test_add_members_idempotent(self, client):
        create = client.post("/api/account-groups", json={"name": "member-idem"})
        gid = create.json()["id"]
        client.post(f"/api/account-groups/{gid}/members", json={"account_ids": ["acc-001"]})
        resp = client.post(f"/api/account-groups/{gid}/members", json={"account_ids": ["acc-001"]})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["added"] == []

    def test_add_members_nonexistent_account(self, client, db):
        """Adding an account_id that doesn't exist in Account table should 400."""
        create = client.post("/api/account-groups", json={"name": "member-bad-acct"})
        gid = create.json()["id"]
        resp = client.post(f"/api/account-groups/{gid}/members", json={
            "account_ids": ["nonexistent-account-id"],
        })
        assert resp.status_code == 400

    def test_list_members(self, client):
        create = client.post("/api/account-groups", json={"name": "member-list"})
        gid = create.json()["id"]
        client.post(f"/api/account-groups/{gid}/members", json={"account_ids": ["acc-001"]})
        resp = client.get(f"/api/account-groups/{gid}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["members"][0]["id"] == "acc-001"

    def test_list_members_with_status_filter(self, client, db):
        """Filter members by account status."""
        # Create two accounts with different statuses
        acct_active = Account(id="filter-active", nickname="活跃", status="active")
        acct_banned = Account(id="filter-banned", nickname="封禁", status="banned")
        db.add_all([acct_active, acct_banned])
        db.commit()

        create = client.post("/api/account-groups", json={"name": "member-filter"})
        gid = create.json()["id"]
        client.post(f"/api/account-groups/{gid}/members", json={
            "account_ids": ["filter-active", "filter-banned"],
        })

        # Filter by active
        resp = client.get(f"/api/account-groups/{gid}/members", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["members"][0]["id"] == "filter-active"

        # Filter by banned
        resp2 = client.get(f"/api/account-groups/{gid}/members", params={"status": "banned"})
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 1
        assert resp2.json()["members"][0]["id"] == "filter-banned"

    def test_remove_members(self, client):
        create = client.post("/api/account-groups", json={"name": "member-remove"})
        gid = create.json()["id"]
        client.post(f"/api/account-groups/{gid}/members", json={"account_ids": ["acc-001"]})
        resp = client.request(
            "DELETE",
            f"/api/account-groups/{gid}/members",
            json={"account_ids": ["acc-001"]},
        )
        assert resp.status_code == 200
        assert resp.json()["removed"] == 1
        # Confirm empty
        listing = client.get(f"/api/account-groups/{gid}/members")
        assert listing.json()["total"] == 0

    def test_list_members_nonexistent_group(self, client):
        resp = client.get("/api/account-groups/no-such-id/members")
        assert resp.status_code == 404

    def test_add_members_nonexistent_group(self, client):
        resp = client.post("/api/account-groups/no-such-id/members", json={
            "account_ids": ["acc-001"],
        })
        assert resp.status_code == 404
