"""Shared FastAPI dependencies — auth, common utilities."""
from fastapi import HTTPException, Header, Depends
from typing import Optional

from app.config import DEVICE_SECRET


def verify_device_secret(x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret")):
    """FastAPI dependency — verifies X-Device-Secret header. Raises 401 if invalid."""
    if x_device_secret != DEVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid device secret")


import jwt
from datetime import datetime, timedelta, timezone
from app.config import JWT_SECRET, JWT_EXPIRE_HOURS


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
