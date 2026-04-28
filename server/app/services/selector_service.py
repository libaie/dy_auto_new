"""Selector management service — backed by SQLAlchemy database."""
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import UISelector


class SelectorService:
    """UI selector management — DB-backed."""

    def get_all_selectors(self, db: Session) -> tuple[int, list[dict]]:
        """Returns (version, selectors_list). Version is max version across all selectors."""
        selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
        if not selectors:
            return 0, []
        version = max(s.version for s in selectors)
        result = []
        for s in selectors:
            result.append({
                "action_name": s.action_name,
                "platform_version": s.platform_version,
                "strategies": s.strategies,
            })
        return version, result

    def get_selector(self, db: Session, action_name: str) -> Optional[dict]:
        """Get a single selector by action_name."""
        s = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.enabled == True,
        ).first()
        if not s:
            return None
        return {
            "action_name": s.action_name,
            "platform_version": s.platform_version,
            "strategies": s.strategies,
        }

    def get_version(self, db: Session) -> int:
        """Get current selectors version."""
        selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
        if not selectors:
            return 0
        return max(s.version for s in selectors)

    def create_selector(self, db: Session, action_name: str, strategies: list,
                        platform_version: str = "default", version: int = 1) -> dict:
        """Create a new UI selector."""
        existing = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.platform_version == platform_version,
        ).first()
        if existing:
            raise ValueError(f"Selector '{action_name}' already exists")

        sel = UISelector(
            action_name=action_name,
            platform_version=platform_version,
            strategies=strategies,
            version=version,
        )
        db.add(sel)
        db.commit()
        db.refresh(sel)
        return {
            "action_name": sel.action_name,
            "platform_version": sel.platform_version,
            "strategies": sel.strategies,
            "version": sel.version,
            "enabled": sel.enabled,
        }

    def update_selector(self, db: Session, action_name: str,
                        strategies: list = None, platform_version: str = None) -> dict:
        """Update an existing selector. Auto-bumps version on any change."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        if strategies is not None:
            sel.strategies = strategies
        if platform_version is not None:
            sel.platform_version = platform_version
        # Auto-bump version on any change
        sel.version = (sel.version or 1) + 1

        db.commit()
        db.refresh(sel)
        return {
            "action_name": sel.action_name,
            "platform_version": sel.platform_version,
            "strategies": sel.strategies,
            "version": sel.version,
            "enabled": sel.enabled,
        }

    def delete_selector(self, db: Session, action_name: str) -> bool:
        """Delete a selector by action_name."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            return False
        db.delete(sel)
        db.commit()
        return True

    def toggle_selector(self, db: Session, action_name: str, enabled: bool) -> dict:
        """Enable or disable a selector."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        sel.enabled = enabled
        db.commit()
        db.refresh(sel)
        return {
            "action_name": sel.action_name,
            "platform_version": sel.platform_version,
            "strategies": sel.strategies,
            "version": sel.version,
            "enabled": sel.enabled,
        }

    def list_all_selectors(self, db: Session, include_disabled: bool = False) -> list[dict]:
        """List all selectors (optionally including disabled ones)."""
        query = db.query(UISelector)
        if not include_disabled:
            query = query.filter(UISelector.enabled == True)
        selectors = query.order_by(UISelector.action_name).all()
        return [{
            "action_name": s.action_name,
            "platform_version": s.platform_version,
            "strategies": s.strategies,
            "version": s.version,
            "enabled": s.enabled,
        } for s in selectors]


# Module-level singleton — stateless, DB sessions injected per call
selector_service = SelectorService()
