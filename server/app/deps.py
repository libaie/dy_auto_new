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


def create_access_token(user_id: str, username: str, role: str) -> str:
    """Create a JWT access token with user identity and role."""
    payload = {
        "sub": username,
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# Backward compat wrapper
def create_admin_token(username: str) -> str:
    return create_access_token("", username, "admin")


def verify_admin_token(authorization: Optional[str] = Header(None)) -> tuple:
    """FastAPI dependency — verifies JWT Bearer token. Returns (user_id, role)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
        role = payload.get("role", "admin")
        return (user_id, role)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*roles: str):
    """Factory — returns a dependency that checks the user has one of the given roles."""
    async def checker(user: tuple = Depends(verify_admin_token)):
        _, role = user
        if role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return checker


def get_current_user_id(user: tuple = Depends(verify_admin_token)) -> str:
    """Extract user_id from token for data scoping."""
    return user[0]


def verify_ws_admin_token(token: str) -> tuple:
    """Verify JWT token from WebSocket query parameter. Returns (user_id, role) or (None, None)."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return (payload.get("user_id", ""), payload.get("role", "admin"))
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return (None, None)


def require_resource_owner(resource, user: tuple, detail: str = "Resource not found"):
    """Return a resource only for its owner or an administrator.

    Unowned legacy records remain administrator-only. A missing user identity
    must never grant an ordinary caller access to unowned records.
    """
    user_id, role = user
    if resource is None or (role != "admin" and (not user_id or resource.user_id != user_id)):
        raise HTTPException(status_code=404, detail=detail)
    return resource


def get_owned_resource(db: Session, model, resource_id: str, user: tuple):
    """Load an owned resource without changing service interfaces."""
    return require_resource_owner(
        db.query(model).filter(model.id == resource_id).first(),
        user,
        detail=f"{model.__name__} not found",
    )


def resource_user_ids(db: Session, model, resource_id: str) -> list[str]:
    """Resolve event recipients; missing/unowned resources reach admins only."""
    row = db.query(model.user_id).filter(model.id == resource_id).first()
    return [row[0]] if row and row[0] else []
