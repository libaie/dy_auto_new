# Phase 1: Database + CRUD APIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MVP's in-memory storage with SQLAlchemy + SQLite, add Account/Device CRUD APIs, and set up Alembic for schema migrations.

**Architecture:** SQLAlchemy ORM models for persistence (`app/db_models.py`), keeping Pydantic models for API validation (`app/models.py`). FastAPI dependency injection for DB sessions. Alembic manages schema migrations. Seed script imports existing YAML config into DB on first run.

**Tech Stack:** SQLAlchemy 2.0, Alembic, SQLite (switchable to PostgreSQL via `DATABASE_URL` env var)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `server/requirements.txt` | Modify | Add sqlalchemy, alembic |
| `server/app/db_models.py` | Create | SQLAlchemy ORM models (accounts, devices, tasks, ui_selectors) |
| `server/app/database.py` | Create | Engine, session factory, Base, get_db dependency |
| `server/alembic.ini` | Create | Alembic config |
| `server/alembic/env.py` | Create | Alembic env (imports db_models) |
| `server/alembic/versions/001_initial.py` | Create | Initial migration (4 tables) |
| `server/app/seed.py` | Create | Import YAML config into DB |
| `server/app/services/task_service.py` | Rewrite | Use SQLAlchemy instead of in-memory dict |
| `server/app/services/selector_service.py` | Rewrite | Use SQLAlchemy instead of YAML direct reads |
| `server/app/deps.py` | Create | Shared FastAPI dependencies (auth) |
| `server/app/routers/accounts.py` | Create | Account CRUD endpoints |
| `server/app/routers/devices.py` | Create | Device CRUD endpoints |
| `server/app/routers/device.py` | Modify | Use DB-backed services |
| `server/app/routers/tasks.py` | Modify | Use DB-backed services |
| `server/app/main.py` | Modify | Add new routers, startup seed |
| `server/tests/conftest.py` | Create | Shared test DB fixture |
| `server/tests/test_accounts_api.py` | Create | Account CRUD tests |
| `server/tests/test_devices_api.py` | Create | Device CRUD tests |
| `server/tests/test_e2e_flow.py` | Modify | Update for DB-backed services |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `server/requirements.txt`

- [ ] **Step 1: Add SQLAlchemy and Alembic to requirements.txt**

```txt
fastapi==0.136.1
uvicorn[standard]==0.46.0
pydantic==2.13.3
pydantic-settings==2.14.0
pyyaml==6.0.3
python-dotenv==1.2.2
httpx==0.28.1
sqlalchemy==2.0.41
alembic==1.16.2
pytest==9.0.3
pytest-asyncio==1.3.0
```

- [ ] **Step 2: Install new dependencies**

Run: `cd server && source venv/bin/activate && pip install sqlalchemy==2.0.41 alembic==1.16.2`

Expected: Successfully installed sqlalchemy-2.0.41 alembic-1.16.2

- [ ] **Step 3: Verify imports work**

Run: `python -c "import sqlalchemy; print(sqlalchemy.__version__)"`

Expected: `2.0.41`

- [ ] **Step 4: Commit**

```bash
git add server/requirements.txt
git commit -m "deps: add sqlalchemy and alembic for database layer"
```

---

## Task 2: SQLAlchemy ORM Models

**Files:**
- Create: `server/app/db_models.py`

- [ ] **Step 1: Create SQLAlchemy ORM models**

```python
"""SQLAlchemy ORM models — database persistence layer."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Boolean,
    JSON, ForeignKey, Enum as SAEnum, event,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True, default=_uuid)
    nickname = Column(String(100), nullable=False)
    douyin_id = Column(String(100), nullable=False, default="")
    group = Column(String(50), nullable=False, default="default")
    status = Column(String(20), nullable=False, default="active")  # active, risk_controlled, banned
    cookie = Column(Text, nullable=True)  # encrypted cookie, nullable for MVP
    daily_limits = Column(JSON, nullable=False, default=lambda: {
        "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
    })
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="account")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    ip = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="offline")  # online, offline, maintenance
    bound_account_id = Column(String(36), ForeignKey("accounts.id"), nullable=True)
    proxy_config = Column(JSON, nullable=True)  # {"type":"http","host":"...","port":8080,"username":"...","password":"..."}
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="device")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    type = Column(String(30), nullable=False)  # nurture, search_comment, search_like, search_dm, reply_comment
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    result = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    account = relationship("Account", back_populates="tasks")
    device = relationship("Device", back_populates="tasks")


class UISelector(Base):
    __tablename__ = "ui_selectors"

    id = Column(String(36), primary_key=True, default=_uuid)
    action_name = Column(String(100), nullable=False, index=True)
    platform_version = Column(String(50), nullable=False, default="default")
    strategies = Column(JSON, nullable=False)  # list of {type, value, x_percent, y_percent, priority}
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 2: Verify module loads without errors**

Run: `cd server && python -c "from app.db_models import Base, Account, Device, Task, UISelector; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/app/db_models.py
git commit -m "feat: add SQLAlchemy ORM models for accounts, devices, tasks, selectors"
```

---

## Task 3: Database Session Management

**Files:**
- Create: `server/app/database.py`

- [ ] **Step 1: Create database session management module**

```python
"""Database engine, session factory, and FastAPI dependency."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from app.db_models import Base

SERVER_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = SERVER_DIR / "app" / "data" / "dy_auto.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite needs check_same_thread=False for FastAPI's multi-threaded request handling
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Create all tables. Called once at startup."""
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith("sqlite"):
        Path(DATABASE_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session per request, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Verify module loads**

Run: `cd server && python -c "from app.database import engine, SessionLocal, init_db, get_db; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/app/database.py
git commit -m "feat: add database session management with SQLAlchemy"
```

---

## Task 4: Shared Auth Dependency

**Files:**
- Create: `server/app/deps.py`

- [ ] **Step 1: Create shared dependencies module**

```python
"""Shared FastAPI dependencies — auth, common utilities."""
from fastapi import HTTPException, Header, Depends
from typing import Optional

from app.config import DEVICE_SECRET


def verify_device_secret(x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret")):
    """FastAPI dependency — verifies X-Device-Secret header. Raises 401 if invalid."""
    if x_device_secret != DEVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid device secret")
```

- [ ] **Step 2: Verify module loads**

Run: `cd server && python -c "from app.deps import verify_device_secret; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/app/deps.py
git commit -m "feat: add shared auth dependency"
```

---

## Task 5: Alembic Setup and Initial Migration

**Files:**
- Create: `server/alembic.ini`
- Create: `server/alembic/env.py`
- Create: `server/alembic/script.py.mako`
- Create: `server/alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Initialize Alembic**

Run: `cd server && python -m alembic init alembic`

Expected: Creates `server/alembic/` directory with template files and `server/alembic.ini`.

- [ ] **Step 2: Configure alembic.ini**

Edit `server/alembic.ini` — find line `sqlalchemy.url = driver://user:pass@localhost/dbname` and replace with:

```ini
sqlalchemy.url = sqlite:///app/data/dy_auto.db
```

- [ ] **Step 3: Replace alembic/env.py**

Replace the entire contents of `server/alembic/env.py` with:

```python
"""Alembic env — imports all ORM models for autogenerate."""
import os
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add parent dir to path so `app` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_models import Base
from app.database import DATABASE_URL

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate initial migration**

Run: `cd server && python -m alembic revision --autogenerate -m "initial schema"`

Expected: Creates `server/alembic/versions/001_initial_schema.py` (or similar timestamped name) with 4 tables: `accounts`, `devices`, `tasks`, `ui_selectors`.

- [ ] **Step 5: Review the generated migration**

Read the generated file. Verify it creates all 4 tables with the correct columns and foreign keys. If the filename is timestamped (e.g., `a1b2c3d4e5f6_initial_schema.py`), rename it to `001_initial_schema.py` for clarity.

- [ ] **Step 6: Run the migration**

Run: `cd server && python -m alembic upgrade head`

Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 001, initial schema`

Verify the database file exists:

Run: `ls -la server/app/data/dy_auto.db`

Expected: File exists with non-zero size.

- [ ] **Step 7: Commit**

```bash
git add server/alembic.ini server/alembic/
git commit -m "feat: set up Alembic with initial migration (4 tables)"
```

---

## Task 6: Seed Script — Import YAML Config into DB

**Files:**
- Create: `server/app/seed.py`

- [ ] **Step 1: Create seed script**

```python
"""Seed database from YAML config files. Idempotent — safe to run multiple times."""
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.db_models import Account, UISelector
from app.config import load_accounts_config, load_selectors_config


def seed_accounts(db: Session) -> int:
    """Import accounts from accounts.yaml. Skips existing (by id)."""
    accounts = load_accounts_config()
    added = 0
    for acc in accounts:
        existing = db.query(Account).filter(Account.id == acc["id"]).first()
        if existing:
            continue
        db.add(Account(
            id=acc["id"],
            nickname=acc.get("nickname", ""),
            douyin_id=acc.get("douyin_id", ""),
            group=acc.get("group", "default"),
            status=acc.get("status", "active"),
            daily_limits=acc.get("daily_limits", {
                "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
            }),
        ))
        added += 1
    db.commit()
    return added


def seed_selectors(db: Session) -> int:
    """Import selectors from selectors.yaml. Skips existing (by action_name + platform_version)."""
    version, selectors = load_selectors_config()
    added = 0
    for sel in selectors:
        existing = db.query(UISelector).filter(
            UISelector.action_name == sel["action_name"],
            UISelector.platform_version == sel.get("platform_version", "default"),
        ).first()
        if existing:
            # Update strategies and version if changed
            existing.strategies = sel["strategies"]
            existing.version = version
            continue
        db.add(UISelector(
            action_name=sel["action_name"],
            platform_version=sel.get("platform_version", "default"),
            strategies=sel["strategies"],
            version=version,
        ))
        added += 1
    db.commit()
    return added


def seed_all():
    """Run all seed operations. Call at startup."""
    init_db()
    db = SessionLocal()
    try:
        acc_count = seed_accounts(db)
        sel_count = seed_selectors(db)
        print(f"Seed complete: {acc_count} accounts added, {sel_count} selectors added")
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
```

- [ ] **Step 2: Run seed script**

Run: `cd server && python -m app.seed`

Expected: `Seed complete: 1 accounts added, 12 selectors added`

- [ ] **Step 3: Run seed again to verify idempotency**

Run: `cd server && python -m app.seed`

Expected: `Seed complete: 0 accounts added, 0 selectors added`

- [ ] **Step 4: Verify data in DB**

Run: `cd server && python -c "from app.database import SessionLocal; from app.db_models import Account, UISelector; db = SessionLocal(); print(f'Accounts: {db.query(Account).count()}'); print(f'Selectors: {db.query(UISelector).count()}'); db.close()"`

Expected: `Accounts: 1` and `Selectors: 12`

- [ ] **Step 5: Commit**

```bash
git add server/app/seed.py
git commit -m "feat: add seed script to import YAML config into database"
```

---

## Task 7: Refactor task_service to Use Database

**Files:**
- Rewrite: `server/app/services/task_service.py`

- [ ] **Step 1: Rewrite task_service.py**

Replace the entire contents of `server/app/services/task_service.py`:

```python
"""Task scheduling service — backed by SQLAlchemy database."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update

from app.db_models import Task as DBTask
from app.models import TaskType, TaskStatus, Task as PydanticTask

MAX_RETRIES = 3


def _db_task_to_pydantic(task: DBTask) -> PydanticTask:
    """Convert SQLAlchemy Task to Pydantic Task for API responses."""
    return PydanticTask(
        id=task.id,
        type=TaskType(task.type),
        account_id=task.account_id,
        device_id=task.device_id or "",
        params=task.params or {},
        status=TaskStatus(task.status),
        scheduled_at=task.scheduled_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        result=task.result,
        retry_count=task.retry_count,
    )


class TaskService:
    """Task scheduling service — DB-backed."""

    def create_task(
        self,
        db: Session,
        task_type: TaskType,
        account_id: str,
        params: dict,
        scheduled_at: Optional[datetime] = None,
    ) -> PydanticTask:
        db_task = DBTask(
            type=task_type.value,
            account_id=account_id,
            params=params,
            status=TaskStatus.PENDING.value,
            scheduled_at=scheduled_at,
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def get_task(self, db: Session, task_id: str) -> Optional[PydanticTask]:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            return None
        return _db_task_to_pydantic(db_task)

    def get_pending_task(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Claim a pending task using optimistic locking (UPDATE ... WHERE status='pending')."""
        # Find oldest pending task
        db_task = db.query(DBTask).filter(
            DBTask.status == TaskStatus.PENDING.value,
        ).order_by(DBTask.created_at.asc()).first()

        if not db_task:
            return None

        # Optimistic lock: atomically claim via UPDATE with WHERE clause
        result = db.execute(
            update(DBTask)
            .where(DBTask.id == db_task.id, DBTask.status == TaskStatus.PENDING.value)
            .values(status=TaskStatus.RUNNING.value, device_id=device_id, started_at=datetime.now())
        )
        db.commit()

        if result.rowcount == 0:
            # Another device claimed it first — retry
            return self.get_pending_task(db, device_id)

        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def report_result(
        self,
        db: Session,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        ui_snapshot: Optional[dict] = None,
    ) -> PydanticTask:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            raise ValueError(f"Task {task_id} not found")

        if status == TaskStatus.COMPLETED:
            db_task.status = TaskStatus.COMPLETED.value
            db_task.result = result
            db_task.completed_at = datetime.now()
        elif status == TaskStatus.FAILED:
            db_task.retry_count += 1
            if db_task.retry_count >= MAX_RETRIES:
                db_task.status = TaskStatus.FAILED.value
                db_task.result = result
                db_task.completed_at = datetime.now()
            else:
                db_task.status = TaskStatus.PENDING.value  # re-queue for retry
                db_task.device_id = None
                db_task.started_at = None

        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def list_tasks(self, db: Session, status: Optional[TaskStatus] = None, skip: int = 0, limit: int = 50) -> list[PydanticTask]:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == status.value)
        db_tasks = query.order_by(DBTask.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_task_to_pydantic(t) for t in db_tasks]

    def count_tasks(self, db: Session, status: Optional[TaskStatus] = None) -> int:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == status.value)
        return query.count()


# Module-level singleton — services are stateless, DB sessions come from get_db
task_service = TaskService()
```

- [ ] **Step 2: Verify module loads**

Run: `cd server && python -c "from app.services.task_service import task_service; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/app/services/task_service.py
git commit -m "refactor: task_service now backed by SQLAlchemy database"
```

---

## Task 8: Refactor selector_service to Use Database

**Files:**
- Rewrite: `server/app/services/selector_service.py`

- [ ] **Step 1: Rewrite selector_service.py**

Replace the entire contents of `server/app/services/selector_service.py`:

```python
"""Selector management service — backed by SQLAlchemy database."""
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import UISelector


class SelectorService:
    """UI selector management — DB-backed."""

    def get_all_selectors(self, db: Session) -> tuple[int, list[dict]]:
        """Returns (version, selectors_list). Version is max version across all selectors."""
        selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
        if not selectors:
            return 0, []
        version = max(s.version for s in selectors)
        result = []
        for s in selectors:
            result.append({
                "action_name": s.action_name,
                "platform_version": s.platform_version,
                "strategies": s.strategies,
            })
        return version, result

    def get_selector(self, db: Session, action_name: str) -> Optional[dict]:
        """Get a single selector by action_name."""
        s = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.enabled == True,
        ).first()
        if not s:
            return None
        return {
            "action_name": s.action_name,
            "platform_version": s.platform_version,
            "strategies": s.strategies,
        }

    def get_version(self, db: Session) -> int:
        """Get current selectors version."""
        selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
        if not selectors:
            return 0
        return max(s.version for s in selectors)


# Module-level singleton — stateless, DB sessions injected per call
selector_service = SelectorService()
```

- [ ] **Step 2: Verify module loads**

Run: `cd server && python -c "from app.services.selector_service import selector_service; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/app/services/selector_service.py
git commit -m "refactor: selector_service now backed by SQLAlchemy database"
```

---

## Task 9: Account CRUD Router

**Files:**
- Create: `server/app/routers/accounts.py`
- Create: `server/tests/test_accounts_api.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_accounts_api.py`:

```python
"""Account CRUD API tests."""
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, SessionLocal
from app.db_models import Base, engine

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def setup_module(module):
    """Create tables before tests."""
    Base.metadata.create_all(bind=engine)


def test_create_account():
    resp = client.post("/api/accounts", json={
        "nickname": "测试账号",
        "douyin_id": "test_douyin_001",
        "group": "nurture",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "测试账号"
    assert data["douyin_id"] == "test_douyin_001"
    assert data["group"] == "nurture"
    assert data["status"] == "active"
    assert "id" in data


def test_list_accounts():
    resp = client.get("/api/accounts", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts" in data
    assert data["total"] >= 1


def test_get_account():
    # Create one first
    create_resp = client.post("/api/accounts", json={
        "nickname": "查询测试",
        "douyin_id": "test_query",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    resp = client.get(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == account_id


def test_get_nonexistent_account():
    resp = client.get("/api/accounts/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404


def test_update_account():
    create_resp = client.post("/api/accounts", json={
        "nickname": "更新前",
        "douyin_id": "test_update",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    resp = client.put(f"/api/accounts/{account_id}", json={
        "nickname": "更新后",
        "status": "risk_controlled",
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "更新后"
    assert resp.json()["status"] == "risk_controlled"


def test_delete_account():
    create_resp = client.post("/api/accounts", json={
        "nickname": "删除测试",
        "douyin_id": "test_delete",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    resp = client.delete(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 200

    # Verify deleted
    resp = client.get(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 404


def test_auth_required():
    resp = client.get("/api/accounts")
    assert resp.status_code == 401


def test_create_account_missing_nickname():
    resp = client.post("/api/accounts", json={}, headers=HEADERS)
    assert resp.status_code == 422  # Pydantic validation error


def test_update_nonexistent_account():
    resp = client.put("/api/accounts/nonexistent-id", json={"nickname": "x"}, headers=HEADERS)
    assert resp.status_code == 404


def test_delete_nonexistent_account():
    resp = client.delete("/api/accounts/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_accounts_api.py -v`

Expected: FAIL (404 on `/api/accounts` — router not mounted yet)

- [ ] **Step 3: Create accounts router**

Create `server/app/routers/accounts.py`:

```python
"""Account management CRUD API."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Account
from app.deps import verify_device_secret

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    nickname: str
    douyin_id: str = ""
    group: str = "default"
    status: str = "active"
    daily_limits: Optional[dict[str, int]] = None


class AccountUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    douyin_id: Optional[str] = None
    group: Optional[str] = None
    status: Optional[str] = None
    daily_limits: Optional[dict[str, int]] = None
    cookie: Optional[str] = None


def _account_to_dict(acc: Account) -> dict:
    return {
        "id": acc.id,
        "nickname": acc.nickname,
        "douyin_id": acc.douyin_id,
        "group": acc.group,
        "status": acc.status,
        "daily_limits": acc.daily_limits,
        "created_at": str(acc.created_at) if acc.created_at else None,
        "updated_at": str(acc.updated_at) if acc.updated_at else None,
    }


@router.post("")
def create_account(
    request: AccountCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    acc = Account(
        nickname=request.nickname,
        douyin_id=request.douyin_id,
        group=request.group,
        status=request.status,
        daily_limits=request.daily_limits,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return _account_to_dict(acc)


@router.get("")
def list_accounts(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    total = db.query(Account).count()
    accounts = db.query(Account).order_by(Account.created_at.desc()).offset(skip).limit(limit).all()
    return {"accounts": [_account_to_dict(a) for a in accounts], "total": total}


@router.get("/{account_id}")
def get_account(
    account_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return _account_to_dict(acc)


@router.put("/{account_id}")
def update_account(
    account_id: str,
    request: AccountUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    if request.nickname is not None:
        acc.nickname = request.nickname
    if request.douyin_id is not None:
        acc.douyin_id = request.douyin_id
    if request.group is not None:
        acc.group = request.group
    if request.status is not None:
        acc.status = request.status
    if request.daily_limits is not None:
        acc.daily_limits = request.daily_limits
    if request.cookie is not None:
        acc.cookie = request.cookie

    db.commit()
    db.refresh(acc)
    return _account_to_dict(acc)


@router.delete("/{account_id}")
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()
    return {"deleted": True, "id": account_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_accounts_api.py -v`

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/accounts.py server/tests/test_accounts_api.py
git commit -m "feat: add Account CRUD API with tests"
```

---

## Task 10: Device CRUD Router

**Files:**
- Create: `server/app/routers/devices.py`
- Create: `server/tests/test_devices_api.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_devices_api.py`:

```python
"""Device CRUD API tests."""
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import Base, engine

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def test_create_device():
    resp = client.post("/api/devices", json={
        "name": "测试设备",
        "ip": "192.168.1.100",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试设备"
    assert data["ip"] == "192.168.1.100"
    assert data["status"] == "offline"
    assert "id" in data


def test_list_devices():
    resp = client.get("/api/devices", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "devices" in data
    assert data["total"] >= 1


def test_get_device():
    create_resp = client.post("/api/devices", json={"name": "查询测试"}, headers=HEADERS)
    device_id = create_resp.json()["id"]

    resp = client.get(f"/api/devices/{device_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == device_id


def test_get_nonexistent_device():
    resp = client.get("/api/devices/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404


def test_update_device():
    create_resp = client.post("/api/devices", json={"name": "更新前"}, headers=HEADERS)
    device_id = create_resp.json()["id"]

    resp = client.put(f"/api/devices/{device_id}", json={
        "name": "更新后",
        "status": "online",
        "proxy_config": {"type": "http", "host": "proxy.example.com", "port": 8080},
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["name"] == "更新后"
    assert resp.json()["status"] == "online"
    assert resp.json()["proxy_config"]["host"] == "proxy.example.com"


def test_delete_device():
    create_resp = client.post("/api/devices", json={"name": "删除测试"}, headers=HEADERS)
    device_id = create_resp.json()["id"]

    resp = client.delete(f"/api/devices/{device_id}", headers=HEADERS)
    assert resp.status_code == 200

    resp = client.get(f"/api/devices/{device_id}", headers=HEADERS)
    assert resp.status_code == 404


def test_auth_required():
    resp = client.get("/api/devices")
    assert resp.status_code == 401


def test_create_device_missing_name():
    resp = client.post("/api/devices", json={}, headers=HEADERS)
    assert resp.status_code == 422


def test_update_nonexistent_device():
    resp = client.put("/api/devices/nonexistent-id", json={"name": "x"}, headers=HEADERS)
    assert resp.status_code == 404


def test_delete_nonexistent_device():
    resp = client.delete("/api/devices/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404


def test_create_device_with_proxy():
    resp = client.post("/api/devices", json={
        "name": "proxy设备",
        "proxy_config": {"type": "http", "host": "proxy.example.com", "port": 8080},
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["proxy_config"]["host"] == "proxy.example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_devices_api.py -v`

Expected: FAIL (404 on `/api/devices`)

- [ ] **Step 3: Create devices router**

Create `server/app/routers/devices.py`:

```python
"""Device management CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Device
from app.deps import verify_device_secret

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceCreateRequest(BaseModel):
    name: str
    ip: Optional[str] = None
    bound_account_id: Optional[str] = None


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    status: Optional[str] = None
    bound_account_id: Optional[str] = None
    proxy_config: Optional[dict[str, Any]] = None


def _device_to_dict(dev: Device) -> dict:
    return {
        "id": dev.id,
        "name": dev.name,
        "ip": dev.ip,
        "status": dev.status,
        "bound_account_id": dev.bound_account_id,
        "proxy_config": dev.proxy_config,
        "last_seen_at": str(dev.last_seen_at) if dev.last_seen_at else None,
        "created_at": str(dev.created_at) if dev.created_at else None,
        "updated_at": str(dev.updated_at) if dev.updated_at else None,
    }


@router.post("")
def create_device(
    request: DeviceCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = Device(
        name=request.name,
        ip=request.ip,
        bound_account_id=request.bound_account_id,
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return _device_to_dict(dev)


@router.get("")
def list_devices(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    total = db.query(Device).count()
    devices = db.query(Device).order_by(Device.created_at.desc()).offset(skip).limit(limit).all()
    return {"devices": [_device_to_dict(d) for d in devices], "total": total}


@router.get("/{device_id}")
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_dict(dev)


@router.put("/{device_id}")
def update_device(
    device_id: str,
    request: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    if request.name is not None:
        dev.name = request.name
    if request.ip is not None:
        dev.ip = request.ip
    if request.status is not None:
        dev.status = request.status
    if request.bound_account_id is not None:
        dev.bound_account_id = request.bound_account_id
    if request.proxy_config is not None:
        dev.proxy_config = request.proxy_config

    db.commit()
    db.refresh(dev)
    return _device_to_dict(dev)


@router.delete("/{device_id}")
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(dev)
    db.commit()
    return {"deleted": True, "id": device_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_devices_api.py -v`

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/devices.py server/tests/test_devices_api.py
git commit -m "feat: add Device CRUD API with tests"
```

---

## Task 11: Wire Everything Together — Update Existing Routers + Main

**Files:**
- Modify: `server/app/routers/device.py`
- Modify: `server/app/routers/tasks.py`
- Modify: `server/app/main.py`
- Modify: `server/tests/test_device_api.py`
- Modify: `server/tests/test_e2e_flow.py`
- Modify: `server/tests/test_task_service.py`
- Modify: `server/tests/test_selector_service.py`
- Create: `server/tests/conftest.py`

- [ ] **Step 1: Create conftest.py with shared test DB fixture**

Create `server/tests/conftest.py`:

```python
"""Shared test fixtures — uses a fresh in-memory SQLite DB per test session."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db_models import Base
from app.database import get_db
from app.main import app
from app.seed import seed_accounts, seed_selectors


@pytest.fixture(scope="session", autouse=True)
def test_db():
    """Create a test database once per session, seed it, and override get_db."""
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    Base.metadata.create_all(bind=test_engine)

    # Seed with test data
    db = TestSession()
    seed_accounts(db)
    seed_selectors(db)
    db.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield test_engine
    app.dependency_overrides.clear()
    test_engine.dispose()
```

- [ ] **Step 2: Update device.py to use DB-backed services**

Replace `server/app/routers/device.py`:

```python
"""Device-facing API — poll, report, heartbeat, selectors."""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import TaskResultReport, PollResponse
from app.database import get_db
from app.deps import verify_device_secret
from app.services.task_service import task_service
from app.services.selector_service import selector_service

router = APIRouter(prefix="/api/device", tags=["device"])


@router.get("/poll", response_model=PollResponse)
def poll_tasks(
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.get_pending_task(db, device_id)
    version = selector_service.get_version(db)

    return PollResponse(
        task=task,
        selectors_version=version,
    )


@router.post("/report")
def report_result(
    report: TaskResultReport,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.report_result(
        db=db,
        task_id=report.task_id,
        status=report.status,
        result=report.result,
        ui_snapshot=report.ui_snapshot,
    )
    return task


@router.post("/heartbeat")
def heartbeat(
    body: dict,
    _: None = Depends(verify_device_secret),
):
    device_id = body.get("device_id", "")
    return {"status": "ok", "device_id": device_id}


@router.get("/selectors")
def get_selectors(
    version: int = Query(0),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):

    current_version, selectors = selector_service.get_all_selectors(db)
    if version == current_version:
        return {"version": current_version, "selectors": None, "changed": False}

    return {
        "version": current_version,
        "selectors": selectors,
        "changed": True,
    }
```

- [ ] **Step 3: Update tasks.py to use DB-backed services**

Replace `server/app/routers/tasks.py`:

```python
"""Task management API -- create, list, get tasks."""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import TaskCreateRequest, TaskStatus
from app.database import get_db
from app.deps import verify_device_secret
from app.services.task_service import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.create_task(
        db=db,
        task_type=request.type,
        account_id=request.account_id,
        params=request.params,
        scheduled_at=request.scheduled_at,
    )
    return task


@router.get("")
def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    tasks = task_service.list_tasks(db=db, status=status, skip=skip, limit=limit)
    total = task_service.count_tasks(db=db, status=status)
    return {"tasks": tasks, "total": total}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

- [ ] **Step 4: Update main.py to mount new routers and run seed at startup**

Replace `server/app/main.py`:

```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import init_db
from app.seed import seed_all
from app.routers import device, tasks, accounts, devices


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and seed. Shutdown: nothing."""
    seed_all()
    yield


app = FastAPI(
    title="抖音自动化助手",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(device.router)
app.include_router(tasks.router)
app.include_router(accounts.router)
app.include_router(devices.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.2.0"}
```

- [ ] **Step 5: Update existing test files to use conftest**

The existing tests in `test_device_api.py`, `test_e2e_flow.py`, `test_task_service.py`, and `test_selector_service.py` need updates because:
- `task_service` methods now require a `db` session parameter
- `selector_service` methods now require a `db` session parameter

Update `server/tests/test_task_service.py`:

```python
"""Task service tests — DB-backed."""
import pytest
from app.models import TaskType, TaskStatus
from app.services.task_service import task_service
from app.database import SessionLocal, get_db
from app.main import app


@pytest.fixture
def db():
    """Get a test DB session from the conftest override."""
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


def test_create_task(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 30})
    assert task.type == TaskType.NURTURE
    assert task.account_id == "acc-001"
    assert task.status == TaskStatus.PENDING


def test_get_pending_task(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    claimed = task_service.get_pending_task(db, "dev-001")
    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.status == TaskStatus.RUNNING
    assert claimed.device_id == "dev-001"


def test_no_duplicate_assignment(db):
    task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    first = task_service.get_pending_task(db, "dev-001")
    second = task_service.get_pending_task(db, "dev-002")
    assert first is not None
    # second may be None or a different task — never the same
    if second is not None:
        assert second.id != first.id


def test_report_result(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    result_task = task_service.report_result(db, task.id, TaskStatus.COMPLETED, {"success_count": 3})
    assert result_task.status == TaskStatus.COMPLETED
    assert result_task.result["success_count"] == 3


def test_report_failure_increments_retry(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    failed = task_service.report_result(db, task.id, TaskStatus.FAILED, {"details": "error"})
    assert failed.status == TaskStatus.PENDING  # re-queued
    assert failed.retry_count == 1


def test_max_retries(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    for i in range(3):
        task_service.get_pending_task(db, "dev-001")
        task = task_service.report_result(db, task.id, TaskStatus.FAILED, {"details": f"fail {i}"})
    assert task.status == TaskStatus.FAILED


def test_list_tasks(db):
    tasks = task_service.list_tasks(db)
    assert len(tasks) > 0
```

Update `server/tests/test_selector_service.py`:

```python
"""Selector service tests — DB-backed."""
import pytest
from app.services.selector_service import selector_service
from app.database import get_db
from app.main import app


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


def test_get_selectors(db):
    version, selectors = selector_service.get_all_selectors(db)
    assert version >= 1
    assert len(selectors) > 0


def test_get_selector_by_action(db):
    selector = selector_service.get_selector(db, "like_button")
    assert selector is not None
    assert selector["action_name"] == "like_button"
    assert len(selector["strategies"]) > 0


def test_get_nonexistent_selector(db):
    selector = selector_service.get_selector(db, "nonexistent_action")
    assert selector is None


def test_selectors_version(db):
    version = selector_service.get_version(db)
    assert isinstance(version, int)
    assert version >= 1
```

Update `server/tests/test_device_api.py`:

```python
"""Device API tests."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_device_poll_no_task():
    resp = client.get("/api/device/poll", params={"device_id": "dev-test"}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "selectors_version" in data


def test_device_poll_with_task():
    # Create a task first
    client.post("/api/tasks", json={
        "type": "nurture",
        "account_id": "acc-001",
        "params": {"duration": 5},
    }, headers=HEADERS)

    resp = client.get("/api/device/poll", params={"device_id": "dev-poll"}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"] is not None
    assert data["task"]["type"] == "nurture"


def test_device_report():
    # Create + poll + report
    create_resp = client.post("/api/tasks", json={
        "type": "nurture",
        "account_id": "acc-001",
        "params": {"duration": 5},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]

    client.get("/api/device/poll", params={"device_id": "dev-report"}, headers=HEADERS)

    report_resp = client.post("/api/device/report", json={
        "task_id": task_id,
        "status": "completed",
        "result": {"success_count": 1},
    }, headers=HEADERS)
    assert report_resp.status_code == 200


def test_device_auth_required():
    resp = client.get("/api/device/poll", params={"device_id": "dev-test"})
    assert resp.status_code == 401
```

Update `server/tests/test_e2e_flow.py`:

```python
"""End-to-end integration test — DB-backed."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_full_task_lifecycle():
    """Create -> poll -> report -> verify completed."""
    create_resp = client.post("/api/tasks", json={
        "type": "nurture", "account_id": "acc-001", "params": {"duration": 5},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending"

    poll_resp = client.get("/api/device/poll", params={"device_id": "dev-e2e"}, headers=HEADERS)
    assert poll_resp.json()["task"]["id"] == task_id

    client.post("/api/device/report", json={
        "task_id": task_id, "status": "completed",
        "result": {"success_count": 3, "fail_count": 0, "details": "OK"},
    }, headers=HEADERS)

    detail = client.get(f"/api/tasks/{task_id}", headers=HEADERS).json()
    assert detail["status"] == "completed"
    assert detail["result"]["success_count"] == 3


def test_full_flow_with_failure_and_retry():
    """Create -> poll -> fail -> re-poll -> succeed."""
    create_resp = client.post("/api/tasks", json={
        "type": "nurture", "account_id": "acc-001", "params": {"duration": 10},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]

    client.get("/api/device/poll", params={"device_id": "dev-retry"}, headers=HEADERS)

    client.post("/api/device/report", json={
        "task_id": task_id, "status": "failed", "result": {"details": "error"},
    }, headers=HEADERS)

    detail = client.get(f"/api/tasks/{task_id}", headers=HEADERS).json()
    assert detail["status"] == "pending"

    poll2 = client.get("/api/device/poll", params={"device_id": "dev-retry2"}, headers=HEADERS).json()
    assert poll2["task"]["id"] == task_id

    client.post("/api/device/report", json={
        "task_id": task_id, "status": "completed", "result": {"success_count": 1},
    }, headers=HEADERS)

    final = client.get(f"/api/tasks/{task_id}", headers=HEADERS).json()
    assert final["status"] == "completed"


def test_selectors_endpoint():
    resp = client.get("/api/device/selectors", params={"version": 0}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["changed"] is True
    assert data["version"] >= 1

    resp2 = client.get("/api/device/selectors", params={"version": data["version"]}, headers=HEADERS)
    assert resp2.json()["changed"] is False


def test_heartbeat():
    resp = client.post("/api/device/heartbeat", json={"device_id": "dev-test"}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 6: Run all tests**

Run: `cd server && python -m pytest tests/ -v`

Expected: All tests PASS (4 accounts + 7 devices + 7 task_service + 4 selector + 4 device_api + 4 e2e = ~30 tests)

- [ ] **Step 7: Verify seed runs on startup**

Run: `cd server && timeout 5 python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1 || true`

Expected: Console output includes `Seed complete: 0 accounts added, 0 selectors added` (already seeded from Task 5)

- [ ] **Step 8: Commit**

```bash
git add server/app/routers/device.py server/app/routers/tasks.py server/app/main.py
git add server/tests/conftest.py server/tests/test_device_api.py server/tests/test_e2e_flow.py
git add server/tests/test_task_service.py server/tests/test_selector_service.py
git commit -m "refactor: wire all routers to DB-backed services, update tests for DB sessions"
```

---

## Task 12: End-to-End Verification

- [ ] **Step 1: Run full test suite**

Run: `cd server && python -m pytest tests/ -v --tb=short`

Expected: All tests PASS

- [ ] **Step 2: Manual API smoke test**

```bash
# Start server
cd server && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Create account
curl -X POST http://localhost:8000/api/accounts \
  -H "Content-Type: application/json" \
  -H "X-Device-Secret: change-me-to-a-random-string" \
  -d '{"nickname": "手动测试", "douyin_id": "manual_test"}'

# List accounts
curl http://localhost:8000/api/accounts \
  -H "X-Device-Secret: change-me-to-a-random-string"

# Create device
curl -X POST http://localhost:8000/api/devices \
  -H "Content-Type: application/json" \
  -H "X-Device-Secret: change-me-to-a-random-string" \
  -d '{"name": "手动测试设备"}'

# Create task and poll
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-Device-Secret: change-me-to-a-random-string" \
  -d '{"type": "nurture", "account_id": "acc-001", "params": {"duration": 5}}'

curl "http://localhost:8000/api/device/poll?device_id=manual-test" \
  -H "X-Device-Secret: change-me-to-a-random-string"
```

- [ ] **Step 3: Verify DB file exists and has data**

Run: `cd server && python -c "from app.database import SessionLocal; from app.db_models import Account, Device, Task, UISelector; db = SessionLocal(); print(f'Accounts: {db.query(Account).count()}, Devices: {db.query(Device).count()}, Tasks: {db.query(Task).count()}, Selectors: {db.query(UISelector).count()}'); db.close()"`

Expected: Non-zero counts for all tables.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "chore: Phase 1 complete — database layer + CRUD APIs"
```

---

## Task Dependency Graph

```
Task 1 (Dependencies)
  └─> Task 2 (ORM Models)
       └─> Task 3 (Database Session)
            ├─> Task 4 (Shared Auth Deps)
            ├─> Task 5 (Alembic)
            └─> Task 6 (Seed Script)
                 └─> Task 7 (Refactor task_service)
                 └─> Task 8 (Refactor selector_service)
                      └─> Task 9 (Accounts CRUD) [parallel]
                      └─> Task 10 (Devices CRUD) [parallel]
                           └─> Task 11 (Wire together + update tests)
                                └─> Task 12 (E2E verification)
```

---

## NOT in Scope (Deferred to Later Phases)

| Item | Phase | Rationale |
|------|-------|-----------|
| Cookie encryption (AES-256-GCM) | Phase 2+ | MVP stores cookies in plaintext, encryption is a security hardening step |
| JWT authentication for Web dashboard | Phase 5 | No web dashboard in Phase 1 |
| HMAC-SHA256 device auth | Phase 2+ | Current shared-secret auth works for single-device |
| Task timeout recovery (cron job) | Phase 2+ | Requires background scheduler, not critical for DB migration |
| Daily operation quota enforcement | Phase 2+ | Needs daily_stats table + scheduler |
| Content templates table | Phase 6 | Only needed for AI content generation |
| Operation logs table | Phase 7 | Only needed for audit/logging |

## What Already Exists

| Existing Code | Reused? | Notes |
|---------------|---------|-------|
| Pydantic models (`TaskType`, `TaskStatus`, `Task`) | Yes | Kept for API validation, coexists with SQLAlchemy models |
| YAML config loading (`load_accounts_config`, `load_selectors_config`) | Yes | Seed script calls them directly |
| Router auth pattern (`_verify_device_secret`) | Refactored | Extracted to shared `app/deps.py` |
| `task_service` / `selector_service` interfaces | Yes | Same method signatures, internals rewritten for DB |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 4 issues found, 0 critical gaps |

- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED — ready to implement
| PostgreSQL migration testing | Phase 2+ | SQLite is sufficient for Phase 1, PG testing is a config change |
