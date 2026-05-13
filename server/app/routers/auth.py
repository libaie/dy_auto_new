"""Admin authentication — login endpoint with brute-force protection."""
import hmac
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
_MAX_TRACKED_IPS = 10000


def _get_client_ip(http_request: Request) -> str:
    """获取真实客户端 IP。
    当直连 IP 为本地/私有地址时，说明前面有反向代理，信任 X-Forwarded-For 最左端 IP。
    否则使用 request.client.host（TCP 层真实 IP）。
    """
    import os
    host = http_request.client.host if http_request.client else ""
    is_local = host in ("127.0.0.1", "::1", "localhost") or host.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "192.168."))

    if is_local:
        forwarded = http_request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    # If behind a configured trusted proxy, use the rightmost untrusted IP
    trusted_proxy = os.getenv("TRUSTED_PROXY_COUNT", "0")
    try:
        proxy_count = int(trusted_proxy)
    except ValueError:
        proxy_count = 0

    if proxy_count > 0:
        forwarded = http_request.headers.get("x-forwarded-for")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",")]
            if len(ips) >= proxy_count + 1:
                return ips[-(proxy_count + 1)]
            return ips[0]

    return host or "unknown"


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if too many failed attempts from this IP."""
    now = time.monotonic()
    with _rate_limit_lock:
        # 防止内存无限增长
        if len(_failed_attempts) > _MAX_TRACKED_IPS:
            _failed_attempts.clear()
        attempts = _failed_attempts[client_ip]
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
    client_ip = _get_client_ip(http_request)
    _check_rate_limit(client_ip)

    # 常量时间比较，防止时序攻击
    username_ok = hmac.compare_digest(request.username, ADMIN_USERNAME)
    password_ok = hmac.compare_digest(request.password, ADMIN_PASSWORD)
    if not username_ok or not password_ok:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _clear_failures(client_ip)
    token = create_admin_token(request.username)
    return LoginResponse(token=token, expires_in=JWT_EXPIRE_HOURS * 3600)
