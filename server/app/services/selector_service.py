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


# Module-level singleton — stateless, DB sessions injected per call
selector_service = SelectorService()
