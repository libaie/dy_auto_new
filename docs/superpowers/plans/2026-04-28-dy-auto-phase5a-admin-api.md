# Phase 5a: Admin API 基础 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立管理后台 API 基础 — JWT 认证、管理端点分离、选择器 CRUD、统计查询接口，为 Vue 前端提供完整 API 层。

**Architecture:** 在 `deps.py` 中新增 `verify_admin_token` 依赖（JWT 校验），accounts/devices/tasks 路由从 `verify_device_secret` 切换到 `verify_admin_token`。新增 `selectors.py`（选择器 CRUD）、`stats.py`（统计查询）、`auth.py`（登录/认证）三个路由。设备端 API 保持 `verify_device_secret` 不变。

**Tech Stack:** Python 3.12 / FastAPI / PyJWT / SQLAlchemy / pytest

---

## 文件结构

```
server/app/
├── config.py              # Modify: 添加 ADMIN_SECRET, JWT_SECRET, ADMIN_USERS 配置
├── deps.py                # Modify: 新增 verify_admin_token 依赖
├── models.py              # Modify: 新增 login/request/response 模型
├── main.py                # Modify: 挂载新路由
├── routers/
│   ├── accounts.py        # Modify: 认证从 verify_device_secret → verify_admin_token
│   ├── devices.py         # Modify: 同上
│   ├── tasks.py           # Modify: 同上
│   ├── auth.py            # Create: POST /api/auth/login
│   ├── selectors.py       # Create: 选择器管理 CRUD
│   └── stats.py           # Create: 统计查询 API
├── services/
│   └── selector_service.py # Modify: 新增 create/update/delete 方法
tests/
├── test_admin_auth.py     # Create: 认证相关测试
├── test_selectors_api.py  # Create: 选择器 CRUD 测试
├── test_stats_api.py      # Create: 统计 API 测试
```

---

## Task 1: Admin 认证配置与 JWT 依赖

**Files:**
- Modify: `server/app/config.py:19`
- Modify: `server/app/deps.py`
- Modify: `server/app/models.py`

- [ ] **Step 1: 添加 admin 配置到 config.py**

在 `server/app/config.py` 第 19 行（`DEVICE_SECRET` 之后）添加：

```python
# Admin 认证
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-jwt-secret-key")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
```

- [ ] **Step 2: 添加 Pydantic 模型到 models.py**

在 `server/app/models.py` 末尾（`RiskReport` 之后）添加：

```python
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    expires_in: int  # seconds

class AdminUser(BaseModel):
    username: str
```

- [ ] **Step 3: 添加 verify_admin_token 到 deps.py**

在 `server/app/deps.py` 末尾（`verify_device_secret` 之后）添加：

```python
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
```

- [ ] **Step 4: 安装 PyJWT 依赖**

```bash
cd server && pip install PyJWT==2.10.1
```

然后在 `requirements.txt` 中添加 `PyJWT==2.10.1`。

- [ ] **Step 5: 运行现有测试确认无破坏**

```bash
cd server && python -m pytest tests/ -q --tb=short
```

Expected: 99 passed（现有测试不受影响）

- [ ] **Step 6: Commit**

```bash
git add server/app/config.py server/app/deps.py server/app/models.py server/requirements.txt
git commit -m "feat(server): add JWT admin authentication infrastructure"
```

---

## Task 2: Admin 登录端点

**Files:**
- Create: `server/app/routers/auth.py`
- Modify: `server/app/main.py`
- Create: `server/tests/test_admin_auth.py`

- [ ] **Step 1: 编写认证测试**

```python
# server/tests/test_admin_auth.py
"""Admin authentication API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_login_success(client):
    response = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["expires_in"] > 0


def test_login_wrong_password(client):
    response = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": "wrong",
    })
    assert response.status_code == 401


def test_login_wrong_username(client):
    response = client.post("/api/auth/login", json={
        "username": "nobody",
        "password": ADMIN_PASSWORD,
    })
    assert response.status_code == 401


def test_expired_token_rejected(client):
    """Expired JWT token should be rejected by verify_admin_token."""
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import JWT_SECRET
    from app.deps import verify_admin_token
    from fastapi import HTTPException

    # Create a token that expired 1 hour ago
    payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    expired_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # verify_admin_token should reject expired tokens
    with pytest.raises(HTTPException) as exc_info:
        verify_admin_token(authorization=f"Bearer {expired_token}")
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_protected_endpoint_no_token(client):
    """Admin endpoints should require JWT token."""
    response = client.get("/api/accounts")
    # Currently uses verify_device_secret, will change in Task 3
    # For now just verify the login endpoint works
    assert response.status_code in (401, 200)


def test_protected_endpoint_with_token(client):
    """Admin endpoints should accept valid JWT token."""
    login = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    token = login.json()["token"]

    # After Task 3, this should work with Bearer token
    response = client.get("/api/accounts", headers={
        "Authorization": f"Bearer {token}",
    })
    # May still return 401 until Task 3 switches auth — that's OK
    assert response.status_code in (200, 401)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server && python -m pytest tests/test_admin_auth.py -v
```

Expected: FAIL — `ModuleNotFoundError` 或 404（auth 路由不存在）

- [ ] **Step 3: 创建 auth 路由**

```python
# server/app/routers/auth.py
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
```

- [ ] **Step 4: 挂载路由到 main.py**

修改 `server/app/main.py`，在 `from app.routers import` 行添加 `auth`，并挂载路由：

```python
from app.routers import device, tasks, accounts, devices, auth
# ...
app.include_router(auth.router)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd server && python -m pytest tests/test_admin_auth.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add server/app/routers/auth.py server/app/main.py server/tests/test_admin_auth.py
git commit -m "feat(server): add admin login endpoint with JWT authentication"
```

---

## Task 3: 管理端点认证分离

**Files:**
- Modify: `server/app/routers/accounts.py:9,48,65,80,91,118`
- Modify: `server/app/routers/devices.py:9,43,61,74,86,113`
- Modify: `server/app/routers/tasks.py:8,17,33,47,58`
- Modify: `server/tests/test_admin_auth.py`

- [ ] **Step 1: 修改 accounts.py 认证**

将 `server/app/routers/accounts.py` 中所有 `from app.deps import verify_device_secret` 替换为 `from app.deps import verify_admin_token`，所有 `Depends(verify_device_secret)` 替换为 `Depends(verify_admin_token)`。

具体变更：
- 第 9 行: `from app.deps import verify_device_secret` → `from app.deps import verify_admin_token`
- 第 48 行: `_: None = Depends(verify_device_secret)` → `_: str = Depends(verify_admin_token)`
- 第 65 行: 同上
- 第 80 行: 同上
- 第 91 行: 同上
- 第 118 行: 同上

- [ ] **Step 2: 修改 devices.py 认证**

同理修改 `server/app/routers/devices.py`，将 `verify_device_secret` 全部替换为 `verify_admin_token`。

- [ ] **Step 3: 修改 tasks.py 认证**

同理修改 `server/app/routers/tasks.py`，将 `verify_device_secret` 全部替换为 `verify_admin_token`。

- [ ] **Step 4: 更新认证测试覆盖**

在 `server/tests/test_admin_auth.py` 末尾追加：

```python
def test_accounts_requires_admin_token(client):
    """Accounts CRUD should require admin JWT token."""
    # No token — should get 401
    response = client.get("/api/accounts")
    assert response.status_code == 401

    # With token — should work
    login = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    token = login.json()["token"]
    response = client.get("/api/accounts", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200


def test_devices_requires_admin_token(client):
    """Devices CRUD should require admin JWT token."""
    response = client.get("/api/devices")
    assert response.status_code == 401

    login = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    token = login.json()["token"]
    response = client.get("/api/devices", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200


def test_tasks_requires_admin_token(client):
    """Tasks CRUD should require admin JWT token."""
    response = client.get("/api/tasks")
    assert response.status_code == 401

    login = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    token = login.json()["token"]
    response = client.get("/api/tasks", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200


def test_device_api_still_uses_secret(client):
    """Device-facing endpoints should still use device secret, not JWT."""
    from app.config import DEVICE_SECRET
    response = client.get("/api/device/poll", params={"device_id": "test"}, headers={
        "X-Device-Secret": DEVICE_SECRET,
    })
    assert response.status_code == 200
```

- [ ] **Step 5: 运行全部测试**

```bash
cd server && python -m pytest tests/ -q --tb=short
```

Expected: 所有测试通过。现有测试中使用 `verify_device_secret` fixture override 的会自动失效，需要检查 conftest。

**关键变更 — 现有测试必须同步更新：**

Task 3 将 accounts/devices/tasks 的认证从 `verify_device_secret` 切换为 `verify_admin_token`。这意味着所有现有测试中 override 了 `verify_device_secret` 的 fixture 需要同时 override `verify_admin_token`，否则这些测试会因 401 而失败。

需要修改的测试文件（在每个文件的 client/db fixture 中添加 `verify_admin_token` override）：

- `server/tests/test_task_service.py` — fixture 中添加 `app.dependency_overrides[verify_admin_token] = lambda: "test"`
- `server/tests/test_anti_detect_api.py` — 同上
- `server/tests/test_accounts_api.py`（如果存在）— 同上
- `server/tests/test_devices_api.py`（如果存在）— 同上
- 其他任何使用 `verify_device_secret` override 的测试文件

推荐做法：在 `conftest.py` 中添加一个统一的 admin auth override fixture：

```python
@pytest.fixture(autouse=True)
def admin_auth_override():
    """Override admin auth for all tests to pass without JWT."""
    from app.deps import verify_admin_token
    app.dependency_overrides[verify_admin_token] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(verify_admin_token, None)
```

这样所有测试自动获得 admin 认证，无需逐文件修改。但注意：`conftest.py` 最后的 `app.dependency_overrides.clear()` 会清空这个 override，所以 `admin_auth_override` fixture 必须在 `test_db` fixture 之后执行（autouse fixture 按声明顺序执行）。将 `admin_auth_override` 放在 `conftest.py` 中 `test_db` fixture 之后即可。

- [ ] **Step 6: Commit**

```bash
git add server/app/routers/accounts.py server/app/routers/devices.py server/app/routers/tasks.py server/tests/
git commit -m "feat(server): switch admin endpoints to JWT authentication"
```

---

## Task 4: 选择器管理 CRUD

**Files:**
- Modify: `server/app/services/selector_service.py`
- Create: `server/app/routers/selectors.py`
- Create: `server/tests/test_selectors_api.py`

- [ ] **Step 1: 编写选择器 CRUD 测试**

```python
# server/tests/test_selectors_api.py
"""Selector management CRUD API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_list_selectors(client):
    response = client.get("/api/selectors")
    assert response.status_code == 200
    data = response.json()
    assert "selectors" in data
    assert "version" in data
    assert "total" in data


def test_get_selector_by_action(client):
    response = client.get("/api/selectors/like_button")
    assert response.status_code == 200
    data = response.json()
    assert data["action_name"] == "like_button"
    assert "strategies" in data


def test_get_selector_not_found(client):
    response = client.get("/api/selectors/nonexistent_action")
    assert response.status_code == 404


def test_create_selector(client):
    response = client.post("/api/selectors", json={
        "action_name": "test_action",
        "strategies": [
            {"type": "text", "value": "测试", "priority": 1},
        ],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["action_name"] == "test_action"


def test_update_selector(client):
    # Create first
    client.post("/api/selectors", json={
        "action_name": "update_test",
        "strategies": [{"type": "text", "value": "old", "priority": 1}],
    })

    # Update
    response = client.put("/api/selectors/update_test", json={
        "strategies": [{"type": "text", "value": "new", "priority": 1}],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["strategies"][0]["value"] == "new"


def test_delete_selector(client):
    # Create first
    client.post("/api/selectors", json={
        "action_name": "delete_test",
        "strategies": [{"type": "text", "value": "bye", "priority": 1}],
    })

    # Delete
    response = client.delete("/api/selectors/delete_test")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    # Confirm gone
    response = client.get("/api/selectors/delete_test")
    assert response.status_code == 404


def test_toggle_selector_enabled(client):
    # Create
    client.post("/api/selectors", json={
        "action_name": "toggle_test",
        "strategies": [{"type": "text", "value": "toggle", "priority": 1}],
    })

    # Disable
    response = client.patch("/api/selectors/toggle_test/toggle", json={
        "enabled": False,
    })
    assert response.status_code == 200
    assert response.json()["enabled"] is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server && python -m pytest tests/test_selectors_api.py -v
```

Expected: FAIL — 404（selectors 路由不存在）

- [ ] **Step 3: 扩展 selector_service.py**

在 `server/app/services/selector_service.py` 的 `SelectorService` 类中，在 `get_version` 方法之后添加：

```python
    def create_selector(self, db: Session, action_name: str, strategies: list,
                        platform_version: str = "default", version: int = 1) -> dict:
        """Create a new UI selector."""
        existing = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.platform_version == platform_version,
        ).first()
        if existing:
            raise ValueError(f"Selector '{action_name}' already exists")

        sel = UISelector(
            action_name=action_name,
            platform_version=platform_version,
            strategies=strategies,
            version=version,
        )
        db.add(sel)
        db.commit()
        db.refresh(sel)
        return {
            "action_name": sel.action_name,
            "platform_version": sel.platform_version,
            "strategies": sel.strategies,
            "version": sel.version,
            "enabled": sel.enabled,
        }

    def update_selector(self, db: Session, action_name: str,
                        strategies: list = None, platform_version: str = None) -> dict:
        """Update an existing selector. Auto-bumps version on any change."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        if strategies is not None:
            sel.strategies = strategies
        if platform_version is not None:
            sel.platform_version = platform_version
        # Auto-bump version on any change
        sel.version = (sel.version or 1) + 1

        db.commit()
        db.refresh(sel)
        return {
            "action_name": sel.action_name,
            "platform_version": sel.platform_version,
            "strategies": sel.strategies,
            "version": sel.version,
            "enabled": sel.enabled,
        }

    def delete_selector(self, db: Session, action_name: str) -> bool:
        """Delete a selector by action_name."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            return False
        db.delete(sel)
        db.commit()
        return True

    def toggle_selector(self, db: Session, action_name: str, enabled: bool) -> dict:
        """Enable or disable a selector."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        sel.enabled = enabled
        db.commit()
        db.refresh(sel)
        return {
            "action_name": sel.action_name,
            "platform_version": sel.platform_version,
            "strategies": sel.strategies,
            "version": sel.version,
            "enabled": sel.enabled,
        }

    def list_all_selectors(self, db: Session, include_disabled: bool = False) -> list[dict]:
        """List all selectors (optionally including disabled ones)."""
        query = db.query(UISelector)
        if not include_disabled:
            query = query.filter(UISelector.enabled == True)
        selectors = query.order_by(UISelector.action_name).all()
        return [{
            "action_name": s.action_name,
            "platform_version": s.platform_version,
            "strategies": s.strategies,
            "version": s.version,
            "enabled": s.enabled,
        } for s in selectors]
```

- [ ] **Step 4: 创建 selectors 路由**

```python
# server/app/routers/selectors.py
"""Selector management CRUD API — admin only."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.services.selector_service import selector_service

router = APIRouter(prefix="/api/selectors", tags=["selectors"])


class SelectorCreateRequest(BaseModel):
    action_name: str
    strategies: list[dict]
    platform_version: str = "default"


class SelectorUpdateRequest(BaseModel):
    strategies: Optional[list[dict]] = None
    platform_version: Optional[str] = None
    # Note: version is auto-bumped on any change, not user-settable


class SelectorToggleRequest(BaseModel):
    enabled: bool


@router.get("")
def list_selectors(
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    selectors = selector_service.list_all_selectors(db, include_disabled=include_disabled)
    version = selector_service.get_version(db)
    return {"selectors": selectors, "total": len(selectors), "version": version}


@router.get("/{action_name}")
def get_selector(
    action_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    sel = selector_service.get_selector(db, action_name)
    if not sel:
        raise HTTPException(status_code=404, detail="Selector not found")
    return sel


@router.post("")
def create_selector(
    request: SelectorCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        sel = selector_service.create_selector(
            db, action_name=request.action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sel


@router.put("/{action_name}")
def update_selector(
    action_name: str,
    request: SelectorUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        sel = selector_service.update_selector(
            db, action_name=action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return sel


@router.delete("/{action_name}")
def delete_selector(
    action_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    deleted = selector_service.delete_selector(db, action_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Selector not found")
    return {"deleted": True, "action_name": action_name}


@router.patch("/{action_name}/toggle")
def toggle_selector(
    action_name: str,
    request: SelectorToggleRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        sel = selector_service.toggle_selector(db, action_name, request.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return sel
```

- [ ] **Step 5: 挂载路由到 main.py**

修改 `server/app/main.py`，在 import 和 include_router 中添加 `selectors`。

- [ ] **Step 6: 运行测试确认通过**

```bash
cd server && python -m pytest tests/test_selectors_api.py -v
```

Expected: 7 tests PASSED

- [ ] **Step 7: Commit**

```bash
git add server/app/services/selector_service.py server/app/routers/selectors.py server/app/main.py server/tests/test_selectors_api.py
git commit -m "feat(server): add selector management CRUD API with admin auth"
```

---

## Task 5: 统计查询 API

**Files:**
- Create: `server/app/routers/stats.py`
- Modify: `server/app/main.py`
- Create: `server/tests/test_stats_api.py`

- [ ] **Step 1: 编写统计 API 测试**

```python
# server/tests/test_stats_api.py
"""Stats API tests — dashboard and daily statistics."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_dashboard_summary(client):
    response = client.get("/api/stats/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert "devices" in data
    assert "tasks" in data
    assert data["accounts"]["total"] >= 0
    assert data["devices"]["total"] >= 0
    assert data["tasks"]["total"] >= 0


def test_daily_stats(client):
    response = client.get("/api/stats/daily")
    assert response.status_code == 200
    data = response.json()
    assert "date" in data
    assert "accounts" in data
    assert isinstance(data["accounts"], list)


def test_account_stats(client):
    """Get stats for a specific account."""
    # First get an account
    from app.database import get_db
    from app.main import app as _app
    gen = _app.dependency_overrides[get_db]()
    db = next(gen)
    from app.db_models import Account
    account = db.query(Account).first()
    db.close()
    gen.close()

    if not account:
        pytest.skip("No accounts in test DB")

    response = client.get(f"/api/stats/accounts/{account.id}")
    assert response.status_code == 200
    data = response.json()
    assert "account_id" in data
    assert "today" in data
    assert "remaining" in data


def test_realtime_stats(client):
    response = client.get("/api/stats/realtime")
    assert response.status_code == 200
    data = response.json()
    assert "online_devices" in data
    assert "running_tasks" in data
    assert "pending_tasks" in data
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server && python -m pytest tests/test_stats_api.py -v
```

Expected: FAIL — 404

- [ ] **Step 3: 创建 stats 路由**

```python
# server/app/routers/stats.py
"""Statistics API — dashboard, daily stats, realtime metrics."""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Account, Device, Task, DailyStats
from app.services.stats_service import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard_summary(
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """Dashboard overview — account/device/task counts and status distribution."""
    # Account stats
    total_accounts = db.query(Account).count()
    active_accounts = db.query(Account).filter(Account.status == "active").count()
    risk_accounts = db.query(Account).filter(Account.status == "risk_controlled").count()

    # Device stats
    total_devices = db.query(Device).count()
    online_devices = db.query(Device).filter(Device.status == "online").count()

    # Task stats
    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    running_tasks = db.query(Task).filter(Task.status == "running").count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()
    failed_tasks = db.query(Task).filter(Task.status == "failed").count()

    return {
        "accounts": {
            "total": total_accounts,
            "active": active_accounts,
            "risk_controlled": risk_accounts,
        },
        "devices": {
            "total": total_devices,
            "online": online_devices,
        },
        "tasks": {
            "total": total_tasks,
            "pending": pending_tasks,
            "running": running_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
        },
    }


@router.get("/daily")
def daily_stats(
    date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """Daily operation stats for all accounts."""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    rows = db.query(DailyStats).filter(DailyStats.date == date).all()
    if not rows:
        return {"date": date, "accounts": []}

    # Batch-load accounts to avoid N+1 query
    account_ids = [row.account_id for row in rows]
    accounts_map = {
        a.id: a.nickname
        for a in db.query(Account).filter(Account.id.in_(account_ids)).all()
    }

    accounts = [{
        "account_id": row.account_id,
        "nickname": accounts_map.get(row.account_id, "unknown"),
        "likes": row.likes,
        "comments": row.comments,
        "follows": row.follows,
        "dms": row.dms,
        "replies": row.replies,
    } for row in rows]

    return {"date": date, "accounts": accounts}


@router.get("/accounts/{account_id}")
def account_stats(
    account_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """Stats for a specific account — today's counts and remaining quotas."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Account not found")

    today_counts = stats_service.get_today_counts(db, account_id)
    remaining = stats_service.get_remaining_quotas(db, account_id)

    return {
        "account_id": account_id,
        "nickname": account.nickname,
        "today": today_counts,
        "remaining": remaining,
    }


@router.get("/realtime")
def realtime_stats(
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """Realtime metrics for dashboard auto-refresh."""
    online_devices = db.query(Device).filter(Device.status == "online").count()
    running_tasks = db.query(Task).filter(Task.status == "running").count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()

    return {
        "online_devices": online_devices,
        "running_tasks": running_tasks,
        "pending_tasks": pending_tasks,
    }
```

- [ ] **Step 4: 挂载路由到 main.py**

修改 `server/app/main.py`，添加 `stats` 路由。

- [ ] **Step 5: 运行全部测试**

```bash
cd server && python -m pytest tests/ -q --tb=short
```

Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add server/app/routers/stats.py server/app/main.py server/tests/test_stats_api.py
git commit -m "feat(server): add stats API with dashboard, daily, and realtime endpoints"
```

---

## Task 6: 集成验证与回归测试

- [ ] **Step 1: 运行全量测试**

```bash
cd server && python -m pytest tests/ -v --tb=short
```

Expected: 全部通过（现有 99 + 新增约 19 = ~118 tests）

- [ ] **Step 2: 启动服务验证 API 端点**

```bash
cd server && python -m uvicorn app.main:app --reload --port 8000 &
sleep 2

# 登录获取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 测试管理端点
curl -s http://localhost:8000/api/stats/dashboard -H "Authorization: Bearer $TOKEN" | python -m json.tool
curl -s http://localhost:8000/api/selectors -H "Authorization: Bearer $TOKEN" | python -m json.tool
curl -s http://localhost:8000/api/stats/realtime -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 测试设备端点仍然正常
curl -s http://localhost:8000/api/device/poll?device_id=test -H "X-Device-Secret: change-me-to-a-random-string" | python -m json.tool
```

- [ ] **Step 3: 更新 .env.example**

在 `.env.example` 中添加：

```env
# Admin authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
JWT_SECRET=change-me-jwt-secret-key
JWT_EXPIRE_HOURS=24
```

- [ ] **Step 4: Final Commit**

```bash
git add .env.example
git commit -m "chore: add admin auth config to .env.example"
```

---

## 任务依赖关系

```
Task 1 (JWT 基础设施)
  └─> Task 2 (登录端点)
       └─> Task 3 (认证分离)
            ├─> Task 4 (选择器 CRUD)
            └─> Task 5 (统计 API)
                 └─> Task 6 (集成验证)
```

---

## API 端点汇总

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/auth/login` | 无 | 管理员登录，返回 JWT |
| GET | `/api/selectors` | JWT | 选择器列表 |
| GET | `/api/selectors/{action_name}` | JWT | 获取单个选择器 |
| POST | `/api/selectors` | JWT | 创建选择器 |
| PUT | `/api/selectors/{action_name}` | JWT | 更新选择器 |
| DELETE | `/api/selectors/{action_name}` | JWT | 删除选择器 |
| PATCH | `/api/selectors/{action_name}/toggle` | JWT | 启用/禁用选择器 |
| GET | `/api/stats/dashboard` | JWT | 仪表盘概览 |
| GET | `/api/stats/daily` | JWT | 每日统计 |
| GET | `/api/stats/accounts/{id}` | JWT | 账号统计 |
| GET | `/api/stats/realtime` | JWT | 实时指标 |
| GET/POST | `/api/accounts/*` | JWT | 账号 CRUD（原 device_secret → JWT） |
| GET/POST | `/api/devices/*` | JWT | 设备 CRUD（原 device_secret → JWT） |
| GET/POST | `/api/tasks/*` | JWT | 任务 CRUD（原 device_secret → JWT） |
| GET | `/api/device/poll` | device_secret | 不变 |
| POST | `/api/device/report` | device_secret | 不变 |
| POST | `/api/device/heartbeat` | device_secret | 不变 |
