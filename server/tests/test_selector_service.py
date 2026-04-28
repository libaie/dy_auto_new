import pytest
from app.services.selector_service import SelectorService


@pytest.fixture
def service():
    return SelectorService()


def test_get_selectors(service):
    version, selectors = service.get_all_selectors()
    assert version == 1
    assert len(selectors) > 0


def test_get_selector_by_action(service):
    selector = service.get_selector("like_button")
    assert selector is not None
    assert selector["action_name"] == "like_button"
    assert len(selector["strategies"]) > 0


def test_get_nonexistent_selector(service):
    selector = service.get_selector("nonexistent_action")
    assert selector is None


def test_selectors_version(service):
    version, _ = service.get_all_selectors()
    assert isinstance(version, int)
    assert version >= 1
