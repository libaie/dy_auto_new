"""Tests for task creation API -- template resolution."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.domains.content_collection.content_service import content_service
from tests.conftest import setup_group

client = TestClient(app)


class TestTaskCreationWithTemplate:
    """Tests for template resolution during task creation."""

    def test_create_task_with_template_resolves_content(self, db):
        """Task created with content_template_id gets content injected."""
        tpl = content_service.create_template(
            db, name="create-test", body="关于{keyword}的评论",
            category="comment", variables=["keyword"],
        )

        with patch("app.domains.content_collection.content_service.ContentService.generate_from_template",
                    new_callable=AsyncMock, return_value="AI生成的评论"):
            resp = client.post("/api/tasks", json={
                "type": "search_comment",
                "account_id": "acc-001",
                "params": {
                    "keyword": "美食",
                    "count": 3,
                    "content_template_id": tpl.id,
                },
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["params"]["content"] == "AI生成的评论"
            assert "content_template_id" in data["params"]  # preserved for reference

    def test_create_task_without_template_unchanged(self):
        """Task without content_template_id keeps params as-is."""
        resp = client.post("/api/tasks", json={
            "type": "search_comment",
            "account_id": "acc-001",
            "params": {"keyword": "美食", "count": 3, "content": "静态内容"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["params"]["content"] == "静态内容"

    def test_create_task_template_not_found_stores_without_content(self, db):
        """If template doesn't exist, task is created without content (no crash)."""
        resp = client.post("/api/tasks", json={
            "type": "search_comment",
            "account_id": "acc-001",
            "params": {
                "keyword": "美食",
                "content_template_id": "nonexistent-template",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" not in data["params"] or data["params"]["content"] is None

    def test_create_task_ai_failure_stores_without_content(self, db):
        """If AI generation fails, task is created without content (no crash)."""
        tpl = content_service.create_template(
            db, name="fail-test", body="测试内容",
            category="comment",
        )

        with patch("app.domains.content_collection.content_service.ContentService.generate_from_template",
                    new_callable=AsyncMock, side_effect=RuntimeError("AI API failed")):
            resp = client.post("/api/tasks", json={
                "type": "search_comment",
                "account_id": "acc-001",
                "params": {"keyword": "美食", "content_template_id": tpl.id},
            })
            assert resp.status_code == 200  # task still created
            data = resp.json()
            assert "content" not in data["params"] or data["params"]["content"] is None

    def test_nurture_task_skips_template_resolution(self, db):
        """Nurture tasks don't use content -- skip AI generation."""
        tpl = content_service.create_template(
            db, name="nurture-test", body="不相关",
            category="comment",
        )

        with patch("app.domains.content_collection.content_service.ContentService.generate_from_template",
                    new_callable=AsyncMock) as mock_gen:
            resp = client.post("/api/tasks", json={
                "type": "nurture",
                "account_id": "acc-001",
                "params": {"duration": 30, "content_template_id": tpl.id},
            })
            assert resp.status_code == 200
            mock_gen.assert_not_called()  # AI never called for nurture tasks


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
            "params": {"sub_tasks": [], "duration": 30},
        })
        assert resp.status_code == 422

    def test_nurture_v2_invalid_sub_task_type(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {"sub_tasks": [{"type": "invalid_type", "count": 1}], "duration": 30},
        })
        assert resp.status_code == 422

    def test_nurture_v2_count_exceeds_limit(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {"sub_tasks": [{"type": "browse", "count": 200}], "duration": 30},
        })
        assert resp.status_code == 422

    def test_nurture_v2_invalid_completion_mode(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {"sub_tasks": [{"type": "browse", "count": 1}], "completion_mode": "invalid"},
        })
        assert resp.status_code == 422

    def test_nurture_legacy_still_works(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {"duration": 30},
        })
        assert resp.status_code == 200
        assert resp.json()["params"]["duration"] == 30

    def test_nurture_v2_with_content_template_id(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [{"type": "comment", "count": 2, "content_template_id": "some-template-id"}],
                "duration": 15,
            },
        })
        assert resp.status_code == 200

    def test_nurture_v2_resolves_comment_subtask_template(self, db):
        tpl = content_service.create_template(
            db, name="nurture-comment-template", body="reply for {keyword}",
            category="comment", variables=["keyword"],
        )

        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {
                "sub_tasks": [{"type": "comment", "count": 1, "content_template_id": tpl.id}],
                "duration": 15,
                "keywords": ["seed-a"],
                "keyword_matrix": ["seed-a", "expanded-a"],
            },
        })

        assert resp.status_code == 200
        sub_task = resp.json()["params"]["sub_tasks"][0]
        assert sub_task["content"] == "reply for seed-a"

    def test_nurture_v2_preserves_expand_count_for_keyword_expansion(self):
        with patch("app.domains.content_collection.content_service.ContentService.generate_keyword_matrix",
                   new_callable=AsyncMock, return_value=["expanded-a", "expanded-b"]) as mock_expand:
            resp = client.post("/api/tasks", json={
                "type": "nurture",
                "account_id": "acc-001",
                "params": {
                    "sub_tasks": [{"type": "like", "count": 1}],
                    "completion_mode": "all",
                    "duration": 15,
                    "keywords": ["seed-a"],
                    "expand_count": 13,
                },
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["params"]["expand_count"] == 13
        assert data["params"]["keyword_matrix"] == ["seed-a", "expanded-a", "expanded-b"]
        assert mock_expand.await_args.args[:2] == ("seed-a", 13)

    def test_batch_nurture_without_keywords_creates_direct_tasks(self, db):
        setup_group(db, group_id="grp-nurture-no-keywords", account_ids=["acc-nurture-a", "acc-nurture-b"])

        resp = client.post("/api/tasks/batch", json={
            "type": "nurture",
            "group_ids": ["grp-nurture-no-keywords"],
            "params": {"duration": 20},
        })

        assert resp.status_code == 200
        assert resp.json() == {"created": 2, "mode": "direct"}

    def test_nurture_v2_duration_exceeds_limit(self):
        resp = client.post("/api/tasks", json={
            "type": "nurture",
            "account_id": "acc-001",
            "params": {"sub_tasks": [{"type": "browse", "count": 1}], "duration": 500},
        })
        assert resp.status_code == 422


class TestChainTaskAssociation:
    """Tasks created via chain should have chain_instance_id and step_order."""

    def test_chain_task_has_instance_fields(self, db):
        from app.db.models import Account, ChainTemplate, Task as DBTask
        from app.domains.account_operations.chain_service import chain_service

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

        task = db.query(DBTask).filter(
            DBTask.account_id == "chain-task-acc",
            DBTask.chain_instance_id.isnot(None),
        ).first()
        assert task is not None
        assert task.chain_instance_id is not None
        assert task.step_order == 1
