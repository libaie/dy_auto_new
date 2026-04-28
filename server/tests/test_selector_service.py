"""Selector service tests — DB-backed."""
import pytest
from app.services.selector_service import selector_service
from app.database import get_db
from app.main import app


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


def test_get_selectors(db):
    version, selectors = selector_service.get_all_selectors(db)
    assert version >= 1
    assert len(selectors) > 0


def test_get_selector_by_action(db):
    selector = selector_service.get_selector(db, "like_button")
    assert selector is not None
    assert selector["action_name"] == "like_button"
    assert len(selector["strategies"]) > 0


def test_get_nonexistent_selector(db):
    selector = selector_service.get_selector(db, "nonexistent_action")
    assert selector is None


def test_selectors_version(db):
    version = selector_service.get_version(db)
    assert isinstance(version, int)
    assert version >= 1
