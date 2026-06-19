# Device Operations PR1 Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a green, behavior-neutral PR1 test boundary for the current `/api/device/*`, `/api/devices/*`, websocket, and offline-checker behavior before any device operations code is moved.

**Architecture:** Keep `server/app/routers/device.py`, `server/app/routers/devices.py`, and `server/app/main.py::_offline_checker` unchanged. Add characterization tests that snapshot route methods, dependency identities, websocket paths, future domain ownership documentation, and the offline-checker lifecycle side effects that later migration PRs must preserve.

**Tech Stack:** FastAPI route metadata, SQLAlchemy model classes, pytest, pytest-asyncio, monkeypatch, existing `app.main` application wiring.

---

## Scope Decisions

- PR1 creates tests only. It does not create an active `app.domains.device_operations` package.
- PR1 keeps the broad migration plan in `docs/superpowers/plans/2026-06-18-device-operations-domain-plan.md` as future context, but supersedes its expected-red PR1 detail with green characterization tests.
- PR1 commits exact files only because the current worktree contains unrelated staged and unstaged changes.
- PR1 snapshots the current admin offline broadcast payload exactly as implemented: `event`, `device_id`, and `status`; there is no `reason` field in the current code.

## File Map

- Create: `server/tests/test_device_operations_auth_parity.py`
  - Owns route method, route name, dependency identity, and websocket path snapshots for `/api/device/*` and `/api/devices/*`.
- Create: `server/tests/test_device_operations_domain_boundary.py`
  - Owns PR1 no-move gates, future domain documentation checks, and app import smoke coverage.
- Create: `server/tests/test_device_operations_status_lifecycle.py`
  - Owns `_offline_checker` heartbeat flush/requeue, stale-device offline broadcast, stuck-task reset/fail, and lifespan task start/stop characterization.
- Do not modify: `server/app/routers/device.py`
- Do not modify: `server/app/routers/devices.py`
- Do not modify: `server/app/main.py`
- Do not create: `server/app/domains/device_operations/__init__.py`
- Do not create: `server/app/domains/device_operations/device_router.py`
- Do not create: `server/app/domains/device_operations/admin_router.py`

---

### Task 1: Route, Auth, And Websocket Snapshot

**Files:**
- Create: `server/tests/test_device_operations_auth_parity.py`
- Do not modify: `server/app/routers/device.py`
- Do not modify: `server/app/routers/devices.py`

- [ ] **Step 1: Create the route/auth characterization test**

Create `server/tests/test_device_operations_auth_parity.py` with exactly this content:

```python
from fastapi.routing import APIRoute, APIWebSocketRoute

from app.main import app


EXPECTED_DEVICE_OPERATION_HTTP_ROUTES = [
    ("/api/device/pair-request", ("POST",), "create_pair_request", ("get_db",)),
    ("/api/device/pair-status", ("GET",), "check_pair_status", ("get_db",)),
    ("/api/device/poll", ("GET",), "poll_tasks", ("get_db", "verify_device_secret")),
    ("/api/device/progress", ("POST",), "report_progress", ("get_db", "verify_device_secret")),
    ("/api/device/report", ("POST",), "report_result", ("get_db", "verify_device_secret")),
    ("/api/device/stats/increment", ("POST",), "stats_increment", ("get_db", "verify_device_secret")),
    ("/api/device/heartbeat", ("POST",), "heartbeat", ("get_db", "verify_device_secret")),
    ("/api/device/register", ("POST",), "register_device", ("get_db", "verify_device_secret")),
    ("/api/device/selectors", ("GET",), "get_selectors", ("get_db", "verify_device_secret")),
    ("/api/device/prompt-templates", ("GET",), "get_prompt_templates", ("get_db", "verify_device_secret")),
    ("/api/device/script-version", ("GET",), "script_version", ("verify_device_secret",)),
    ("/api/device/script-download", ("GET",), "script_download", ("verify_device_secret",)),
    ("/api/device/script-upload", ("POST",), "script_upload", ("verify_admin_token",)),
    ("/api/device/risk-report", ("POST",), "report_risk", ("get_db", "verify_device_secret")),
    ("/api/device/comment-claim-reply", ("POST",), "claim_comment_reply", ("get_db", "verify_device_secret")),
    ("/api/device/comment-claim-release", ("POST",), "release_comment_claim", ("get_db", "verify_device_secret")),
    ("/api/device/generate-content", ("POST",), "generate_content", ("get_db", "verify_device_secret")),
    ("/api/device/templates", ("GET",), "device_list_templates", ("verify_device_secret", "get_db")),
    ("/api/device/templates/{filename}", ("GET",), "device_download_template", ("verify_device_secret", "get_db")),
    ("/api/device/calibrate", ("POST",), "device_calibrate", ("get_db", "verify_device_secret")),
    ("/api/device/ai-proxy", ("POST",), "ai_proxy", ("get_db", "verify_device_secret")),
    ("/api/device/collect-report", ("POST",), "collect_report", ("get_db", "verify_device_secret")),
    ("/api/device/dm-claim-recipient", ("POST",), "dm_claim_recipient", ("get_db", "verify_device_secret")),
    ("/api/device/dm-send-report", ("POST",), "dm_send_report", ("get_db", "verify_device_secret")),
    ("/api/device/dm-release-recipient", ("POST",), "dm_release_recipient", ("get_db", "verify_device_secret")),
    ("/api/device/comment-ai-reply", ("POST",), "save_comment_ai_reply", ("get_db", "verify_device_secret")),
    ("/api/device/user-profile", ("POST",), "save_user_profile", ("get_db", "verify_device_secret")),
    ("/api/device/user-avatar", ("POST",), "upload_user_avatar", ("get_db", "verify_device_secret")),
    ("/api/device/avatar/{douyin_id}", ("GET",), "get_user_avatar", ()),
    ("/api/devices", ("POST",), "create_device", ("get_db", "require_role:admin")),
    ("/api/devices", ("GET",), "list_devices", ("get_db", "verify_admin_token")),
    ("/api/devices/pair-requests", ("GET",), "list_pair_requests", ("get_db", "verify_admin_token")),
    ("/api/devices/pair-requests/{request_id}/approve", ("POST",), "approve_pair_request", ("get_db", "verify_admin_token")),
    ("/api/devices/pair-requests/{request_id}/reject", ("POST",), "reject_pair_request", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}", ("GET",), "get_device", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}", ("PUT",), "update_device", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}/disconnect", ("POST",), "disconnect_device", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}", ("DELETE",), "delete_device", ("get_db", "verify_admin_token")),
]


EXPECTED_DEVICE_OPERATION_WEBSOCKETS = [
    ("/api/device/ws/pair/{token}", "ws_pair_status", "app.routers.device.ws_pair_status", "device"),
    ("/api/device/ws/status", "ws_device_status", "app.routers.device.ws_device_status", "device"),
    ("/api/devices/ws/pair-events", "ws_pair_events", "app.routers.devices.ws_pair_events", "admin"),
]


def test_device_operation_route_table_snapshot():
    routes = [(path, methods, name) for path, methods, name, _dependencies in _device_operation_http_routes()]

    assert routes == [
        (path, methods, name)
        for path, methods, name, _dependencies in EXPECTED_DEVICE_OPERATION_HTTP_ROUTES
    ]


def test_device_operation_auth_dependency_snapshot():
    assert _device_operation_http_routes() == EXPECTED_DEVICE_OPERATION_HTTP_ROUTES


def test_device_operation_websocket_snapshot():
    assert _device_operation_websockets() == EXPECTED_DEVICE_OPERATION_WEBSOCKETS


def _device_operation_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_device_operation_route(route.path):
            dependency_names = [
                _dependency_identity(dep.call)
                for dep in route.dependant.dependencies
                if dep.call
            ]
            routes.append((route.path, tuple(sorted(route.methods)), route.name, tuple(dependency_names)))
    return routes


def _device_operation_websockets():
    websockets = []
    for route in app.routes:
        if isinstance(route, APIWebSocketRoute) and _is_device_operation_route(route.path):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            audience = "admin" if route.path.startswith("/api/devices") else "device"
            websockets.append((route.path, route.name, endpoint, audience))
    return websockets


def _is_device_operation_route(path):
    return (
        path == "/api/device"
        or path.startswith("/api/device/")
        or path == "/api/devices"
        or path.startswith("/api/devices/")
    )


def _dependency_identity(call):
    name = getattr(call, "__name__", repr(call))
    qualname = getattr(call, "__qualname__", "")
    if name == "checker" and qualname.endswith("require_role.<locals>.checker"):
        closure = getattr(call, "__closure__", None) or ()
        for cell in closure:
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, str):
                return f"require_role:{value}"
            if isinstance(value, (frozenset, set, tuple, list)) and value:
                roles = ",".join(sorted(str(role) for role in value))
                return f"require_role:{roles}"
    return name
```

- [ ] **Step 2: Run the auth parity test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 3: Commit the route/auth characterization**

Run:

```powershell
git add server/tests/test_device_operations_auth_parity.py
git commit --only server/tests/test_device_operations_auth_parity.py -m "test: characterize device operation route auth"
```

Expected:

```text
[codex/bailian-high-quality-video-pipeline <commit>] test: characterize device operation route auth
 1 file changed
 create mode 100644 server/tests/test_device_operations_auth_parity.py
```

---

### Task 2: Domain Boundary And No-Move Gates

**Files:**
- Create: `server/tests/test_device_operations_domain_boundary.py`
- Read: `docs/superpowers/specs/2026-06-19-device-operations-domain-design.md`
- Do not create: `server/app/domains/device_operations/__init__.py`

- [ ] **Step 1: Create the domain-boundary characterization test**

Create `server/tests/test_device_operations_domain_boundary.py` with exactly this content:

```python
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-19-device-operations-domain-design.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
LEGACY_DEVICE_ROUTER_PATH = REPO_ROOT / "server/app/routers/device.py"
LEGACY_ADMIN_DEVICE_ROUTER_PATH = REPO_ROOT / "server/app/routers/devices.py"
FUTURE_DOMAIN_PATH = REPO_ROOT / "server/app/domains/device_operations"


def test_device_operations_future_contract_is_documented_in_spec():
    text = SPEC_PATH.read_text(encoding="utf-8")

    required_contract_terms = [
        "app.domains.device_operations",
        "__init__.py",
        "device_router.py",
        "admin_router.py",
        "pairing.py",
        "status_ws.py",
        "status_lifecycle.py",
        "polling.py",
        "reporting.py",
        "script_assets.py",
        "content_bridge.py",
        "adapters.py",
        "DOMAIN_NAME = \"device_operations\"",
        "(\"/api/device\", \"/api/devices\")",
    ]
    for term in required_contract_terms:
        assert term in text


def test_device_operations_bridge_ownership_is_documented_as_temporary():
    text = SPEC_PATH.read_text(encoding="utf-8")

    assert "temporary bridge" in text
    assert "content/collection/DM" in text
    assert "content_collection" in text
    assert "do not move content/collection/DM bridge ownership" in text


def test_device_operations_pr1_keeps_legacy_router_files_active():
    device_text = LEGACY_DEVICE_ROUTER_PATH.read_text(encoding="utf-8")
    admin_text = LEGACY_ADMIN_DEVICE_ROUTER_PATH.read_text(encoding="utf-8")

    assert 'router = APIRouter(prefix="/api/device", tags=["device"])' in device_text
    assert 'router = APIRouter(prefix="/api/devices", tags=["devices"])' in admin_text
    assert _line_count(LEGACY_DEVICE_ROUTER_PATH) >= 1000
    assert _line_count(LEGACY_ADMIN_DEVICE_ROUTER_PATH) >= 300


def test_device_operations_pr1_has_no_active_domain_package():
    assert not (FUTURE_DOMAIN_PATH / "__init__.py").exists()
    assert not (FUTURE_DOMAIN_PATH / "device_router.py").exists()
    assert not (FUTURE_DOMAIN_PATH / "admin_router.py").exists()
    assert not (FUTURE_DOMAIN_PATH / "status_lifecycle.py").exists()


def test_main_continues_to_wire_legacy_device_routers_in_pr1():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.routers import device" in text
    assert "app.include_router(device.router)" in text
    assert "app.include_router(devices.router)" in text
    assert "device_operations" not in text


def test_app_import_smoke_keeps_device_routes_registered():
    from app.main import app

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/api/device/poll" in paths
    assert "/api/device/report" in paths
    assert "/api/devices" in paths
    assert "/api/devices/{device_id}/disconnect" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [ ] **Step 2: Run the domain-boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_domain_boundary.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 3: Commit the domain-boundary gates**

Run:

```powershell
git add server/tests/test_device_operations_domain_boundary.py
git commit --only server/tests/test_device_operations_domain_boundary.py -m "test: guard device operations pr1 boundary"
```

Expected:

```text
[codex/bailian-high-quality-video-pipeline <commit>] test: guard device operations pr1 boundary
 1 file changed
 create mode 100644 server/tests/test_device_operations_domain_boundary.py
```

---

### Task 3: Offline Checker Lifecycle Characterization

**Files:**
- Create: `server/tests/test_device_operations_status_lifecycle.py`
- Read only: `server/app/main.py`

- [ ] **Step 1: Create the lifecycle characterization test**

Create `server/tests/test_device_operations_status_lifecycle.py` with exactly this content:

```python
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class FakePairWsManager:
    def __init__(self, heartbeats=None):
        self._heartbeats = dict(heartbeats or {})
        self._device_last_seen = {}
        self.broadcasts = []
        self.drain_calls = 0

    def drain_heartbeats(self):
        self.drain_calls += 1
        heartbeats = dict(self._heartbeats)
        self._heartbeats.clear()
        return heartbeats

    async def broadcast_to_admins(self, payload):
        self.broadcasts.append(payload)


class FakeSession:
    def __init__(self, first_devices=None, online_devices=None, stuck_tasks=None, fail_commits=0):
        self.first_devices = list(first_devices or [])
        self.online_devices = list(online_devices or [])
        self.stuck_tasks = list(stuck_tasks or [])
        self.fail_commits = fail_commits
        self.commit_count = 0
        self.closed = False
        self.queries = []
        self.updates = []
        self.channel_updates = []

    def query(self, model):
        model_name = getattr(model, "__name__", str(model))
        self.queries.append(model_name)
        return FakeQuery(self, model_name)

    def commit(self):
        self.commit_count += 1
        if self.fail_commits:
            self.fail_commits -= 1
            raise RuntimeError("commit failed")

    def close(self):
        self.closed = True


class FakeQuery:
    def __init__(self, session, model_name):
        self.session = session
        self.model_name = model_name
        self.conditions = []

    def filter(self, *conditions):
        self.conditions.extend(conditions)
        return self

    def first(self):
        if self.model_name == "Device" and self.session.first_devices:
            return self.session.first_devices.pop(0)
        return None

    def all(self):
        if self.model_name == "Device":
            return list(self.session.online_devices)
        if self.model_name == "Task":
            return list(self.session.stuck_tasks)
        return []

    def update(self, values, synchronize_session=False):
        self.session.updates.append((self.model_name, dict(values), synchronize_session))
        if self.model_name == "Device":
            for device in self.session.online_devices:
                for key, value in values.items():
                    setattr(device, key, value)
        if self.model_name == "ChannelItem":
            self.session.channel_updates.append(dict(values))
        return 1


@pytest.mark.asyncio
async def test_offline_checker_requeues_drained_heartbeats_when_flush_commit_fails(monkeypatch):
    now = datetime(2026, 6, 19, 9, 0, 0)
    seen_at = now - timedelta(seconds=3)
    device = SimpleNamespace(id="device-1", status="offline", last_seen_at=None)
    session = FakeSession(first_devices=[device], online_devices=[], fail_commits=1)
    manager = FakePairWsManager(heartbeats={"device-1": seen_at})

    await _run_offline_checker_one_cycle(monkeypatch, session, manager, now)

    assert manager.drain_calls == 1
    assert manager._device_last_seen == {"device-1": seen_at}
    assert device.last_seen_at == seen_at
    assert device.status == "online"
    assert session.commit_count == 1
    assert session.closed is True


@pytest.mark.asyncio
async def test_offline_checker_marks_stale_devices_offline_and_broadcasts_current_payload(monkeypatch):
    now = datetime(2026, 6, 19, 9, 0, 0)
    stale_device = SimpleNamespace(
        id="device-stale",
        status="online",
        last_seen_at=now - timedelta(seconds=121),
    )
    session = FakeSession(online_devices=[stale_device])
    manager = FakePairWsManager()

    await _run_offline_checker_one_cycle(monkeypatch, session, manager, now)

    assert ("Device", {"status": "offline"}, False) in session.updates
    assert stale_device.status == "offline"
    assert manager.broadcasts == [
        {
            "event": "device_status_changed",
            "device_id": "device-stale",
            "status": "offline",
        }
    ]
    assert session.closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial_retry_count", "expected_task_status", "expected_channel_status"),
    [
        (0, "cancelled", "pending"),
        ("max_minus_one", "failed", "failed"),
    ],
)
async def test_offline_checker_handles_stuck_online_device_tasks(
    monkeypatch,
    initial_retry_count,
    expected_task_status,
    expected_channel_status,
):
    from app.services.task_service import MAX_RETRIES

    now = datetime(2026, 6, 19, 9, 0, 0)
    retry_count = MAX_RETRIES - 1 if initial_retry_count == "max_minus_one" else initial_retry_count
    online_device = SimpleNamespace(id="device-online", status="online", last_seen_at=now)
    stuck_task = SimpleNamespace(
        id="task-1",
        status="running",
        retry_count=retry_count,
        completed_at=None,
        device_id="device-online",
        started_at=now - timedelta(minutes=11),
    )
    session = FakeSession(online_devices=[online_device], stuck_tasks=[stuck_task])
    manager = FakePairWsManager()
    monkeypatch.setenv("TASK_STALE_MINUTES", "10")

    await _run_offline_checker_one_cycle(monkeypatch, session, manager, now)

    assert stuck_task.retry_count == retry_count + 1
    assert stuck_task.status == expected_task_status
    assert stuck_task.completed_at == now
    assert session.channel_updates[-1]["status"] == expected_channel_status
    assert session.channel_updates[-1]["assigned_device_id"] is None
    assert session.channel_updates[-1]["assigned_at"] is None
    assert session.channel_updates[-1]["task_id"] is None
    assert session.closed is True


@pytest.mark.asyncio
async def test_lifespan_starts_and_cancels_offline_checker_task(monkeypatch):
    import app.main as main
    from app.services import pixelle_client

    created_task_names = []
    created_tasks = []

    class FakeTask:
        def __init__(self, name):
            self.name = name
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    async def fake_offline_checker():
        return None

    async def fake_style_lock_worker():
        return None

    async def fake_story_plan_worker():
        return None

    async def fake_one_sentence_reference_worker():
        return None

    def fake_create_task(coro):
        name = coro.cr_code.co_name
        created_task_names.append(name)
        coro.close()
        task = FakeTask(name)
        created_tasks.append(task)
        return task

    async def fake_gather(*tasks, return_exceptions=False):
        assert return_exceptions is True
        return list(tasks)

    monkeypatch.setattr(main, "_offline_checker", fake_offline_checker)
    monkeypatch.setattr(main, "_style_lock_worker", fake_style_lock_worker)
    monkeypatch.setattr(main, "_story_plan_worker", fake_story_plan_worker)
    monkeypatch.setattr(main, "_one_sentence_reference_worker", fake_one_sentence_reference_worker)
    monkeypatch.setattr(main.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(main.asyncio, "gather", fake_gather)
    monkeypatch.setattr(main.ai_generator, "aclose", AsyncMock())
    close_pixelle_client = AsyncMock()
    monkeypatch.setattr(pixelle_client, "close_client", close_pixelle_client)

    sentinel = object()
    previous_override = main.app.dependency_overrides.get(main.get_db, sentinel)
    main.app.dependency_overrides[main.get_db] = lambda: None
    try:
        async with main.lifespan(main.app):
            assert created_task_names == [
                "fake_offline_checker",
                "fake_style_lock_worker",
                "fake_story_plan_worker",
                "fake_one_sentence_reference_worker",
            ]
            assert len(created_tasks) == 4
    finally:
        if previous_override is sentinel:
            main.app.dependency_overrides.pop(main.get_db, None)
        else:
            main.app.dependency_overrides[main.get_db] = previous_override

    assert [task.cancelled for task in created_tasks] == [True, True, True, True]
    main.ai_generator.aclose.assert_awaited_once()
    close_pixelle_client.assert_awaited_once()


async def _run_offline_checker_one_cycle(monkeypatch, session, manager, now):
    import app.main as main
    import app.ws_manager as ws_manager_module

    sleep_calls = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            return None
        raise asyncio.CancelledError()

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(main, "bj_now", lambda: now)
    monkeypatch.setattr(ws_manager_module, "pair_ws_manager", manager)

    with pytest.raises(asyncio.CancelledError):
        await main._offline_checker()
```

- [ ] **Step 2: Run the lifecycle test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_status_lifecycle.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 3: Commit the lifecycle characterization**

Run:

```powershell
git add server/tests/test_device_operations_status_lifecycle.py
git commit --only server/tests/test_device_operations_status_lifecycle.py -m "test: characterize device offline lifecycle"
```

Expected:

```text
[codex/bailian-high-quality-video-pipeline <commit>] test: characterize device offline lifecycle
 1 file changed
 create mode 100644 server/tests/test_device_operations_status_lifecycle.py
```

---

### Task 4: Focused PR1 Verification

**Files:**
- Test: `server/tests/test_device_operations_auth_parity.py`
- Test: `server/tests/test_device_operations_domain_boundary.py`
- Test: `server/tests/test_device_operations_status_lifecycle.py`
- Test: `server/tests/test_device_api.py`
- Test: `server/tests/test_device_endpoints.py`
- Test: `server/tests/test_devices_api.py`

- [ ] **Step 1: Run the PR1 focused test set**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py -q
```

Expected:

```text
14 passed
```

- [ ] **Step 2: Run existing device compatibility checks**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

Expected:

```text
All selected existing device tests pass, or any failure is documented as unrelated to the three new PR1 files by the failing test name and traceback.
```

- [ ] **Step 3: Prove the three PR1 commits only contain the new tests**

Run:

```powershell
git diff --name-only HEAD~3..HEAD
```

Expected:

```text
server/tests/test_device_operations_auth_parity.py
server/tests/test_device_operations_domain_boundary.py
server/tests/test_device_operations_status_lifecycle.py
```

- [ ] **Step 4: Show the staged PR1 file list before final commit or PR**

Run:

```powershell
git status --short server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py server/app/routers/device.py server/app/routers/devices.py server/app/main.py
```

Expected after the three task commits:

```text
No output for the three new test files because they are already committed.
Any output for server/app/routers/device.py, server/app/routers/devices.py, or server/app/main.py is pre-existing dirty-tree work and must not be included in the PR1 commits.
```

---

## PR1 Success Criteria

- `server/tests/test_device_operations_auth_parity.py` snapshots every current HTTP route under `/api/device` and `/api/devices`.
- `server/tests/test_device_operations_auth_parity.py` snapshots websocket paths for pair status, device status, and admin pair events.
- `server/tests/test_device_operations_auth_parity.py` distinguishes `verify_device_secret`, `verify_admin_token`, `require_role:admin`, unauthenticated avatar GET, and DB dependency ordering.
- `server/tests/test_device_operations_domain_boundary.py` documents future `device_operations` ownership without creating an active production package.
- `server/tests/test_device_operations_domain_boundary.py` blocks accidental PR1 movement out of `server/app/routers/device.py`, `server/app/routers/devices.py`, and `server/app/main.py`.
- `server/tests/test_device_operations_status_lifecycle.py` characterizes heartbeat drain, DB flush failure requeue, stale-device offline broadcast payload, stuck-task cancel/fail channel reset, and lifespan task cancellation.
- No production route, service, model, frontend, or worker behavior is changed by PR1.
- Only the three new PR1 test files are committed by the implementation work.

## Self-Review Notes

- Spec coverage: route/auth/websocket, no-move boundary, future domain documentation, content/DM bridge documentation, `_offline_checker`, and lifespan behavior are each mapped to a task.
- Placeholder scan: no unresolved implementation blanks are present in the task steps.
- Type consistency: helper names, fake objects, route snapshots, and expected payload shapes match the current code inspected on 2026-06-19.
