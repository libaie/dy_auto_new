"""Shared FastAPI dependencies — auth, common utilities."""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session

from app.config import DEVICE_SECRET, JWT_SECRET, JWT_EXPIRE_HOURS
from app.database import get_db


def verify_device_secret(
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
    db: Session = Depends(get_db),
) -> Optional[str]:
    """FastAPI dependency — verifies X-Device-Secret header. Returns device_id or None.

    Accepts either the global DEVICE_SECRET (master key) or a per-device secret.
    Returns the device_id for per-device secrets, None for master secret.
    """
    if not x_device_secret:
        raise HTTPException(status_code=401, detail="Missing device secret")

    # Master secret — backward compatible, returns None (can access any device)
    if x_device_secret == DEVICE_SECRET:
        return None

    # Per-device secret — returns device_id for ownership verification
    from app.db_models import Device
    device = db.query(Device).filter(Device.device_secret == x_device_secret).first()
    if device:
        return device.id

    raise HTTPException(status_code=401, detail="Invalid device secret")


def create_admin_token(username: str) -> str:
    """Create a JWT token for admin user."""
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_admin_token(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency — verifies JWT Bearer token. Returns username."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization[7:]  # strip "Bearer "
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def verify_ws_admin_token(token: str) -> Optional[str]:
    """Verify JWT token from WebSocket query parameter. Returns username or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
