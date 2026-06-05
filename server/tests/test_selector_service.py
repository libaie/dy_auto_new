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


def test_device_selectors_keep_platform_candidates(db):
    from app.db_models import Device, UISelector

    db.add(Device(
        id="dev-selector-candidates",
        name="selector candidate device",
        device_secret="selector-candidate-secret",
        screen_resolution="1080x2340",
    ))
    db.add(UISelector(
        action_name="candidate_action",
        platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "old", "priority": 1}],
        version=1,
    ))
    db.add(UISelector(
        action_name="candidate_action",
        platform_version="38.6.0",
        resolution_profile="default",
        strategies=[{"type": "image", "template": "candidate.jpg", "priority": 1}],
        version=2,
    ))
    db.commit()

    _, selectors = selector_service.get_all_selectors(db, device_id="dev-selector-candidates")
    candidates = [s for s in selectors if s["action_name"] == "candidate_action"]

    assert {s["platform_version"] for s in candidates} == {"default", "38.6.0"}


def test_revision_bumps_on_create(db):
    """Creating a selector must increment the global revision."""
    from app.db_models import UISelector
    v1 = selector_service.get_version(db)
    db.add(UISelector(
        action_name="rev_test_create",
        platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "test", "priority": 1}],
    ))
    from app.services.selector_service import _bump_revision
    _bump_revision(db)
    db.commit()
    v2 = selector_service.get_version(db)
    assert v2 > v1, f"Revision should increase after create: {v1} -> {v2}"


def test_revision_bumps_on_update(db):
    """Updating a selector must increment the global revision."""
    from app.db_models import UISelector
    sel = UISelector(
        action_name="rev_test_update",
        platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "old", "priority": 1}],
    )
    db.add(sel)
    db.commit()
    v1 = selector_service.get_version(db)
    result = selector_service.update_selector(db, "rev_test_update",
        platform_version="default", resolution_profile="default",
        strategies=[{"type": "text", "value": "new", "priority": 1}])
    v2 = selector_service.get_version(db)
    assert v2 > v1, f"Revision should increase after update: {v1} -> {v2}"


def test_revision_bumps_on_delete(db):
    """Deleting a selector must increment the global revision."""
    from app.db_models import UISelector
    sel = UISelector(
        action_name="rev_test_delete",
        platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "test", "priority": 1}],
    )
    db.add(sel)
    db.commit()
    v1 = selector_service.get_version(db)
    selector_service.delete_selector(db, "rev_test_delete",
        platform_version="default", resolution_profile="default")
    v2 = selector_service.get_version(db)
    assert v2 > v1, f"Revision should increase after delete: {v1} -> {v2}"


def test_revision_bumps_on_toggle(db):
    """Toggling a selector must increment the global revision."""
    from app.db_models import UISelector
    sel = UISelector(
        action_name="rev_test_toggle",
        platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "test", "priority": 1}],
    )
    db.add(sel)
    db.commit()
    v1 = selector_service.get_version(db)
    selector_service.toggle_selector(db, "rev_test_toggle", False,
        platform_version="default", resolution_profile="default")
    v2 = selector_service.get_version(db)
    assert v2 > v1, f"Revision should increase after toggle: {v1} -> {v2}"


def test_resolution_filtering_1080x2400_device(db):
    """1080x2400 device gets default + 1080x2400 + same-AR, not 1080x2340."""
    from app.db_models import Device, UISelector

    db.add(Device(
        id="dev-1080x2400", name="test device 1080x2400",
        device_secret="secret-1080x2400", screen_resolution="1080x2400",
    ))
    db.add(UISelector(
        action_name="resfilter_default", platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "def", "priority": 1}],
    ))
    db.add(UISelector(
        action_name="resfilter_exact", platform_version="default",
        resolution_profile="1080x2400",
        strategies=[{"type": "text", "value": "exact", "priority": 1}],
    ))
    db.add(UISelector(
        action_name="resfilter_other", platform_version="default",
        resolution_profile="1080x2340",
        strategies=[{"type": "text", "value": "other", "priority": 1}],
    ))
    db.commit()

    _, selectors = selector_service.get_all_selectors(db, device_id="dev-1080x2400")
    profiles = {s["resolution_profile"] for s in selectors}

    assert "default" in profiles, "1080x2400 device should get default selectors"
    assert "1080x2400" in profiles, "1080x2400 device should get exact match"
    assert "1080x2340" not in profiles, "1080x2400 device should NOT get 1080x2340 selectors (different AR)"


def test_composite_key_edit_precision(db):
    """Editing same action_name with different resolutions must not touch wrong row."""
    from app.db_models import UISelector

    sel_default = UISelector(
        action_name="ckey_test", platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "default", "priority": 1}],
    )
    sel_1080 = UISelector(
        action_name="ckey_test", platform_version="default",
        resolution_profile="1080x2400",
        strategies=[{"type": "image", "template": "ckey.jpg", "priority": 1}],
    )
    db.add(sel_default)
    db.add(sel_1080)
    db.commit()

    # Update only the 1080x2400 row
    selector_service.update_selector(db, "ckey_test",
        platform_version="default", resolution_profile="1080x2400",
        strategies=[{"type": "image", "template": "ckey_new.jpg", "priority": 1}])

    db.refresh(sel_default)
    db.refresh(sel_1080)

    def_val = sel_default.strategies[0]["value"]
    res_val = sel_1080.strategies[0]["template"]
    assert def_val == "default", f"Default row should be untouched, got: {def_val}"
    assert res_val == "ckey_new.jpg", f"1080x2400 row should be updated, got: {res_val}"


def test_disabled_selector_not_served(db):
    """Disabled selectors must not appear in get_all_selectors for device."""
    from app.db_models import UISelector

    db.add(UISelector(
        action_name="dis_test_active", platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "active", "priority": 1}],
        enabled=True,
    ))
    db.add(UISelector(
        action_name="dis_test_disabled", platform_version="default",
        resolution_profile="default",
        strategies=[{"type": "text", "value": "disabled", "priority": 1}],
        enabled=False,
    ))
    db.commit()

    _, selectors = selector_service.get_all_selectors(db)
    names = {s["action_name"] for s in selectors}
    assert "dis_test_active" in names
    assert "dis_test_disabled" not in names, "Disabled selectors should not be served to devices"
