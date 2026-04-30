"""Admin authentication — login endpoint with brute-force protection."""
import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, HTTPException, Request

from app.models import LoginRequest, LoginResponse
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD, JWT_EXPIRE_HOURS
from app.deps import create_admin_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Rate limiting: max 5 failed attempts per IP within 5 minutes
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 300
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = Lock()


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if too many failed attempts from this IP."""
    now = time.monotonic()
    with _rate_limit_lock:
        attempts = _failed_attempts[client_ip]
        # Remove expired entries
        _failed_attempts[client_ip] = [
            t for t in attempts if now - t < _LOGIN_WINDOW_SECONDS
        ]
        if len(_failed_attempts[client_ip]) >= _LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Try again later.",
            )


def _record_failure(client_ip: str) -> None:
    """Record a failed login attempt."""
    with _rate_limit_lock:
        _failed_attempts[client_ip].append(time.monotonic())


def _clear_failures(client_ip: str) -> None:
    """Clear failed attempts after successful login."""
    with _rate_limit_lock:
        _failed_attempts.pop(client_ip, None)


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, http_request: Request):
    """Admin login — returns JWT token."""
    client_ip = http_request.client.host if http_request.client else "unknown"
    _check_rate_limit(client_ip)

    if request.username != ADMIN_USERNAME or request.password != ADMIN_PASSWORD:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _clear_failures(client_ip)
    token = create_admin_token(request.username)
    return LoginResponse(token=token, expires_in=JWT_EXPIRE_HOURS * 3600)
