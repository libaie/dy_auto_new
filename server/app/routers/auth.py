"""Admin authentication — login endpoint."""
from fastapi import APIRouter, HTTPException

from app.models import LoginRequest, LoginResponse
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD
from app.deps import create_admin_token, JWT_EXPIRE_HOURS

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """Admin login — returns JWT token."""
    if request.username != ADMIN_USERNAME or request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_admin_token(request.username)
    return LoginResponse(token=token, expires_in=JWT_EXPIRE_HOURS * 3600)
