"""选择器管理业务域模块。

选择器管理业务域，负责 UI 选择器模板、版本和设备端匹配配置。本文件负责 selector_service 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.selector_management import UISelector
from app.db.models.system_configuration import SystemSetting
from app.db.models import Device

_SELECTORS_REVISION_KEY = "selectors_revision"


def _get_revision(db: Session) -> int:
    """业务函数：处理 _get_revision 对应的业务流程、校验或数据转换。

    入参：db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _set_revision 对应的业务流程、校验或数据转换。

    入参：db、rev 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    row = db.query(SystemSetting).filter(SystemSetting.key == _SELECTORS_REVISION_KEY).first()
    if row:
        row.value = str(rev)
    else:
        db.add(SystemSetting(key=_SELECTORS_REVISION_KEY, value=str(rev)))
    db.flush()


def _bump_revision(db: Session) -> int:
    """业务函数：处理 _bump_revision 对应的业务流程、校验或数据转换。

    入参：db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Increment selectors revision counter and return new value."""
    rev = _get_revision(db) + 1
    _set_revision(db, rev)
    return rev


def _aspect_tag(resolution: str) -> str:
    """业务函数：处理 _aspect_tag 对应的业务流程、校验或数据转换。

    入参：resolution 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _profile_priority 对应的业务流程、校验或数据转换。

    入参：sel_profile、dev_resolution、dev_ar 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _to_dict 对应的业务流程、校验或数据转换。

    入参：sel 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _to_device_dict 对应的业务流程、校验或数据转换。

    入参：sel 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务类：承载 SelectorService 相关的数据结构、状态或业务协作。

    类参数：无显式类参数 承载该类的业务配置、状态或数据字段。
    """
    """UI selector management — DB-backed."""

    def get_all_selectors(self, db: Session, device_id: str = None) -> tuple[int, list[dict]]:
        """业务函数：处理 get_all_selectors 对应的业务流程、校验或数据转换。

        入参：db、device_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 get_selector 对应的业务流程、校验或数据转换。

        入参：db、action_name 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        """Get a single selector by action_name."""
        s = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.enabled == True,
        ).first()
        if not s:
            return None
        return _to_dict(s)

    def get_version(self, db: Session) -> int:
        """业务函数：处理 get_version 对应的业务流程、校验或数据转换。

        入参：db 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        """Get current selectors revision — guaranteed monotonic across all CRUD."""
        return _get_revision(db)

    def create_selector(self, db: Session, action_name: str, strategies: list,
                        platform_version: str = "default", version: int = 1,
                        description: str = "", category: str = "",
                        purpose: str = "locate", strategy_logic: str = "and",
                        extract_field: str = None,
                        clean_mode: str = None, clean_pattern: str = None,
                        clean_prompt: str = None, resolution_profile: str = "default") -> dict:
        """业务函数：处理 create_selector 对应的业务流程、校验或数据转换。

        入参：db、action_name、strategies、platform_version、version、description、category、purpose、strategy_logic、extract_field、clean_mode、clean_pattern、clean_prompt、resolution_profile 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 update_selector 对应的业务流程、校验或数据转换。

        入参：db、action_name、strategies、platform_version、description、category、purpose、strategy_logic、extract_field、clean_mode、clean_pattern、clean_prompt、resolution_profile 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 delete_selector 对应的业务流程、校验或数据转换。

        入参：db、action_name、platform_version、resolution_profile 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 toggle_selector 对应的业务流程、校验或数据转换。

        入参：db、action_name、enabled、platform_version、resolution_profile 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 list_all_selectors 对应的业务流程、校验或数据转换。

        入参：db、include_disabled、category 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
