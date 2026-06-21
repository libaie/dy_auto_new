"""身份访问业务域模块。

身份访问业务域，负责登录、鉴权和用户身份上下文。本文件负责 auth_router 相关业务规则、状态转换和外部系统边界。
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from app.models import LoginRequest, RegisterRequest
from app.config import JWT_EXPIRE_HOURS
from app.deps import create_access_token, require_role
from app.database import get_db

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


@router.post("/login")
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """User login — queries DB, verifies bcrypt hash, returns JWT with user_id + role."""
    client_ip = _get_client_ip(http_request)
    _check_rate_limit(client_ip)

    from app.db.models.identity_access import User
    import bcrypt

    user = db.query(User).filter(User.username == request.username, User.status == "active").first()
    if not user:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    try:
        pw_ok = bcrypt.checkpw(request.password.encode(), user.password_hash.encode())
    except Exception:
        pw_ok = False
    if not pw_ok:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _clear_failures(client_ip)
    token = create_access_token(user.id, user.username, user.role)
    return {"token": token, "expires_in": JWT_EXPIRE_HOURS * 3600, "role": user.role, "user_id": user.id}


@router.post("/device-login")
def device_login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """Device login with account credentials — returns device_secret for binding."""
    client_ip = _get_client_ip(http_request)
    _check_rate_limit(client_ip)

    from app.db.models.identity_access import User
    from app.db.models import Device
    import bcrypt, uuid as _uuid

    user = db.query(User).filter(User.username == request.username, User.status == "active").first()
    if not user:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    try:
        pw_ok = bcrypt.checkpw(request.password.encode(), user.password_hash.encode())
    except Exception:
        pw_ok = False
    if not pw_ok:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _clear_failures(client_ip)

    device = db.query(Device).filter(Device.name == request.username, Device.user_id == user.id).first()
    if device:
        if not device.device_secret:
            device.device_secret = _uuid.uuid4().hex
    else:
        device = Device(id=str(_uuid.uuid4()), name=request.username, user_id=user.id,
                        device_secret=_uuid.uuid4().hex, status="online")
        db.add(device)
    db.commit()
    return {"device_secret": device.device_secret, "user_id": user.id, "device_id": device.id}


@router.post("/register")
def register_user(request: RegisterRequest, user=Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Create a new user (admin only)."""
    from app.db.models.identity_access import User
    import bcrypt

    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    pw_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
    new_user = User(
        username=request.username,
        password_hash=pw_hash,
        role=request.role or "operator",
        nickname=request.nickname or request.username,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "username": new_user.username, "role": new_user.role}


@router.get("/users")
def list_users(user=Depends(require_role("admin")), db: Session = Depends(get_db)):
    """List all users (admin only)."""
    from app.db.models.identity_access import User
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {"users": [{"id": u.id, "username": u.username, "nickname": u.nickname,
                       "role": u.role, "status": u.status, "created_at": str(u.created_at)} for u in users]}
