"""System settings API — key-value config store for admin UI."""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.db_models import SystemSetting
from app.deps import verify_admin_token, require_role
from app.models import SettingUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys whose values are masked in GET responses (never sent to client)
_SENSITIVE_KEYS = {"ai_api_key", "llm_api_key"}
_MASKED_VALUE = "****"


@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        rows = db.query(SystemSetting).all()
        result = {}
        for s in rows:
            if s.key in _SENSITIVE_KEYS:
                result[s.key] = _MASKED_VALUE
            else:
                result[s.key] = s.value
        return result
    except OperationalError:
        logger.warning("system_settings table missing, returning empty settings")
        return {}


@router.put("")
def update_settings(
    request: SettingUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    for key, value in request.settings.items():
        # Skip masked values — client sent placeholder, don't overwrite real secret
        if value == _MASKED_VALUE and key in _SENSITIVE_KEYS:
            continue
        try:
            existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        except OperationalError:
            logger.warning("system_settings table missing, attempting create")
            from app.database import init_db
            init_db()
            existing = None
        if existing:
            existing.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    db.commit()
    return {"updated": len(request.settings)}
