"""Selector management service for selector CRUD and device selector filtering."""
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.selector_management import UISelector
from app.db.models.system_configuration import SystemSetting
from app.db_models import Device

_SELECTORS_REVISION_KEY = "selectors_revision"


def _get_revision(db: Session) -> int:
    """Get current selectors revision counter. Falls back to max(updated_at)
    ts for migration from pre-revision installations."""
    row = db.query(SystemSetting).filter(SystemSetting.key == _SELECTORS_REVISION_KEY).first()
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            pass
    # Migration: seed from existing data
    selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
    if not selectors:
        return 0
    rev = int(max(s.updated_at for s in selectors).timestamp())
    _set_revision(db, rev)
    return rev


def _set_revision(db: Session, rev: int) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == _SELECTORS_REVISION_KEY).first()
    if row:
        row.value = str(rev)
    else:
        db.add(SystemSetting(key=_SELECTORS_REVISION_KEY, value=str(rev)))
    db.flush()


def _bump_revision(db: Session) -> int:
    """Increment selectors revision counter and return new value."""
    rev = _get_revision(db) + 1
    _set_revision(db, rev)
    return rev


def _aspect_tag(resolution: str) -> str:
    """Compute aspect-ratio tag from 'WxH' string, e.g. '1080x2400' → '9:20'."""
    try:
        w, h = resolution.split("x")
        w, h = int(w), int(h)
    except (ValueError, AttributeError):
        return "unknown"
    if w == 0 or h == 0:
        return "unknown"
    # Reduce to simplest ratio
    a, b = w, h
    while b:
        a, b = b, a % b
    gcd = a
    return f"{w // gcd}:{h // gcd}"


def _profile_priority(sel_profile: str, dev_resolution: str, dev_ar: str) -> int:
    """Score a selector's resolution_profile against device resolution.
    3=exact match, 2=same aspect ratio, 1=default, 0=other."""
    if not sel_profile or sel_profile == "default":
        return 1
    if sel_profile == dev_resolution:
        return 3
    if _aspect_tag(sel_profile) == dev_ar:
        return 2
    return 0


def _to_dict(sel: UISelector) -> dict:
    return {
        "action_name": sel.action_name,
        "description": sel.description or "",
        "platform_version": sel.platform_version,
        "resolution_profile": sel.resolution_profile or "default",
        "strategies": sel.strategies,
        "version": sel.version,
        "enabled": sel.enabled,
        "category": sel.category or "",
        "purpose": sel.purpose or "locate",
        "strategy_logic": sel.strategy_logic or "and",
        "extract_field": sel.extract_field,
        "clean_mode": sel.clean_mode,
        "clean_pattern": sel.clean_pattern,
        "clean_prompt": sel.clean_prompt,
    }


def _to_device_dict(sel: UISelector) -> dict:
    """Device-facing dict (no description/version/enabled)."""
    return {
        "action_name": sel.action_name,
        "platform_version": sel.platform_version,
        "resolution_profile": sel.resolution_profile or "default",
        "strategies": sel.strategies,
        "purpose": sel.purpose or "locate",
        "strategy_logic": sel.strategy_logic or "and",
        "extract_field": sel.extract_field,
        "clean_mode": sel.clean_mode,
        "clean_pattern": sel.clean_pattern,
        "clean_prompt": sel.clean_prompt,
    }


class SelectorService:
    """UI selector management — DB-backed."""

    def get_all_selectors(self, db: Session, device_id: str = None) -> tuple[int, list[dict]]:
        """Returns (version, selectors_list). Version is max version across all selectors.
        When device_id is given, filters by resolution_profile: exact match > same AR > default.
        """
        selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
        if not selectors:
            return 0, []

        # Resolve device resolution for profile filtering
        if device_id:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.screen_resolution:
                dev_res = device.screen_resolution
                dev_ar = _aspect_tag(dev_res)
                # Keep all resolution-compatible candidates. The device knows the
                # installed Douyin version, so it must make the final per-action
                # choice between platform-specific/default selector rows.
                selectors = [
                    s for s in selectors
                    if _profile_priority(s.resolution_profile or "default", dev_res, dev_ar) > 0
                ]

        version = _get_revision(db)
        return version, [_to_device_dict(s) for s in selectors]

    def get_selector(self, db: Session, action_name: str) -> Optional[dict]:
        """Get a single selector by action_name."""
        s = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.enabled == True,
        ).first()
        if not s:
            return None
        return _to_dict(s)

    def get_version(self, db: Session) -> int:
        """Get current selectors revision — guaranteed monotonic across all CRUD."""
        return _get_revision(db)

    def create_selector(self, db: Session, action_name: str, strategies: list,
                        platform_version: str = "default", version: int = 1,
                        description: str = "", category: str = "",
                        purpose: str = "locate", strategy_logic: str = "and",
                        extract_field: str = None,
                        clean_mode: str = None, clean_pattern: str = None,
                        clean_prompt: str = None, resolution_profile: str = "default") -> dict:
        """Create a new UI selector."""
        existing = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.platform_version == platform_version,
            UISelector.resolution_profile == resolution_profile,
        ).first()
        if existing:
            raise ValueError(f"Selector '{action_name}' already exists for this platform/profile")

        sel = UISelector(
            action_name=action_name,
            description=description,
            platform_version=platform_version,
            resolution_profile=resolution_profile,
            strategies=strategies,
            version=version,
            category=category or None,
            purpose=purpose or "locate",
            strategy_logic=strategy_logic or "and",
            extract_field=extract_field,
            clean_mode=clean_mode,
            clean_pattern=clean_pattern,
            clean_prompt=clean_prompt,
        )
        db.add(sel)
        _bump_revision(db)
        db.commit()
        db.refresh(sel)
        return _to_dict(sel)

    def update_selector(self, db: Session, action_name: str,
                        strategies: list = None, platform_version: str = None,
                        description: str = None, category: str = None,
                        purpose: str = None, strategy_logic: str = None,
                        extract_field: str = None,
                        clean_mode: str = None, clean_pattern: str = None,
                        clean_prompt: str = None, resolution_profile: str = None) -> dict:
        """Update an existing selector. platform_version and resolution_profile
        are lookup-only (composite key) — never updated. To change them, delete+recreate."""
        q = db.query(UISelector).filter(UISelector.action_name == action_name)
        if platform_version:
            q = q.filter(UISelector.platform_version == platform_version)
        if resolution_profile:
            q = q.filter(UISelector.resolution_profile == resolution_profile)
        sel = q.first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        if strategies is not None:
            sel.strategies = strategies
        if description is not None:
            sel.description = description
        if category is not None:
            sel.category = category or None
        if purpose is not None:
            sel.purpose = purpose
        if strategy_logic is not None:
            sel.strategy_logic = strategy_logic
        if extract_field is not None:
            sel.extract_field = extract_field
        if clean_mode is not None:
            sel.clean_mode = clean_mode
        if clean_pattern is not None:
            sel.clean_pattern = clean_pattern
        if clean_prompt is not None:
            sel.clean_prompt = clean_prompt
        # Auto-bump version on any change
        sel.version = (sel.version or 1) + 1

        _bump_revision(db)
        db.commit()
        db.refresh(sel)
        return _to_dict(sel)

    def delete_selector(self, db: Session, action_name: str, platform_version: str = None,
                        resolution_profile: str = None) -> bool:
        """Delete a selector by (action_name, platform_version, resolution_profile)."""
        q = db.query(UISelector).filter(UISelector.action_name == action_name)
        if platform_version:
            q = q.filter(UISelector.platform_version == platform_version)
        if resolution_profile:
            q = q.filter(UISelector.resolution_profile == resolution_profile)
        sel = q.first()
        if not sel:
            return False
        db.delete(sel)
        _bump_revision(db)
        db.commit()
        return True

    def toggle_selector(self, db: Session, action_name: str, enabled: bool,
                        platform_version: str = None, resolution_profile: str = None) -> dict:
        """Enable or disable a selector by (action_name, platform_version, resolution_profile)."""
        q = db.query(UISelector).filter(UISelector.action_name == action_name)
        if platform_version:
            q = q.filter(UISelector.platform_version == platform_version)
        if resolution_profile:
            q = q.filter(UISelector.resolution_profile == resolution_profile)
        sel = q.first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        sel.enabled = enabled
        _bump_revision(db)
        db.commit()
        db.refresh(sel)
        return _to_dict(sel)

    def list_all_selectors(self, db: Session, include_disabled: bool = False,
                           category: str = None) -> list[dict]:
        """List all selectors (optionally including disabled ones and filtering by category)."""
        query = db.query(UISelector)
        if not include_disabled:
            query = query.filter(UISelector.enabled == True)
        if category:
            query = query.filter(UISelector.category == category)
        selectors = query.order_by(UISelector.action_name).all()
        return [_to_dict(s) for s in selectors]


# Module-level singleton — stateless, DB sessions injected per call
selector_service = SelectorService()
