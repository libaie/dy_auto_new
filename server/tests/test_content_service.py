"""Tests for content service -- template CRUD, sensitive word CRUD, variable substitution."""
import pytest
from app.services.content_service import content_service


class TestTemplateCRUD:
    def test_create_template(self, db):
        tpl = content_service.create_template(
            db, name="test-tpl", category="comment",
            body="Nice video about {keyword}!", variables=["keyword"]
        )
        assert tpl.id
        assert tpl.name == "test-tpl"
        assert tpl.category == "comment"
        assert tpl.body == "Nice video about {keyword}!"
        assert tpl.variables == ["keyword"]
        assert tpl.is_active is True

    def test_list_templates(self, db):
        content_service.create_template(db, name="t1", category="comment", body="b1")
        content_service.create_template(db, name="t2", category="dm", body="b2")
        templates, total = content_service.list_templates(db)
        assert total >= 2
        names = [t.name for t in templates]
        assert "t1" in names
        assert "t2" in names

    def test_list_templates_filter_category(self, db):
        content_service.create_template(db, name="c1", category="comment", body="b1")
        content_service.create_template(db, name="d1", category="dm", body="b2")
        templates, total = content_service.list_templates(db, category="comment")
        for t in templates:
            assert t.category == "comment"

    def test_get_template(self, db):
        tpl = content_service.create_template(db, name="get-me", category="reply", body="body")
        fetched = content_service.get_template(db, tpl.id)
        assert fetched is not None
        assert fetched.name == "get-me"

    def test_get_template_not_found(self, db):
        assert content_service.get_template(db, "nonexistent-id") is None

    def test_update_template(self, db):
        tpl = content_service.create_template(db, name="old", category="comment", body="old body")
        updated = content_service.update_template(db, tpl.id, name="new", body="new body")
        assert updated.name == "new"
        assert updated.body == "new body"

    def test_delete_template(self, db):
        tpl = content_service.create_template(db, name="delete-me", category="comment", body="body")
        result = content_service.delete_template(db, tpl.id)
        assert result is True
        assert content_service.get_template(db, tpl.id) is None

    def test_delete_template_not_found(self, db):
        assert content_service.delete_template(db, "nonexistent-id") is False


class TestSensitiveWordCRUD:
    def test_add_word(self, db):
        word = content_service.add_sensitive_word(db, "赌博")
        assert word.id
        assert word.word == "赌博"

    def test_add_duplicate_word(self, db):
        content_service.add_sensitive_word(db, "违禁词")
        with pytest.raises(ValueError, match="already exists"):
            content_service.add_sensitive_word(db, "违禁词")

    def test_list_words(self, db):
        content_service.add_sensitive_word(db, "word_a")
        content_service.add_sensitive_word(db, "word_b")
        words, total = content_service.list_sensitive_words(db)
        ws = [w.word for w in words]
        assert "word_a" in ws
        assert "word_b" in ws

    def test_delete_word(self, db):
        word = content_service.add_sensitive_word(db, "delete-word")
        result = content_service.delete_sensitive_word(db, word.id)
        assert result is True

    def test_contains_sensitive(self, db):
        # Use a unique word to avoid collision with test_add_word in shared DB
        word = "sensitive_test_marker"
        try:
            content_service.add_sensitive_word(db, word)
        except ValueError:
            pass  # already exists from a previous run
        assert content_service.contains_sensitive(db, f"这里包含{word}内容") is True
        assert content_service.contains_sensitive(db, "正常评论内容") is False


class TestVariableSubstitution:
    def test_substitute_variables(self):
        body = "关于{keyword}的视频，作者{username}"
        context = {"keyword": "美食", "username": "小明"}
        result = content_service.substitute_variables(body, context)
        assert result == "关于美食的视频，作者小明"

    def test_substitute_missing_variable(self):
        body = "关于{keyword}的视频"
        context = {}  # keyword not provided
        result = content_service.substitute_variables(body, context)
        assert result == "关于{keyword}的视频"  # unchanged when missing

    def test_substitute_no_variables(self):
        body = "固定文本内容"
        result = content_service.substitute_variables(body, {"keyword": "test"})
        assert result == "固定文本内容"
