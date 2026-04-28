"""Shared FastAPI dependencies — auth, common utilities."""
from fastapi import HTTPException, Header, Depends
from typing import Optional

from app.config import DEVICE_SECRET


def verify_device_secret(x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret")):
    """FastAPI dependency — verifies X-Device-Secret header. Raises 401 if invalid."""
    if x_device_secret != DEVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid device secret")
