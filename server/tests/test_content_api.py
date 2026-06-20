"""Integration tests for content API — templates, sensitive words, generate."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _create_template(**overrides):
    """Helper: create a template and return its JSON response."""
    payload = {"name": "test-tpl", "body": "test body", "category": "comment"}
    payload.update(overrides)
    resp = client.post("/api/content/templates", json=payload)
    assert resp.status_code == 200
    return resp.json()


def _create_word(word):
    """Helper: add a sensitive word and return its JSON response."""
    resp = client.post("/api/content/sensitive-words", json={"word": word})
    assert resp.status_code == 200
    return resp.json()


class TestTemplateAPI:
    def test_create_template(self):
        resp = client.post("/api/content/templates", json={
            "name": "美食评论",
            "category": "comment",
            "body": "这个{keyword}看起来太好吃了！",
            "variables": ["keyword"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "美食评论"
        assert data["category"] == "comment"
        assert data["body"] == "这个{keyword}看起来太好吃了！"
        assert data["variables"] == ["keyword"]
        assert data["is_active"] is True
        assert "id" in data

    def test_create_template_validation_error(self):
        resp = client.post("/api/content/templates", json={
            "name": "",
            "body": "",
        })
        assert resp.status_code == 422

    def test_list_templates(self):
        _create_template(name="list-t1", body="body1")
        _create_template(name="list-t2", body="body2", category="dm")
        resp = client.get("/api/content/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "total" in data
        assert data["total"] >= 2

    def test_list_templates_filter_category(self):
        _create_template(name="filter-dm", body="dm body", category="dm")
        resp = client.get("/api/content/templates?category=dm")
        assert resp.status_code == 200
        for t in resp.json()["templates"]:
            assert t["category"] == "dm"

    def test_get_template(self):
        tpl = _create_template(name="get-me", body="body")
        resp = client.get(f"/api/content/templates/{tpl['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-me"

    def test_get_template_not_found(self):
        resp = client.get("/api/content/templates/nonexistent-id")
        assert resp.status_code == 404

    def test_update_template(self):
        tpl = _create_template(name="old", body="old body")
        resp = client.put(f"/api/content/templates/{tpl['id']}", json={"name": "new", "body": "new body"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new"
        assert resp.json()["body"] == "new body"

    def test_delete_template(self):
        tpl = _create_template(name="delete-me", body="body")
        resp = client.delete(f"/api/content/templates/{tpl['id']}")
        assert resp.status_code == 200
        resp = client.get(f"/api/content/templates/{tpl['id']}")
        assert resp.status_code == 404

    def test_delete_template_not_found(self):
        resp = client.delete("/api/content/templates/nonexistent-id")
        assert resp.status_code == 404


class TestSensitiveWordAPI:
    def test_add_word(self):
        resp = client.post("/api/content/sensitive-words", json={"word": "测试敏感词"})
        assert resp.status_code == 200
        assert resp.json()["word"] == "测试敏感词"

    def test_add_duplicate_word(self):
        _create_word("重复词")
        resp = client.post("/api/content/sensitive-words", json={"word": "重复词"})
        assert resp.status_code == 409

    def test_list_words(self):
        _create_word("列表词")
        resp = client.get("/api/content/sensitive-words")
        assert resp.status_code == 200
        data = resp.json()
        assert "words" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_delete_word(self):
        word = _create_word("删除词")
        resp = client.delete(f"/api/content/sensitive-words/{word['id']}")
        assert resp.status_code == 200

    def test_delete_word_not_found(self):
        resp = client.delete("/api/content/sensitive-words/nonexistent-id")
        assert resp.status_code == 404


class TestGenerateAPI:
    def test_generate_success(self, db):
        """Happy path: admin generates content from template."""
        from unittest.mock import patch, AsyncMock
        tpl = _create_template(name="gen-happy", body="关于{keyword}的评论", variables=["keyword"])
        with patch("app.domains.content_collection.content_service.ContentService.generate_from_template",
                    new_callable=AsyncMock, return_value="好吃的内容"):
            resp = client.post("/api/content/generate", json={
                "template_id": tpl["id"],
                "context": {"keyword": "美食"},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["content"] == "好吃的内容"
            assert data["template_id"] == tpl["id"]

    def test_generate_no_api_key(self, monkeypatch):
        """Generate endpoint should return 503 when AI_API_KEY is not set."""
        monkeypatch.delenv("AI_API_KEY", raising=False)
        tpl = _create_template(name="gen-test", body="关于{keyword}的评论", variables=["keyword"])
        resp = client.post("/api/content/generate", json={
            "template_id": tpl["id"],
            "context": {"keyword": "美食"},
        })
        assert resp.status_code == 503

    def test_generate_template_not_found(self):
        resp = client.post("/api/content/generate", json={
            "template_id": "nonexistent",
            "context": {},
        })
        assert resp.status_code == 404


class TestAuthRequired:
    """Verify all content endpoints reject unauthenticated requests."""

    def test_templates_create_requires_auth(self, real_auth):
        resp = client.post("/api/content/templates", json={"name": "x", "body": "y"})
        assert resp.status_code in (401, 403)

    def test_templates_list_requires_auth(self, real_auth):
        resp = client.get("/api/content/templates")
        assert resp.status_code in (401, 403)

    def test_template_get_requires_auth(self, real_auth):
        resp = client.get("/api/content/templates/any-id")
        assert resp.status_code in (401, 403)

    def test_template_update_requires_auth(self, real_auth):
        resp = client.put("/api/content/templates/any-id", json={"name": "x"})
        assert resp.status_code in (401, 403)

    def test_template_delete_requires_auth(self, real_auth):
        resp = client.delete("/api/content/templates/any-id")
        assert resp.status_code in (401, 403)

    def test_sensitive_words_add_requires_auth(self, real_auth):
        resp = client.post("/api/content/sensitive-words", json={"word": "test"})
        assert resp.status_code in (401, 403)

    def test_sensitive_words_list_requires_auth(self, real_auth):
        resp = client.get("/api/content/sensitive-words")
        assert resp.status_code in (401, 403)

    def test_sensitive_words_delete_requires_auth(self, real_auth):
        resp = client.delete("/api/content/sensitive-words/any-id")
        assert resp.status_code in (401, 403)

    def test_generate_requires_auth(self, real_auth):
        resp = client.post("/api/content/generate", json={
            "template_id": "any-id", "context": {},
        })
        assert resp.status_code in (401, 403)
