"""Independent, server-only credentials and safe public configuration for Jev."""
import math
import os

from sqlalchemy.exc import SQLAlchemyError

from app.db_models import SystemSetting
from app.services.crypto import decrypt

DECISION_MODEL = "typesafe-ai/jev"
DECISION_API_URL = "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
_DEFAULTS = {
    "enabled": "false",
    "api_key": "",
    "api_url": DECISION_API_URL,
    "model": DECISION_MODEL,
    "min_confidence": "0.5",
    "min_probability": "0.75",
}
_SETTING_KEYS = {"decision_" + field for field in _DEFAULTS}
_INVALID = "Invalid decision configuration"


def _enabled(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(_INVALID)


def _threshold(value):
    # Environment variables and the settings store are strings; unlike native
    # answers they must be parsed. Booleans must never become numeric thresholds.
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(_INVALID)
    try:
        parsed = float(value)
    except (ValueError, OverflowError):
        raise ValueError(_INVALID) from None
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise ValueError(_INVALID)
    return parsed


def _api_key(value):
    if not isinstance(value, str) or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(_INVALID)
    return value.strip()


def validate_decision_settings(updates):
    """Validate partial settings without echoing values, especially credentials."""
    for key, value in updates.items():
        if key not in _SETTING_KEYS:
            continue
        if key == "decision_enabled":
            _enabled(value)
        elif key in {"decision_min_confidence", "decision_min_probability"}:
            _threshold(value)
        elif key == "decision_api_url":
            if value != DECISION_API_URL:
                raise ValueError(_INVALID)
        elif key == "decision_model":
            if value != DECISION_MODEL:
                raise ValueError(_INVALID)
        else:
            # Empty and masked values are deliberate key-preservation markers.
            _api_key(value)


def _read_configuration(db, *, settings_snapshot=None):
    raw = {field: os.getenv("DECISION_" + field.upper(), default) for field, default in _DEFAULTS.items()}
    encrypted_key = False
    if db is not None or settings_snapshot is not None:
        try:
            stored_values = settings_snapshot
            if stored_values is None:
                rows = db.query(SystemSetting).filter(SystemSetting.key.in_(_SETTING_KEYS)).all()
                stored_values = {row.key: row.value for row in rows}
        except SQLAlchemyError:
            raise ValueError(_INVALID) from None
        for key in _SETTING_KEYS:
            if key not in stored_values:
                continue
            field = key[len("decision_"):]
            raw[field] = stored_values[key]
            if field == "api_key":
                encrypted_key = True
    return raw, encrypted_key


def _public_values(raw):
    validate_decision_settings({"decision_" + key: value for key, value in raw.items() if key != "api_key"})
    return {
        "enabled": _enabled(raw["enabled"]),
        "model": raw["model"],
        "min_confidence": _threshold(raw["min_confidence"]),
        "min_probability": _threshold(raw["min_probability"]),
    }


def resolve_decision_config(db=None):
    """Resolve DB-over-environment settings; decrypt only a stored decision key."""
    raw, encrypted_key = _read_configuration(db)
    config = _public_values(raw)
    key = raw["api_key"]
    if encrypted_key and key:
        try:
            key = decrypt(key)
        except Exception:
            raise ValueError(_INVALID) from None
    key = _api_key(key)
    if key == "****":
        raise ValueError(_INVALID)
    return {**config, "api_key": key, "api_url": raw["api_url"]}


def get_public_decision_config(db=None, *, settings_snapshot=None):
    """Never publish credentials; invalid enabled settings remain fail closed."""
    raw = None
    try:
        raw, _ = _read_configuration(db, settings_snapshot=settings_snapshot)
        return _public_values(raw)
    except ValueError:
        enabled = True
        if raw is not None:
            try:
                enabled = _enabled(raw["enabled"])
            except ValueError:
                pass
        return {
            "enabled": enabled,
            "model": DECISION_MODEL,
            "min_confidence": 0.5,
            "min_probability": 0.75,
        }


def get_decision_settings(db=None, *, settings_snapshot=None):
    """Return effective admin strings; unreadable stored keys can still be replaced."""
    raw, _ = _read_configuration(db, settings_snapshot=settings_snapshot)
    public = _public_values(raw)
    return {
        "decision_enabled": "true" if public["enabled"] else "false",
        "decision_api_key": "****" if raw["api_key"] else "",
        "decision_api_url": raw["api_url"],
        "decision_model": public["model"],
        "decision_min_confidence": str(public["min_confidence"]),
        "decision_min_probability": str(public["min_probability"]),
    }
