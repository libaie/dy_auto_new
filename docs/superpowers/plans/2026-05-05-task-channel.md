# Task Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a channel-based concurrent keyword task distribution system that coordinates multiple devices to execute search tasks in parallel, with risk control awareness and stale recovery.

**Architecture:** New `Channel` + `ChannelItem` ORM tables as a queue layer above the existing `Task` system. Devices claim channel items via the existing poll endpoint; tasks are created lazily on claim. Channel completion uses atomic SQL to avoid race conditions. Risk control events auto-skip pending items for affected accounts.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite (WAL mode), Vue 3.5, Tailwind CSS v4, Headless UI

---

## File Structure

| File | Responsibility |
|------|---------------|
| `server/app/database.py` | SQLite WAL mode pragma (existing, add listener) |
| `server/app/db_models.py` | Channel + ChannelItem ORM models (existing, add models) |
| `server/app/models.py` | Channel Pydantic request/response schemas (existing, add schemas) |
| `server/app/services/channel_service.py` | **NEW** — Channel CRUD, claim, complete, stale recovery, risk联动 |
| `server/app/services/task_service.py` | Modify `get_pending_task()` to check channels first (existing) |
| `server/app/routers/channels.py` | **NEW** — Admin channel management endpoints |
| `server/app/routers/device.py` | Modify `risk-report` to联动通道 (existing) |
| `server/app/ws_manager.py` | Add channel event broadcast methods (existing) |
| `server/tests/conftest.py` | Shared test fixtures (db, setup helpers) |
| `server/tests/test_channel_service.py` | **NEW** — Channel service unit + concurrency tests |
| `server/tests/test_channel_api.py` | **NEW** — Channel admin API endpoint tests |
| `web/src/api/channels.js` | **NEW** — Channel API client |
| `web/src/views/ChannelsPage.vue` | **NEW** — Channel management page |
| `web/src/components/ChannelCard.vue` | **NEW** — Channel card component |
| `web/src/components/CreateChannelDialog.vue` | **NEW** — Create channel dialog |
| `web/src/components/ChannelDetail.vue` | **NEW** — Channel detail dialog |
| `web/src/router/index.js` | Add `/channels` route (existing) |
| `web/src/views/AdminLayout.vue` | Add sidebar nav entry (existing) |

---

### Task 1: SQLite WAL Mode

**Files:**
- Modify: `server/app/database.py:22-23`
- Test: `server/tests/test_database.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_database.py
"""Database configuration tests."""
from sqlalchemy import text
from app.database import engine


def test_sqlite_wal_mode():
    """SQLite should be in WAL journal mode for concurrent writes."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert result == "wal", f"Expected WAL mode, got {result}"


def test_sqlite_busy_timeout():
    """SQLite busy_timeout should be set to avoid SQLITE_BUSY errors."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert result >= 5000, f"Expected busy_timeout >= 5000, got {result}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_database.py -v`
Expected: FAIL — WAL mode is not configured, busy_timeout is 0

- [ ] **Step 3: Implement WAL mode**

Edit `server/app/database.py`, after line 22 (`engine = create_engine(...)`) add:

```python
from sqlalchemy import event

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/database.py server/tests/test_database.py
git commit -m "feat: enable SQLite WAL mode and busy_timeout for concurrent access"
```

---

### Task 1b: Shared Test Fixtures (conftest.py)

**Files:**
- Create: `server/tests/conftest.py`

- [ ] **Step 1: Create conftest.py with shared fixtures**

```python
# server/tests/conftest.py
"""Shared test fixtures for channel tests."""
import pytest
from app.database import get_db
from app.main import app
from app.db_models import Account, AccountGroup, AccountGroupMember


@pytest.fixture
def db():
    """Provide a DB session that rolls back after each test."""
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    session.rollback()
    gen.close()


def setup_group(db, group_id="grp-001", account_ids=None):
    """Helper: create a group with active accounts."""
    if account_ids is None:
        account_ids = ["acc-001", "acc-002"]
    group = AccountGroup(id=group_id, name=f"test-{group_id}")
    db.add(group)
    for aid in account_ids:
        acc = Account(id=aid, nickname=f"nick-{aid}", status="active")
        db.add(acc)
        db.add(AccountGroupMember(group_id=group_id, account_id=aid))
    db.flush()
    return group
```

- [ ] **Step 2: Commit**

```bash
git add server/tests/conftest.py
git commit -m "test: add shared test fixtures for channel tests"
```

---

### Task 2: Channel ORM Models

**Files:**
- Modify: `server/app/db_models.py`
- Test: `server/tests/test_channel_models.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_channel_models.py
"""Channel and ChannelItem ORM model tests."""
import pytest
from app.database import get_db
from app.main import app
from app.db_models import Channel, ChannelItem, Account, AccountGroup, AccountGroupMember


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    session.rollback()
    gen.close()


def _create_group_with_accounts(db, group_name, account_ids):
    group = AccountGroup(id=f"grp-{group_name}", name=group_name)
    db.add(group)
    for aid in account_ids:
        acc = Account(id=aid, nickname=f"acc-{aid}")
        db.add(acc)
        member = AccountGroupMember(group_id=group.id, account_id=aid)
        db.add(member)
    db.flush()
    return group


def test_create_channel(db):
    group = _create_group_with_accounts(db, "test-ch", ["a1", "a2"])
    ch = Channel(
        id="ch-001",
        group_id=group.id,
        task_type="search_comment",
        status="active",
        account_mode="round_robin",
        params_template={"content": "hi", "count": 5},
        cooldown_seconds=300,
        delay_range=[3000, 8000],
        max_keywords=500,
    )
    db.add(ch)
    db.flush()
    assert ch.id == "ch-001"
    assert ch.status == "active"
    assert ch.deleted_at is None


def test_create_channel_item(db):
    group = _create_group_with_accounts(db, "test-ci", ["a1"])
    ch = Channel(id="ch-002", group_id=group.id, task_type="search_like",
                 status="active", account_mode="single_account", account_id="a1",
                 params_template={"count": 10})
    db.add(ch)
    item = ChannelItem(
        id="ci-001",
        channel_id="ch-002",
        keyword="美食",
        account_id="a1",
        status="pending",
        queue_position=0,
    )
    db.add(item)
    db.flush()
    assert item.status == "pending"
    assert item.assigned_device_id is None
    assert item.task_id is None


def test_channel_item_indexes(db):
    """Verify composite index exists on (channel_id, status)."""
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(db.bind)
    indexes = {idx["name"] for idx in insp.get_indexes("channel_items")}
    assert "ix_channel_items_channel_status" in indexes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_channel_models.py -v`
Expected: FAIL — Channel model does not exist

- [ ] **Step 3: Implement Channel and ChannelItem models**

Add to the end of `server/app/db_models.py` (before the file ends):

```python
class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="RESTRICT"), nullable=False)
    task_type = Column(String(30), nullable=False)  # search_comment, search_like, search_dm, reply_comment
    status = Column(String(20), nullable=False, default="active")  # active, paused, completed, cancelled
    account_mode = Column(String(20), nullable=False, default="round_robin")  # single_account, round_robin
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=True)  # single_account mode
    params_template = Column(JSON, nullable=False, default=dict)
    cooldown_seconds = Column(Integer, nullable=False, default=300)
    delay_range = Column(JSON, nullable=False, default=lambda: [3000, 8000])
    max_keywords = Column(Integer, nullable=False, default=500)
    current_account_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    group = relationship("AccountGroup")
    account = relationship("Account")
    items = relationship("ChannelItem", back_populates="channel", cascade="all, delete-orphan")


class ChannelItem(Base):
    __tablename__ = "channel_items"
    __table_args__ = (
        Index("ix_channel_items_channel_status", "channel_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    channel_id = Column(String(36), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(200), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, assigned, completed, failed, skipped
    assigned_device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)  # 设备领取时间，用于 stale recovery
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    queue_position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="items")
    account = relationship("Account")
    device = relationship("Device")
    task = relationship("Task")
```

Also add the `Index` import at the top of `db_models.py`:

```python
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean,
    JSON, ForeignKey, UniqueConstraint, Index,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_channel_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/db_models.py server/tests/test_channel_models.py
git commit -m "feat: add Channel and ChannelItem ORM models with indexes"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Modify: `server/app/models.py`

- [ ] **Step 1: Add Channel Pydantic models**

Add to the end of `server/app/models.py`:

```python
# --- 通道 (Channel) ---

class ChannelCreate(BaseModel):
    group_id: str
    task_type: TaskType
    account_mode: str = Field(default="round_robin", pattern="^(single_account|round_robin)$")
    account_id: Optional[str] = None
    keywords: list[str] = Field(..., min_length=1, max_length=500)
    params_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = Field(default=300, ge=30, le=3600)
    delay_range: list[int] = Field(default=[3000, 8000])

    @model_validator(mode="after")
    def validate_single_account(self):
        if self.account_mode == "single_account" and not self.account_id:
            raise ValueError("single_account 模式下 account_id 必填")
        if len(self.delay_range) != 2 or self.delay_range[0] >= self.delay_range[1]:
            raise ValueError("delay_range 必须为 [min, max] 且 min < max")
        return self


class ChannelUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(paused|active|cancelled)$")


class ChannelItemUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(skipped|pending)$")


class ChannelAppendItems(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=500)


class ChannelItemResponse(BaseModel):
    id: str
    keyword: str
    account_id: str
    account_nickname: str = ""
    status: str
    assigned_device_id: str = ""
    device_name: str = ""
    task_id: str = ""
    queue_position: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ChannelResponse(BaseModel):
    id: str
    group_id: str
    group_name: str = ""
    task_type: str
    status: str
    account_mode: str
    account_id: str = ""
    params_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = 300
    delay_range: list[int] = Field(default=[3000, 8000])
    total: int = 0
    pending: int = 0
    assigned: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ChannelDetailResponse(ChannelResponse):
    items: list[ChannelItemResponse] = []
```

- [ ] **Step 2: Verify import works**

Run: `cd server && python -c "from app.models import ChannelCreate, ChannelResponse; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add server/app/models.py
git commit -m "feat: add Channel Pydantic request/response schemas"
```

---

### Task 4: Channel Service — Create

**Files:**
- Create: `server/app/services/channel_service.py`
- Test: `server/tests/test_channel_service.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_channel_service.py
"""Channel service tests."""
import pytest
from app.database import get_db
from app.main import app
from app.db_models import Account, AccountGroup, AccountGroupMember, Channel, ChannelItem
from app.services.channel_service import channel_service


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    session.rollback()
    gen.close()


def _setup_group(db, group_id="grp-001", account_ids=None):
    if account_ids is None:
        account_ids = ["acc-001", "acc-002"]
    group = AccountGroup(id=group_id, name=f"test-{group_id}")
    db.add(group)
    for aid in account_ids:
        acc = Account(id=aid, nickname=f"nick-{aid}", status="active")
        db.add(acc)
        db.add(AccountGroupMember(group_id=group_id, account_id=aid))
    db.flush()
    return group


def test_create_channel_round_robin(db):
    _setup_group(db)
    ch = channel_service.create_channel(
        db,
        group_id="grp-001",
        task_type="search_comment",
        account_mode="round_robin",
        keywords=["美食", "旅游", "健身"],
        params_template={"content": "好棒", "count": 5},
    )
    assert ch.status == "active"
    assert ch.total == 3
    # Check items were created with round-robin account assignment
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()
    assert len(items) == 3
    assert items[0].account_id != items[1].account_id or items[1].account_id != items[2].account_id


def test_create_channel_single_account(db):
    _setup_group(db)
    ch = channel_service.create_channel(
        db,
        group_id="grp-001",
        task_type="search_like",
        account_mode="single_account",
        account_id="acc-001",
        keywords=["a", "b"],
        params_template={"count": 10},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.account_id == "acc-001" for i in items)


def test_create_channel_max_keywords_exceeded(db):
    _setup_group(db)
    with pytest.raises(ValueError, match="最多"):
        channel_service.create_channel(
            db,
            group_id="grp-001",
            task_type="search_comment",
            account_mode="round_robin",
            keywords=["k"] * 501,
            params_template={},
        )


def test_create_channel_skips_non_active_accounts(db):
    """round_robin should skip risk_controlled/banned accounts."""
    group = AccountGroup(id="grp-002", name="mixed")
    db.add(group)
    db.add(Account(id="acc-active", nickname="active", status="active"))
    db.add(Account(id="acc-risk", nickname="risk", status="risk_controlled"))
    db.add(AccountGroupMember(group_id="grp-002", account_id="acc-active"))
    db.add(AccountGroupMember(group_id="grp-002", account_id="acc-risk"))
    db.flush()

    ch = channel_service.create_channel(
        db,
        group_id="grp-002",
        task_type="search_comment",
        account_mode="round_robin",
        keywords=["a", "b", "c"],
        params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.account_id == "acc-active" for i in items)


def test_create_channel_invalid_group(db):
    """Should raise ValueError for non-existent group."""
    with pytest.raises(ValueError, match="不存在"):
        channel_service.create_channel(
            db, group_id="nonexistent", task_type="search_comment",
            account_mode="round_robin", keywords=["a"], params_template={},
        )


def test_create_channel_no_active_accounts(db):
    """Should raise ValueError when group has no active accounts."""
    group = AccountGroup(id="grp-empty", name="empty")
    db.add(group)
    db.add(Account(id="acc-banned", nickname="banned", status="banned"))
    db.add(AccountGroupMember(group_id="grp-empty", account_id="acc-banned"))
    db.flush()

    with pytest.raises(ValueError, match="活跃账号"):
        channel_service.create_channel(
            db, group_id="grp-empty", task_type="search_comment",
            account_mode="round_robin", keywords=["a"], params_template={},
        )


def test_create_channel_single_account_not_active(db):
    """Should raise ValueError when specified account is not active."""
    _setup_group(db)
    db.add(Account(id="acc-risk-2", nickname="risk", status="risk_controlled"))
    db.add(AccountGroupMember(group_id="grp-001", account_id="acc-risk-2"))
    db.flush()

    with pytest.raises(ValueError, match="非 active"):
        channel_service.create_channel(
            db, group_id="grp-001", task_type="search_comment",
            account_mode="single_account", account_id="acc-risk-2",
            keywords=["a"], params_template={},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_channel_service.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement channel_service.py**

```python
# server/app/services/channel_service.py
"""Channel service — create, claim, complete, stale recovery, risk control."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update, and_, not_, exists

from app.db_models import (
    Channel, ChannelItem, Account, AccountGroupMember,
    Task as DBTask, Device as DBDevice,
)
from app.models import TaskType


MAX_KEYWORDS = 500


def _get_active_accounts(db: Session, group_id: str) -> list[Account]:
    """Get active accounts in a group, ordered by today's usage (ascending)."""
    members = db.query(AccountGroupMember).filter(
        AccountGroupMember.group_id == group_id
    ).all()
    account_ids = [m.account_id for m in members]
    if not account_ids:
        return []
    accounts = db.query(Account).filter(
        Account.id.in_(account_ids),
        Account.status == "active",
    ).all()
    return accounts


class ChannelService:

    def create_channel(
        self,
        db: Session,
        group_id: str,
        task_type: str,
        account_mode: str,
        keywords: list[str],
        params_template: dict,
        account_id: Optional[str] = None,
        cooldown_seconds: int = 300,
        delay_range: list[int] = None,
    ) -> Channel:
        if len(keywords) > MAX_KEYWORDS:
            raise ValueError(f"关键词最多 {MAX_KEYWORDS} 个，当前 {len(keywords)} 个")

        if delay_range is None:
            delay_range = [3000, 8000]

        # Validate group exists
        from app.db_models import AccountGroup
        group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
        if not group:
            raise ValueError(f"分组 {group_id} 不存在")

        # Get active accounts for distribution
        active_accounts = _get_active_accounts(db, group_id)
        if not active_accounts:
            raise ValueError("该分组内没有活跃账号")

        if account_mode == "single_account":
            if not account_id:
                raise ValueError("single_account 模式下 account_id 必填")
            acc = db.query(Account).filter(Account.id == account_id, Account.status == "active").first()
            if not acc:
                raise ValueError(f"账号 {account_id} 不存在或非 active 状态")
            item_accounts = [account_id] * len(keywords)
        else:
            # round_robin: distribute keywords across active accounts, prefer least-used
            item_accounts = self._round_robin_assign(db, keywords, active_accounts)

        ch = Channel(
            group_id=group_id,
            task_type=task_type,
            status="active",
            account_mode=account_mode,
            account_id=account_id,
            params_template=params_template,
            cooldown_seconds=cooldown_seconds,
            delay_range=delay_range,
            max_keywords=MAX_KEYWORDS,
        )
        db.add(ch)
        db.flush()  # get ch.id

        for i, keyword in enumerate(keywords):
            item = ChannelItem(
                channel_id=ch.id,
                keyword=keyword,
                account_id=item_accounts[i],
                status="pending",
                queue_position=i,
            )
            db.add(item)

        db.commit()
        db.refresh(ch)
        return ch

    def _round_robin_assign(self, db: Session, keywords: list[str], accounts: list[Account]) -> list[str]:
        """Assign accounts to keywords using round-robin, preferring least-used today."""
        if not accounts:
            raise ValueError("无可用账号")

        # Sort accounts by today's total usage (ascending) — prefer least-used
        from app.services.stats_service import stats_service
        account_usage = []
        for acc in accounts:
            counts = stats_service.get_today_counts(db, acc.id)
            total = sum(counts.values())
            account_usage.append((acc, total))
        account_usage.sort(key=lambda x: x[1])  # ascending by usage

        sorted_accounts = [acc for acc, _ in account_usage]
        result = []
        for i in range(len(keywords)):
            acc = sorted_accounts[i % len(sorted_accounts)]
            result.append(acc.id)
        return result

    def get_channel(self, db: Session, channel_id: str) -> Optional[Channel]:
        return db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.deleted_at.is_(None),
        ).first()

    def list_channels(self, db: Session) -> list[Channel]:
        return db.query(Channel).filter(
            Channel.deleted_at.is_(None),
        ).order_by(Channel.created_at.desc()).all()

    def get_channel_stats(self, db: Session, channel_id: str) -> dict:
        items = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).all()
        stats = {"total": len(items), "pending": 0, "assigned": 0, "completed": 0, "failed": 0, "skipped": 0}
        for item in items:
            if item.status in stats:
                stats[item.status] += 1
        return stats

    def get_channels_stats_batch(self, db: Session, channel_ids: list[str]) -> dict[str, dict]:
        """Batch query stats for multiple channels. Returns {channel_id: stats_dict}."""
        from sqlalchemy import func
        if not channel_ids:
            return {}
        rows = db.query(
            ChannelItem.channel_id,
            ChannelItem.status,
            func.count(ChannelItem.id).label("cnt"),
        ).filter(
            ChannelItem.channel_id.in_(channel_ids),
        ).group_by(ChannelItem.channel_id, ChannelItem.status).all()

        result = {cid: {"total": 0, "pending": 0, "assigned": 0, "completed": 0, "failed": 0, "skipped": 0} for cid in channel_ids}
        for channel_id, status, cnt in rows:
            result[channel_id]["total"] += cnt
            if status in result[channel_id]:
                result[channel_id][status] = cnt
        return result


channel_service = ChannelService()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_channel_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add server/app/services/channel_service.py server/tests/test_channel_service.py
git commit -m "feat: add channel service with create and round-robin distribution"
```

---

### Task 5: Channel Service — Claim (Core Distribution)

**Files:**
- Modify: `server/app/services/channel_service.py`
- Modify: `server/tests/test_channel_service.py`

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_channel_service.py`:

```python
def test_claim_pending_item(db):
    """Device should be able to claim a pending channel item."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["美食"], params_template={"content": "hi", "count": 5},
    )
    # Register a device
    from app.db_models import Device
    db.add(Device(id="dev-001", name="test-device", status="online"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-001")
    assert result is not None
    task, channel_item_id = result
    assert task.type == "search_comment"
    assert task.account_id == "acc-001"

    item = db.query(ChannelItem).filter(ChannelItem.id == channel_item_id).first()
    assert item.status == "assigned"
    assert item.assigned_device_id == "dev-001"
    assert item.task_id == task.id


def test_claim_respects_account_status_filter(db):
    """Should not claim items for risk_controlled accounts."""
    group = AccountGroup(id="grp-risk", name="risk-group")
    db.add(group)
    db.add(Account(id="acc-risk", nickname="risk", status="risk_controlled"))
    db.add(AccountGroupMember(group_id="grp-risk", account_id="acc-risk"))
    db.flush()

    ch = Channel(id="ch-risk", group_id="grp-risk", task_type="search_comment",
                 status="active", account_mode="single_account", account_id="acc-risk",
                 params_template={})
    db.add(ch)
    db.add(ChannelItem(id="ci-risk", channel_id="ch-risk", keyword="test",
                       account_id="acc-risk", status="pending", queue_position=0))
    db.flush()

    from app.db_models import Device
    db.add(Device(id="dev-risk", name="dev", status="online"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-risk")
    assert result is None  # account is risk_controlled, should be skipped


def test_claim_respects_per_account_concurrency(db):
    """Should not assign second item to account that already has running channel task."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["a", "b"], params_template={"content": "x", "count": 1},
    )
    from app.db_models import Device
    db.add(Device(id="dev-c1", name="c1", status="online"))
    db.add(Device(id="dev-c2", name="c2", status="online"))
    db.flush()

    # First claim should succeed
    result1 = channel_service.claim_channel_item(db, "dev-c1")
    assert result1 is not None

    # Second claim should fail (acc-001 already has running channel task)
    result2 = channel_service.claim_channel_item(db, "dev-c2")
    assert result2 is None


def test_claim_returns_none_when_empty(db):
    """Should return None when no pending items."""
    from app.db_models import Device
    db.add(Device(id="dev-empty", name="empty", status="online"))
    db.flush()
    result = channel_service.claim_channel_item(db, "dev-empty")
    assert result is None


def test_claim_stale_recovery(db):
    """Items assigned > 10 min ago should auto-revert to pending."""
    from datetime import timedelta
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["stale-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    item = items[0]
    # Simulate stale assignment: set assigned_at to 11 minutes ago
    from app.db_models import Device
    db.add(Device(id="dev-stale", name="stale", status="online"))
    db.flush()
    item.status = "assigned"
    item.assigned_device_id = "dev-stale"
    item.assigned_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    db.flush()

    # New device claims — should trigger stale recovery first
    db.add(Device(id="dev-new", name="new", status="online"))
    db.flush()
    result = channel_service.claim_channel_item(db, "dev-new")
    assert result is not None  # stale item recovered, new device claims it

    db.refresh(item)
    assert item.status == "assigned"
    assert item.assigned_device_id == "dev-new"


def test_claim_cooldown_filtering(db):
    """Should not claim item if account is within cooldown period."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["cd-a", "cd-b"], params_template={},
        cooldown_seconds=600,  # 10 min cooldown
    )
    from app.db_models import Device
    db.add(Device(id="dev-cd1", name="cd1", status="online"))
    db.add(Device(id="dev-cd2", name="cd2", status="online"))
    db.flush()

    # First claim succeeds
    result1 = channel_service.claim_channel_item(db, "dev-cd1")
    assert result1 is not None

    # Complete the first item
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()
    items[0].status = "completed"
    items[0].completed_at = datetime.now(timezone.utc)
    db.flush()

    # Second claim should be blocked by cooldown (600s, but just completed)
    result2 = channel_service.claim_channel_item(db, "dev-cd2")
    assert result2 is None  # cooldown blocks


def test_claim_respects_bound_account_routing(db):
    """Bound device should only claim items for its bound account."""
    group = AccountGroup(id="grp-bound", name="bound-group")
    db.add(group)
    db.add(Account(id="acc-bound-1", nickname="b1", status="active"))
    db.add(Account(id="acc-bound-2", nickname="b2", status="active"))
    db.add(AccountGroupMember(group_id="grp-bound", account_id="acc-bound-1"))
    db.add(AccountGroupMember(group_id="grp-bound", account_id="acc-bound-2"))
    db.flush()

    ch = Channel(id="ch-bound", group_id="grp-bound", task_type="search_comment",
                 status="active", account_mode="round_robin",
                 params_template={})
    db.add(ch)
    db.add(ChannelItem(id="ci-b1", channel_id="ch-bound", keyword="kw1",
                       account_id="acc-bound-1", status="pending", queue_position=0))
    db.add(ChannelItem(id="ci-b2", channel_id="ch-bound", keyword="kw2",
                       account_id="acc-bound-2", status="pending", queue_position=1))
    db.flush()

    # Device bound to acc-bound-1
    from app.db_models import Device
    db.add(Device(id="dev-bound", name="bound", status="online", bound_account_id="acc-bound-1"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-bound")
    assert result is not None
    task, item_id = result
    assert task.account_id == "acc-bound-1"  # can only claim its own account's items


def test_claim_concurrent_optimistic_lock(db):
    """Two devices trying to claim the same item — only one succeeds."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["concurrent"], params_template={},
    )
    from app.db_models import Device
    db.add(Device(id="dev-c1", name="c1", status="online"))
    db.add(Device(id="dev-c2", name="c2", status="online"))
    db.flush()

    # Both try to claim — optimistic lock ensures only one succeeds
    result1 = channel_service.claim_channel_item(db, "dev-c1")
    result2 = channel_service.claim_channel_item(db, "dev-c2")
    assert result1 is not None
    assert result2 is None  # item already claimed


def test_claim_respects_quota_limit(db):
    """Should not claim item if account has exceeded daily quota."""
    from app.services.stats_service import stats_service
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["quota-kw"], params_template={},
    )
    from app.db_models import Device
    db.add(Device(id="dev-quota", name="quota", status="online"))
    db.flush()

    # Exhaust daily comment quota (default 20)
    for _ in range(20):
        stats_service.increment(db, "acc-001", "search_comment")
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-quota")
    assert result is None  # quota exceeded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_channel_service.py::test_claim_pending_item -v`
Expected: FAIL — claim_channel_item not found

- [ ] **Step 3: Implement claim_channel_item**

Add to `ChannelService` class in `server/app/services/channel_service.py`:

```python
    def claim_channel_item(self, db: Session, device_id: str) -> Optional[tuple]:
        """Claim a pending channel item. Returns (PydanticTask, channel_item_id) or None.

        Filters:
        - Channel.status = 'active', deleted_at IS NULL
        - ChannelItem.status = 'pending'
        - Account.status = 'active'
        - Per-account concurrency: no other assigned item for same account in active channels
        - Cooldown: last completed task for this account >= cooldown_seconds ago
        - Quota: account has remaining daily quota for this task type
        - Routing: respect bound_account_id (same logic as task_service)
        """
        from app.services.task_service import _db_task_to_pydantic
        from app.services.stats_service import stats_service
        from app.models import TaskType, TaskStatus

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Stale recovery: reset items assigned > 10 min ago (uses assigned_at)
        stale_threshold = datetime.fromtimestamp(
            now.timestamp() - 600, tz=timezone.utc
        ).replace(tzinfo=None)
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.status == "assigned",
                ChannelItem.assigned_at.isnot(None),
                ChannelItem.assigned_at < stale_threshold,
            )
            .values(status="pending", assigned_device_id=None, assigned_at=None, task_id=None)
        )

        # Find active channels with pending items
        active_channels = db.query(Channel).filter(
            Channel.status == "active",
            Channel.deleted_at.is_(None),
        ).all()

        if not active_channels:
            return None

        channel_ids = [ch.id for ch in active_channels]
        channel_map = {ch.id: ch for ch in active_channels}

        # Build routing filter based on device's bound_account_id
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        bound_account_id = device.bound_account_id if device else None

        # Get pending items from active channels
        candidates = db.query(ChannelItem).filter(
            ChannelItem.channel_id.in_(channel_ids),
            ChannelItem.status == "pending",
        ).order_by(ChannelItem.queue_position.asc()).limit(10).all()

        for item in candidates:
            ch = channel_map[item.channel_id]

            # Filter: account must be active
            account = db.query(Account).filter(Account.id == item.account_id).first()
            if not account or account.status != "active":
                continue

            # Filter: routing (bound device can only claim its account's items)
            if bound_account_id and item.account_id != bound_account_id:
                continue

            # Filter: per-account concurrency (no other assigned item for this account)
            running = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "assigned",
                ChannelItem.channel_id.in_(channel_ids),
            ).first()
            if running:
                continue

            # Filter: cooldown
            last_completed = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "completed",
                ChannelItem.completed_at.isnot(None),
            ).order_by(ChannelItem.completed_at.desc()).first()
            if last_completed and ch.cooldown_seconds > 0:
                elapsed = (now - last_completed.completed_at.replace(tzinfo=None)).total_seconds()
                if elapsed < ch.cooldown_seconds:
                    continue

            # Filter: daily quota
            if not stats_service.check_quota(db, item.account_id, ch.task_type):
                continue

            # Optimistic lock: claim the item
            result = db.execute(
                update(ChannelItem)
                .where(ChannelItem.id == item.id, ChannelItem.status == "pending")
                .values(
                    status="assigned",
                    assigned_device_id=device_id,
                    assigned_at=now,
                )
            )
            if result.rowcount == 0:
                continue  # another device claimed it

            # Flush-only Task creation (no commit)
            params = dict(ch.params_template or {})
            params["keyword"] = item.keyword
            task = DBTask(
                type=ch.task_type,
                account_id=item.account_id,
                device_id=device_id,
                params=params,
                status=TaskStatus.PENDING.value,
            )
            db.add(task)
            db.flush()

            # Link task to channel item
            item.task_id = task.id
            db.flush()

            return (_db_task_to_pydantic(task), item.id)

        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_channel_service.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add server/app/services/channel_service.py server/tests/test_channel_service.py
git commit -m "feat: add channel item claim with routing, concurrency, cooldown filters"
```

---

### Task 6: Channel Service — Complete, Stale Recovery, Risk Control

**Files:**
- Modify: `server/app/services/channel_service.py`
- Modify: `server/tests/test_channel_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_channel_service.py`:

```python
def test_complete_item_marks_channel_completed_when_all_done(db):
    """Channel should be marked completed when all items are terminal."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["only-one"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert len(items) == 1

    channel_service.complete_item(db, items[0].id, "completed")

    db.refresh(ch)
    assert ch.status == "completed"
    assert ch.completed_at is not None


def test_complete_item_not_completed_when_items_remain(db):
    """Channel should stay active when items remain."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["a", "b"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()

    channel_service.complete_item(db, items[0].id, "completed")

    db.refresh(ch)
    assert ch.status == "active"


def test_complete_item_with_retry_rollback(db):
    """When task retries, channel item should roll back to pending."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["retry-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    item = items[0]
    item.status = "assigned"
    item.assigned_device_id = "dev-001"
    db.flush()

    # Simulate task retry (re-queue)
    channel_service.complete_item(db, item.id, "failed", retrying=True)

    db.refresh(item)
    assert item.status == "pending"
    assert item.assigned_device_id is None


def test_risk_control_skips_pending_items(db):
    """Risk control event should skip all pending items for the account."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["a", "b", "c"], params_template={},
    )

    channel_service.on_risk_control(db, "acc-001")

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.status == "skipped" for i in items)


def test_cancel_channel_skips_pending_items(db):
    """Cancelling a channel should skip all pending items."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["x", "y"], params_template={},
    )

    channel_service.update_channel_status(db, ch.id, "cancelled")

    db.refresh(ch)
    assert ch.status == "cancelled"
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.status == "skipped" for i in items)


def test_pause_and_resume_channel(db):
    """Pause and resume a channel."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["pause-kw"], params_template={},
    )

    channel_service.update_channel_status(db, ch.id, "paused")
    db.refresh(ch)
    assert ch.status == "paused"

    channel_service.update_channel_status(db, ch.id, "active")
    db.refresh(ch)
    assert ch.status == "active"


def test_invalid_status_transition(db):
    """Should raise ValueError for invalid status transitions."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["inv-kw"], params_template={},
    )

    with pytest.raises(ValueError, match="不允许"):
        channel_service.update_channel_status(db, ch.id, "completed")  # can't go active→completed


def test_soft_delete_channel(db):
    """Soft delete should set deleted_at and skip pending items."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["del-a", "del-b"], params_template={},
    )

    channel_service.soft_delete_channel(db, ch.id)

    db.refresh(ch)
    assert ch.deleted_at is not None
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.status == "skipped" for i in items)


def test_append_items_to_active_channel(db):
    """Should append new keywords to an active channel."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["orig"], params_template={},
    )

    channel_service.append_items(db, ch.id, ["new-a", "new-b"])

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()
    assert len(items) == 3
    assert items[1].keyword == "new-a"
    assert items[2].keyword == "new-b"


def test_append_items_rejects_paused_channel(db):
    """Should raise ValueError when appending to a paused channel."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["orig"], params_template={},
    )
    channel_service.update_channel_status(db, ch.id, "paused")

    with pytest.raises(ValueError, match="活跃"):
        channel_service.append_items(db, ch.id, ["new"])


def test_update_item_status_skip(db):
    """Should allow skipping a pending item."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["skip-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()

    channel_service.update_item_status(db, items[0].id, "skipped")
    db.refresh(items[0])
    assert items[0].status == "skipped"


def test_update_item_status_requeue_failed(db):
    """Should allow re-queuing a failed item."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["requeue-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    items[0].status = "failed"
    items[0].completed_at = datetime.now(timezone.utc)
    db.flush()

    channel_service.update_item_status(db, items[0].id, "pending")
    db.refresh(items[0])
    assert items[0].status == "pending"
    assert items[0].completed_at is None


def test_complete_item_failed_finalizes_channel(db):
    """Failed items (no retry) should contribute to channel completion."""
    _setup_group(db)
    ch = channel_service.create_channel(
        db, group_id="grp-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-001",
        keywords=["fail-final"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()

    channel_service.complete_item(db, items[0].id, "failed")

    db.refresh(ch)
    assert ch.status == "completed"  # all items terminal → channel completed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_channel_service.py::test_complete_item_marks_channel_completed_when_all_done -v`
Expected: FAIL — complete_item not found

- [ ] **Step 3: Implement complete_item, on_risk_control, update_channel_status**

Add to `ChannelService` class:

```python
    def complete_item(self, db: Session, item_id: str, status: str, retrying: bool = False):
        """Complete a channel item and check if channel is fully done."""
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            return

        channel_id = item.channel_id

        if retrying:
            # Task is retrying — roll back item to pending
            item.status = "pending"
            item.assigned_device_id = None
            item.task_id = None
            db.flush()
            return

        item.status = status
        item.completed_at = datetime.now(timezone.utc)
        db.flush()

        # Atomic completion check
        if status in ("completed", "failed"):
            result = db.execute(
                update(Channel)
                .where(
                    Channel.id == channel_id,
                    Channel.status == "active",
                    ~exists().where(
                        and_(
                            ChannelItem.channel_id == channel_id,
                            ChannelItem.status.notin_(["completed", "failed", "skipped"]),
                        )
                    ),
                )
                .values(status="completed", completed_at=datetime.now(timezone.utc))
            )
            db.flush()

    def on_risk_control(self, db: Session, account_id: str):
        """Skip all pending channel items for a risk-controlled account."""
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.account_id == account_id,
                ChannelItem.status == "pending",
            )
            .values(status="skipped", completed_at=datetime.now(timezone.utc))
        )
        db.flush()

    def update_channel_status(self, db: Session, channel_id: str, new_status: str):
        """Update channel status with validation."""
        ch = self.get_channel(db, channel_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")

        valid_transitions = {
            "active": ["paused", "cancelled"],
            "paused": ["active", "cancelled"],
        }
        allowed = valid_transitions.get(ch.status, [])
        if new_status not in allowed:
            raise ValueError(f"不允许从 {ch.status} 转换到 {new_status}")

        ch.status = new_status
        if new_status == "cancelled":
            # Skip all pending items
            db.execute(
                update(ChannelItem)
                .where(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status == "pending",
                )
                .values(status="skipped", completed_at=datetime.now(timezone.utc))
            )
        db.commit()

    def soft_delete_channel(self, db: Session, channel_id: str):
        """Soft delete a channel."""
        ch = self.get_channel(db, channel_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        ch.deleted_at = datetime.now(timezone.utc)
        # Skip pending items
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.channel_id == channel_id,
                ChannelItem.status == "pending",
            )
            .values(status="skipped", completed_at=datetime.now(timezone.utc))
        )
        db.commit()

    def append_items(self, db: Session, channel_id: str, keywords: list[str]):
        """Append new keywords to an active channel."""
        ch = self.get_channel(db, channel_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        if ch.status != "active":
            raise ValueError("只能向活跃通道追加关键词")

        existing_count = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).count()
        if existing_count + len(keywords) > ch.max_keywords:
            raise ValueError(f"超出最大关键词数 {ch.max_keywords}")

        # Get accounts for distribution
        if ch.account_mode == "single_account":
            account_ids = [ch.account_id] * len(keywords)
        else:
            active_accounts = _get_active_accounts(db, ch.group_id)
            account_ids = self._round_robin_assign(db, keywords, active_accounts)

        for i, keyword in enumerate(keywords):
            item = ChannelItem(
                channel_id=channel_id,
                keyword=keyword,
                account_id=account_ids[i],
                status="pending",
                queue_position=existing_count + i,
            )
            db.add(item)
        db.commit()

    def update_item_status(self, db: Session, item_id: str, new_status: str):
        """Update a single channel item status (skip/requeue)."""
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} 不存在")

        valid = {"pending": ["skipped"], "failed": ["pending"]}
        allowed = valid.get(item.status, [])
        if new_status not in allowed:
            raise ValueError(f"不允许从 {item.status} 转换到 {new_status}")

        item.status = new_status
        if new_status == "pending":
            item.assigned_device_id = None
            item.task_id = None
            item.completed_at = None
        db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_channel_service.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add server/app/services/channel_service.py server/tests/test_channel_service.py
git commit -m "feat: add channel complete, stale recovery, risk control, cancel, append"
```

---

### Task 7: Task Service Integration

**Files:**
- Modify: `server/app/services/task_service.py:86-143`
- Modify: `server/app/services/task_service.py:145-189`

- [ ] **Step 1: Modify get_pending_task() to check channels first**

In `server/app/services/task_service.py`, modify `get_pending_task()`. Insert channel check before the existing routing logic (after line 93, before line 94):

```python
    def get_pending_task(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Claim a pending task using optimistic locking, respecting daily quotas and device routing."""
        # --- Channel claim (priority path) ---
        from app.services.channel_service import channel_service
        channel_result = channel_service.claim_channel_item(db, device_id)
        if channel_result:
            task_pydantic, _channel_item_id = channel_result
            # The task was flush-only created by channel_service; commit now
            db.commit()
            return task_pydantic

        # --- Existing routing logic (unchanged) ---
        # 1. Look up the polling device's bound account
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        # ... rest of existing code ...
```

- [ ] **Step 2: Modify report_result() to handle channel items**

In `report_result()`, insert channel item handling **after** `chain_service.advance_chain()` call (line 185) and **before** `db.commit()` (line 187). This ensures channel changes are committed together with the task changes:

```python
        # Advance chain if this task is part of one
        if db_task.chain_instance_id and db_task.status in ("completed", "failed"):
            from app.services.chain_service import chain_service
            chain_service.advance_chain(db, task_id, db_task.status, result)

        # --- INSERT HERE: Update channel item if this task belongs to one ---
        from app.db_models import ChannelItem
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()
        if channel_item:
            if db_task.status == TaskStatus.COMPLETED.value:
                channel_service.complete_item(db, channel_item.id, "completed")
            elif db_task.status == TaskStatus.FAILED.value:
                if db_task.retry_count < MAX_RETRIES:
                    channel_service.complete_item(db, channel_item.id, "failed", retrying=True)
                else:
                    channel_service.complete_item(db, channel_item.id, "failed")
        # --- END INSERT ---

        db.commit()  # existing line 187 — commits both task + channel changes
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `cd server && python -m pytest tests/test_device_endpoints.py tests/test_stats_service.py -v`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add server/app/services/task_service.py
git commit -m "feat: integrate channel claim into get_pending_task and report_result"
```

---

### Task 8: Channel Router (Admin API)

**Files:**
- Create: `server/app/routers/channels.py`
- Modify: `server/app/main.py` (register router)

- [ ] **Step 1: Create channels router**

```python
# server/app/routers/channels.py
"""Channel management API — admin endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.models import (
    ChannelCreate, ChannelUpdate, ChannelAppendItems,
    ChannelItemUpdate, ChannelResponse, ChannelDetailResponse, ChannelItemResponse,
)
from app.services.channel_service import channel_service
from app.db_models import Account, AccountGroup, Device

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _channel_to_response(ch, stats: dict, group_name: str = "") -> dict:
    return {
        "id": ch.id,
        "group_id": ch.group_id,
        "group_name": group_name,
        "task_type": ch.task_type,
        "status": ch.status,
        "account_mode": ch.account_mode,
        "account_id": ch.account_id or "",
        "params_template": ch.params_template or {},
        "cooldown_seconds": ch.cooldown_seconds,
        "delay_range": ch.delay_range or [3000, 8000],
        "total": stats["total"],
        "pending": stats["pending"],
        "assigned": stats["assigned"],
        "completed": stats["completed"],
        "failed": stats["failed"],
        "skipped": stats["skipped"],
        "created_at": str(ch.created_at) if ch.created_at else None,
        "completed_at": str(ch.completed_at) if ch.completed_at else None,
    }


def _item_to_response(item, account_nickname: str = "", device_name: str = "") -> dict:
    return {
        "id": item.id,
        "keyword": item.keyword,
        "account_id": item.account_id,
        "account_nickname": account_nickname,
        "status": item.status,
        "assigned_device_id": item.assigned_device_id or "",
        "device_name": device_name,
        "task_id": item.task_id or "",
        "queue_position": item.queue_position,
        "created_at": str(item.created_at) if item.created_at else None,
        "completed_at": str(item.completed_at) if item.completed_at else None,
    }


@router.post("")
def create_channel(
    request: ChannelCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        ch = channel_service.create_channel(
            db,
            group_id=request.group_id,
            task_type=request.task_type.value,
            account_mode=request.account_mode,
            keywords=request.keywords,
            params_template=request.params_template,
            account_id=request.account_id,
            cooldown_seconds=request.cooldown_seconds,
            delay_range=request.delay_range,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    return _channel_to_response(ch, stats, group.name if group else "")


@router.get("")
def list_channels(
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    channels = channel_service.list_channels(db)
    group_ids = list(set(ch.group_id for ch in channels))
    groups = {g.id: g.name for g in db.query(AccountGroup).filter(AccountGroup.id.in_(group_ids)).all()} if group_ids else {}

    # Batch query stats for all channels (avoid N+1)
    channel_ids = [ch.id for ch in channels]
    stats_map = channel_service.get_channels_stats_batch(db, channel_ids)

    result = []
    for ch in channels:
        stats = stats_map.get(ch.id, {"total": 0, "pending": 0, "assigned": 0, "completed": 0, "failed": 0, "skipped": 0})
        result.append(_channel_to_response(ch, stats, groups.get(ch.group_id, "")))
    return {"channels": result, "total": len(result)}


@router.get("/{channel_id}")
def get_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    ch = channel_service.get_channel(db, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="通道不存在")

    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    resp = _channel_to_response(ch, stats, group.name if group else "")

    # Include items
    from app.db_models import ChannelItem
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).order_by(ChannelItem.queue_position).all()
    account_ids = list(set(i.account_id for i in items))
    device_ids = list(set(i.assigned_device_id for i in items if i.assigned_device_id))
    accounts = {a.id: a.nickname for a in db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}
    devices_map = {d.id: d.name for d in db.query(Device).filter(Device.id.in_(device_ids)).all()} if device_ids else {}

    resp["items"] = [
        _item_to_response(i, accounts.get(i.account_id, ""), devices_map.get(i.assigned_device_id, ""))
        for i in items
    ]
    return resp


@router.patch("/{channel_id}")
def update_channel(
    channel_id: str,
    request: ChannelUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    try:
        channel_service.update_channel_status(db, channel_id, request.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "updated", "id": channel_id}


@router.delete("/{channel_id}")
def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        channel_service.soft_delete_channel(db, channel_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": True, "id": channel_id}


@router.post("/{channel_id}/items")
def append_items(
    channel_id: str,
    request: ChannelAppendItems,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        channel_service.append_items(db, channel_id, request.keywords)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"appended": len(request.keywords), "channel_id": channel_id}


@router.patch("/{channel_id}/items/{item_id}")
def update_item(
    channel_id: str,
    item_id: str,
    request: ChannelItemUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    try:
        channel_service.update_item_status(db, item_id, request.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "updated", "item_id": item_id}
```

- [ ] **Step 2: Register router in main.py**

In `server/app/main.py`, add the import and include:

```python
from app.routers import channels
# ... existing router includes ...
app.include_router(channels.router)
```

- [ ] **Step 3: Run server to verify startup**

Run: `cd server && python -c "from app.main import app; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add server/app/routers/channels.py server/app/main.py
git commit -m "feat: add channel management admin API endpoints"
```

---

### Task 8b: Channel API Endpoint Tests

**Files:**
- Create: `server/tests/test_channel_api.py`

- [ ] **Step 1: Write API endpoint tests**

```python
# server/tests/test_channel_api.py
"""Channel admin API endpoint tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.db_models import Account, AccountGroup, AccountGroupMember, Device

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


@pytest.fixture(autouse=True)
def setup_data():
    """Seed test data for each test."""
    from app.deps import create_admin_token
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        token = create_admin_token("admin")
        global ADMIN_HEADERS
        ADMIN_HEADERS = {"Authorization": f"Bearer {token}"}
        group = AccountGroup(id="grp-api", name="api-group")
        db.merge(group)
        for aid in ["acc-api-1", "acc-api-2"]:
            db.merge(Account(id=aid, nickname=f"nick-{aid}", status="active"))
            db.merge(AccountGroupMember(group_id="grp-api", account_id=aid))
        db.merge(Device(id="dev-api", name="api-device", status="online"))
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        from app.db_models import Channel, ChannelItem, Task
        db.query(ChannelItem).delete()
        db.query(Channel).delete()
        db.query(Task).filter(Task.device_id == "dev-api").delete()
        db.commit()
    finally:
        db.close()


ADMIN_HEADERS = {}


def test_create_channel_api():
    resp = client.post("/api/channels", json={
        "group_id": "grp-api",
        "task_type": "search_comment",
        "account_mode": "single_account",
        "account_id": "acc-api-1",
        "keywords": ["kw1", "kw2"],
        "params_template": {"content": "hi", "count": 1},
    }, headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["status"] == "active"


def test_list_channels_api():
    # Create one first
    client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["a"], params_template={},
    }, headers=ADMIN_HEADERS)
    resp = client.get("/api/channels", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_get_channel_detail_api():
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["detail-kw"], params_template={},
    }, headers=ADMIN_HEADERS)
    ch_id = create_resp.json()["id"]
    resp = client.get(f"/api/channels/{ch_id}", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_pause_resume_channel_api():
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["pause-api"], params_template={},
    }, headers=ADMIN_HEADERS)
    ch_id = create_resp.json()["id"]

    # Pause
    resp = client.patch(f"/api/channels/{ch_id}", json={"status": "paused"}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200

    # Resume
    resp = client.patch(f"/api/channels/{ch_id}", json={"status": "active"}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200


def test_cancel_channel_api():
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["cancel-api"], params_template={},
    }, headers=ADMIN_HEADERS)
    ch_id = create_resp.json()["id"]

    resp = client.patch(f"/api/channels/{ch_id}", json={"status": "cancelled"}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200


def test_delete_channel_api():
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["delete-api"], params_template={},
    }, headers=ADMIN_HEADERS)
    ch_id = create_resp.json()["id"]

    resp = client.delete(f"/api/channels/{ch_id}", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # Should not appear in list
    list_resp = client.get("/api/channels", headers=ADMIN_HEADERS)
    ids = [c["id"] for c in list_resp.json()["channels"]]
    assert ch_id not in ids


def test_append_items_api():
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["orig-api"], params_template={},
    }, headers=ADMIN_HEADERS)
    ch_id = create_resp.json()["id"]

    resp = client.post(f"/api/channels/{ch_id}/items", json={"keywords": ["new-api"]}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["appended"] == 1


def test_skip_item_api():
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["skip-api"], params_template={},
    }, headers=ADMIN_HEADERS)
    ch_id = create_resp.json()["id"]

    detail = client.get(f"/api/channels/{ch_id}", headers=ADMIN_HEADERS)
    item_id = detail.json()["items"][0]["id"]

    resp = client.patch(f"/api/channels/{ch_id}/items/{item_id}", json={"status": "skipped"}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200


def test_create_channel_validation_error():
    """Should return 400 for missing account_id in single_account mode."""
    resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account",
        "keywords": ["a"], params_template={},
    }, headers=ADMIN_HEADERS)
    assert resp.status_code == 400


def test_channel_not_found():
    resp = client.get("/api/channels/nonexistent", headers=ADMIN_HEADERS)
    assert resp.status_code == 404


def test_create_channel_requires_auth():
    resp = client.post("/api/channels", json={
        "group_id": "grp-api", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-api-1",
        "keywords": ["a"], params_template={},
    })
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests**

Run: `cd server && python -m pytest tests/test_channel_api.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_channel_api.py
git commit -m "test: add channel admin API endpoint tests"
```

---

### Task 9: WS Manager — Channel Events

**Files:**
- Modify: `server/app/ws_manager.py`
- Modify: `server/app/services/channel_service.py` (broadcast calls)

- [ ] **Step 1: Add broadcast_channel_event to ws_manager**

Add to `PairWSManager` class in `server/app/ws_manager.py`:

```python
    async def broadcast_channel_progress(self, channel_id: str, stats: dict):
        """Push channel progress event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_progress",
            "channel_id": channel_id,
            **stats,
        })

    async def broadcast_channel_completed(self, channel_id: str):
        """Push channel completed event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_completed",
            "channel_id": channel_id,
        })
```

- [ ] **Step 2: Add broadcast calls to channel_service**

In `channel_service.py`, add async broadcast calls in `complete_item()` after the atomic completion check. Since the service is sync, use `asyncio.create_task`:

```python
import asyncio

# In complete_item(), after db.flush():
try:
    from app.ws_manager import pair_ws_manager
    stats = self.get_channel_stats(db, channel_id)
    asyncio.create_task(pair_ws_manager.broadcast_channel_progress(channel_id, stats))
    if ch and ch.status == "completed":
        asyncio.create_task(pair_ws_manager.broadcast_channel_completed(channel_id))
except Exception:
    pass  # WS broadcast is non-critical
```

- [ ] **Step 3: Commit**

```bash
git add server/app/ws_manager.py server/app/services/channel_service.py
git commit -m "feat: add channel progress/completed WS broadcast events"
```

---

### Task 10: Device Router — Risk Report Channel Linkage

**Files:**
- Modify: `server/app/routers/device.py`

- [ ] **Step 1: Modify risk-report endpoint**

In the existing `risk-report` endpoint in `server/app/routers/device.py`, after setting `account.status = "risk_controlled"`, add:

```python
        # Skip pending channel items for this account
        from app.services.channel_service import channel_service
        channel_service.on_risk_control(db, report.account_id)
```

- [ ] **Step 2: Commit**

```bash
git add server/app/routers/device.py
git commit -m "feat: risk-report auto-skips pending channel items for affected account"
```

---

### Task 11: Frontend API Layer

**Files:**
- Create: `web/src/api/channels.js`

- [ ] **Step 1: Create channels API module**

```javascript
// web/src/api/channels.js
import client from './client';

export function listChannels() {
  return client.get('/channels');
}

export function getChannel(id) {
  return client.get(`/channels/${id}`);
}

export function createChannel(data) {
  return client.post('/channels', data);
}

export function updateChannel(id, data) {
  return client.patch(`/channels/${id}`, data);
}

export function deleteChannel(id) {
  return client.delete(`/channels/${id}`);
}

export function appendChannelItems(id, keywords) {
  return client.post(`/channels/${id}/items`, { keywords });
}

export function updateChannelItem(channelId, itemId, data) {
  return client.patch(`/channels/${channelId}/items/${itemId}`, data);
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/api/channels.js
git commit -m "feat: add channels API client module"
```

---

### Task 12: Frontend — ChannelsPage

**Files:**
- Create: `web/src/views/ChannelsPage.vue`
- Create: `web/src/components/ChannelCard.vue`
- Create: `web/src/components/CreateChannelDialog.vue`
- Create: `web/src/components/ChannelDetail.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/views/AdminLayout.vue`

- [ ] **Step 1: Create ChannelCard component**

Create `web/src/components/ChannelCard.vue` following the existing glass-card pattern:

```vue
<script setup>
import { computed } from 'vue';

const props = defineProps({
  channel: { type: Object, required: true },
});

const emit = defineEmits(['pause', 'resume', 'cancel', 'detail']);

const progressPercent = computed(() => {
  if (!props.channel.total) return 0;
  return Math.round(((props.channel.completed + props.channel.failed + props.channel.skipped) / props.channel.total) * 100);
});

const statusLabel = computed(() => ({
  active: '运行中',
  paused: '已暂停',
  completed: '已完成',
  cancelled: '已取消',
}[props.channel.status] || props.channel.status));
</script>

<template>
  <div class="glass-card gradient-border p-5">
    <div class="flex items-center justify-between mb-3">
      <div>
        <h3 class="text-white font-semibold">{{ channel.group_name }} · {{ channel.task_type }}</h3>
        <p class="text-sm text-white/50">{{ channel.account_mode === 'single_account' ? '单账号' : '轮转分配' }}</p>
      </div>
      <span :class="[
        'badge',
        channel.status === 'active' ? 'badge-success' :
        channel.status === 'paused' ? 'badge-warning' :
        channel.status === 'completed' ? 'badge-info' : 'badge-danger'
      ]">{{ statusLabel }}</span>
    </div>

    <!-- Progress bar -->
    <div class="w-full bg-white/10 rounded-full h-2 mb-3">
      <div class="bg-gradient-to-r from-purple-500 to-cyan-500 h-2 rounded-full transition-all"
           :style="{ width: progressPercent + '%' }"></div>
    </div>
    <div class="flex justify-between text-xs text-white/50 mb-4">
      <span>{{ channel.completed + channel.failed + channel.skipped }} / {{ channel.total }}</span>
      <span>{{ progressPercent }}%</span>
    </div>

    <!-- Stats -->
    <div class="flex gap-3 text-xs text-white/60 mb-4">
      <span>待处理: {{ channel.pending }}</span>
      <span>执行中: {{ channel.assigned }}</span>
      <span>完成: {{ channel.completed }}</span>
      <span>失败: {{ channel.failed }}</span>
    </div>

    <!-- Actions -->
    <div class="flex gap-2">
      <button v-if="channel.status === 'active'" @click="emit('pause')"
              class="text-xs px-3 py-1 border border-yellow-500/30 text-yellow-400 rounded hover:bg-yellow-500/10">暂停</button>
      <button v-if="channel.status === 'paused'" @click="emit('resume')"
              class="text-xs px-3 py-1 border border-green-500/30 text-green-400 rounded hover:bg-green-500/10">恢复</button>
      <button v-if="['active','paused'].includes(channel.status)" @click="emit('cancel')"
              class="text-xs px-3 py-1 border border-red-500/30 text-red-400 rounded hover:bg-red-500/10">取消</button>
      <button @click="emit('detail')"
              class="text-xs px-3 py-1 border border-white/20 text-white/70 rounded hover:bg-white/5">详情</button>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Create CreateChannelDialog component**

Create `web/src/components/CreateChannelDialog.vue`:

```vue
<script setup>
import { reactive, ref, watch } from 'vue';
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue';
import { listGroups, listGroupMembers } from '../api/accountGroups';
import { createChannel } from '../api/channels';

const props = defineProps({ open: Boolean });
const emit = defineEmits(['close', 'created']);

const saving = ref(false);
const formError = ref(null);
const groups = ref([]);
const accounts = ref([]);

const form = reactive({
  group_id: '',
  task_type: 'search_comment',
  account_mode: 'round_robin',
  account_id: '',
  keywords: '',
  params_template: { content: '', count: 5, sort_by: 'latest' },
  cooldown_seconds: 300,
});

watch(() => props.open, async (val) => {
  if (val) {
    formError.value = null;
    const res = await listGroups();
    groups.value = res.data.groups || [];
  }
});

watch(() => form.group_id, async (gid) => {
  if (gid) {
    const res = await listGroupMembers(gid, { status: 'active' });
    accounts.value = res.data.members || [];
  }
});

async function handleSubmit() {
  saving.value = true;
  formError.value = null;
  try {
    const keywords = form.keywords.split('\n').map(k => k.trim()).filter(Boolean);
    if (!keywords.length) { formError.value = '请输入至少一个关键词'; return; }
    await createChannel({
      ...form,
      keywords,
      params_template: { ...form.params_template },
    });
    emit('created');
    emit('close');
  } catch (e) {
    formError.value = e.response?.data?.detail || e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog @close="emit('close')" class="relative z-50">
      <TransitionChild enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100"
                       leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-black/60 backdrop-blur-sm" />
      </TransitionChild>
      <div class="fixed inset-0 flex items-center justify-center p-4">
        <TransitionChild enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100"
                         leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0 scale-95">
          <DialogPanel class="glass-card gradient-border w-full max-w-lg p-6">
            <DialogTitle class="text-xl font-bold gradient-text mb-4">创建通道</DialogTitle>
            <div v-if="formError" class="bg-red-500/10 border border-red-500/30 text-red-400 px-3 py-2 rounded mb-4 text-sm">{{ formError }}</div>
            <form @submit.prevent="handleSubmit" class="space-y-4">
              <div>
                <label class="block text-sm text-white/70 mb-1">账号分组</label>
                <select v-model="form.group_id" class="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white">
                  <option value="" disabled>选择分组</option>
                  <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-white/70 mb-1">任务类型</label>
                <select v-model="form.task_type" class="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white">
                  <option value="search_comment">搜索评论</option>
                  <option value="search_like">搜索点赞</option>
                  <option value="search_dm">搜索私信</option>
                  <option value="reply_comment">回复评论</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-white/70 mb-1">账号模式</label>
                <select v-model="form.account_mode" class="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white">
                  <option value="round_robin">轮转分配</option>
                  <option value="single_account">单账号</option>
                </select>
              </div>
              <div v-if="form.account_mode === 'single_account'">
                <label class="block text-sm text-white/70 mb-1">指定账号</label>
                <select v-model="form.account_id" class="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white">
                  <option value="" disabled>选择账号</option>
                  <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.nickname }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-white/70 mb-1">关键词（每行一个，最多 500 个）</label>
                <textarea v-model="form.keywords" rows="6"
                          class="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white font-mono text-sm"
                          placeholder="美食&#10;旅游&#10;健身"></textarea>
              </div>
              <div>
                <label class="block text-sm text-white/70 mb-1">评论内容</label>
                <input v-model="form.params_template.content"
                       class="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white" />
              </div>
              <div>
                <label class="block text-sm text-white/70 mb-1">冷却时间（秒）</label>
                <input v-model.number="form.cooldown_seconds" type="number" min="30" max="3600"
                       class="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white" />
              </div>
              <div class="flex justify-end gap-3 pt-2">
                <button type="button" @click="emit('close')"
                        class="px-4 py-2 border border-white/20 text-white/70 rounded hover:bg-white/5">取消</button>
                <button type="submit" :disabled="saving"
                        class="btn-aurora px-4 py-2 rounded disabled:opacity-50">{{ saving ? '创建中...' : '创建' }}</button>
              </div>
            </form>
          </DialogPanel>
        </TransitionChild>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
```

- [ ] **Step 3: Create ChannelDetail component**

Create `web/src/components/ChannelDetail.vue` — a dialog showing channel items in a table:

```vue
<script setup>
import { ref, watch } from 'vue';
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue';
import { getChannel, updateChannel, updateChannelItem, appendChannelItems } from '../api/channels';

const props = defineProps({ open: Boolean, channelId: String });
const emit = defineEmits(['close']);

const channel = ref(null);
const loading = ref(false);
const newKeywords = ref('');

async function loadChannel() {
  if (!props.channelId) return;
  loading.value = true;
  try {
    const res = await getChannel(props.channelId);
    channel.value = res.data;
  } finally {
    loading.value = false;
  }
}

watch(() => [props.open, props.channelId], ([open]) => {
  if (open) loadChannel();
});

async function handlePauseResume() {
  const newStatus = channel.value.status === 'active' ? 'paused' : 'active';
  await updateChannel(props.channelId, { status: newStatus });
  await loadChannel();
}

async function handleCancel() {
  await updateChannel(props.channelId, { status: 'cancelled' });
  await loadChannel();
}

async function handleSkipItem(itemId) {
  await updateChannelItem(props.channelId, itemId, { status: 'skipped' });
  await loadChannel();
}

async function handleRequeueItem(itemId) {
  await updateChannelItem(props.channelId, itemId, { status: 'pending' });
  await loadChannel();
}

async function handleAppend() {
  const keywords = newKeywords.value.split('\n').map(k => k.trim()).filter(Boolean);
  if (!keywords.length) return;
  await appendChannelItems(props.channelId, keywords);
  newKeywords.value = '';
  await loadChannel();
}

const statusMap = { pending: '待处理', assigned: '执行中', completed: '已完成', failed: '失败', skipped: '已跳过' };
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog @close="emit('close')" class="relative z-50">
      <TransitionChild enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100"
                       leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-black/60 backdrop-blur-sm" />
      </TransitionChild>
      <div class="fixed inset-0 flex items-center justify-center p-4">
        <TransitionChild enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100"
                         leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0 scale-95">
          <DialogPanel class="glass-card gradient-border w-full max-w-4xl max-h-[80vh] overflow-y-auto p-6">
            <DialogTitle class="text-xl font-bold gradient-text mb-4">通道详情</DialogTitle>
            <div v-if="loading" class="text-white/50 text-center py-8">加载中...</div>
            <template v-else-if="channel">
              <!-- Stats bar -->
              <div class="flex gap-4 mb-4 text-sm text-white/70">
                <span>总计: {{ channel.total }}</span>
                <span>待处理: {{ channel.pending }}</span>
                <span>执行中: {{ channel.assigned }}</span>
                <span>完成: {{ channel.completed }}</span>
                <span>失败: {{ channel.failed }}</span>
                <span>跳过: {{ channel.skipped }}</span>
              </div>
              <!-- Progress -->
              <div class="w-full bg-white/10 rounded-full h-2 mb-4">
                <div class="bg-gradient-to-r from-purple-500 to-cyan-500 h-2 rounded-full transition-all"
                     :style="{ width: (channel.total ? Math.round((channel.completed + channel.failed + channel.skipped) / channel.total * 100) : 0) + '%' }"></div>
              </div>
              <!-- Actions -->
              <div class="flex gap-2 mb-4">
                <button v-if="['active','paused'].includes(channel.status)" @click="handlePauseResume"
                        class="text-xs px-3 py-1 border border-white/20 text-white/70 rounded hover:bg-white/5">
                  {{ channel.status === 'active' ? '暂停' : '恢复' }}
                </button>
                <button v-if="['active','paused'].includes(channel.status)" @click="handleCancel"
                        class="text-xs px-3 py-1 border border-red-500/30 text-red-400 rounded hover:bg-red-500/10">取消</button>
              </div>
              <!-- Append keywords -->
              <div v-if="channel.status === 'active'" class="mb-4 flex gap-2">
                <textarea v-model="newKeywords" rows="2" placeholder="追加关键词（每行一个）"
                          class="flex-1 bg-white/5 border border-white/10 rounded px-3 py-2 text-white text-sm font-mono"></textarea>
                <button @click="handleAppend" class="btn-aurora px-3 py-2 rounded text-sm self-end">追加</button>
              </div>
              <!-- Items table -->
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-white/50 border-b border-white/10">
                    <th class="text-left py-2">关键词</th>
                    <th class="text-left py-2">账号</th>
                    <th class="text-left py-2">状态</th>
                    <th class="text-left py-2">设备</th>
                    <th class="text-left py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in channel.items" :key="item.id" class="border-b border-white/5 text-white/80">
                    <td class="py-2">{{ item.keyword }}</td>
                    <td class="py-2">{{ item.account_nickname || item.account_id }}</td>
                    <td class="py-2">{{ statusMap[item.status] || item.status }}</td>
                    <td class="py-2">{{ item.device_name || '-' }}</td>
                    <td class="py-2">
                      <button v-if="item.status === 'pending'" @click="handleSkipItem(item.id)"
                              class="text-xs text-yellow-400 hover:underline">跳过</button>
                      <button v-if="item.status === 'failed'" @click="handleRequeueItem(item.id)"
                              class="text-xs text-green-400 hover:underline">重新入队</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </template>
            <div class="flex justify-end pt-4">
              <button @click="emit('close')" class="px-4 py-2 border border-white/20 text-white/70 rounded hover:bg-white/5">关闭</button>
            </div>
          </DialogPanel>
        </TransitionChild>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
```

- [ ] **Step 4: Create ChannelsPage**

Create `web/src/views/ChannelsPage.vue`:

```vue
<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { listChannels, updateChannel, deleteChannel } from '../api/channels';
import ChannelCard from '../components/ChannelCard.vue';
import CreateChannelDialog from '../components/CreateChannelDialog.vue';
import ChannelDetail from '../components/ChannelDetail.vue';
import ConfirmDialog from '../components/ConfirmDialog.vue';

const pageError = ref(null);
const channels = ref([]);
const loading = ref(false);
const showCreate = ref(false);
const detailChannelId = ref(null);
const showDetail = ref(false);
const showDeleteDialog = ref(false);
const deletingChannel = ref(null);

async function fetchChannels() {
  loading.value = true;
  try {
    const res = await listChannels();
    channels.value = res.data.channels || [];
  } catch (e) {
    pageError.value = e.response?.data?.detail || e.message;
  } finally {
    loading.value = false;
  }
}

async function handlePause(ch) {
  await updateChannel(ch.id, { status: 'paused' });
  await fetchChannels();
}

async function handleResume(ch) {
  await updateChannel(ch.id, { status: 'active' });
  await fetchChannels();
}

async function handleCancel(ch) {
  await updateChannel(ch.id, { status: 'cancelled' });
  await fetchChannels();
}

function handleDetail(ch) {
  detailChannelId.value = ch.id;
  showDetail.value = true;
}

async function handleDeleteConfirm() {
  if (!deletingChannel.value) return;
  await deleteChannel(deletingChannel.value.id);
  showDeleteDialog.value = false;
  deletingChannel.value = null;
  await fetchChannels();
}

// WS for real-time updates
let ws = null;
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = localStorage.getItem('token');
  ws = new WebSocket(`${proto}//${location.host}/api/devices/ws/pair-events?token=${token}`);
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.event === 'channel_progress' || data.event === 'channel_completed') {
        fetchChannels();
      }
    } catch {}
  };
  ws.onclose = () => { setTimeout(connectWS, 3000); };
}

onMounted(() => {
  fetchChannels();
  connectWS();
});

onUnmounted(() => {
  if (ws) { ws.onclose = null; ws.close(); }
});
</script>

<template>
  <div class="p-6">
    <div v-if="pageError" class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-2 rounded mb-4 flex justify-between">
      <span>{{ pageError }}</span>
      <button @click="pageError = null" class="text-red-400 hover:text-red-300">&times;</button>
    </div>

    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold gradient-text">任务通道</h1>
      <button @click="showCreate = true" class="btn-aurora px-4 py-2 rounded">创建通道</button>
    </div>

    <div v-if="loading" class="text-white/50 text-center py-12">加载中...</div>
    <div v-else-if="channels.length === 0" class="text-white/50 text-center py-12">暂无通道</div>
    <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <ChannelCard
        v-for="ch in channels"
        :key="ch.id"
        :channel="ch"
        @pause="handlePause(ch)"
        @resume="handleResume(ch)"
        @cancel="handleCancel(ch)"
        @detail="handleDetail(ch)"
      />
    </div>

    <CreateChannelDialog :open="showCreate" @close="showCreate = false" @created="fetchChannels" />
    <ChannelDetail :open="showDetail" :channel-id="detailChannelId" @close="showDetail = false" />
  </div>
</template>
```

- [ ] **Step 5: Add route**

In `web/src/router/index.js`, add to the children array:

```javascript
{
  path: '/channels',
  name: 'Channels',
  component: () => import('../views/ChannelsPage.vue'),
},
```

- [ ] **Step 6: Add sidebar entry**

In `web/src/views/AdminLayout.vue`, add to the navigation items array:

```javascript
{ name: '任务通道', path: '/channels', icon: 'M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z' },
```

- [ ] **Step 7: Commit**

```bash
git add web/src/components/ChannelCard.vue web/src/components/CreateChannelDialog.vue \
       web/src/components/ChannelDetail.vue web/src/views/ChannelsPage.vue \
       web/src/api/channels.js web/src/router/index.js web/src/views/AdminLayout.vue
git commit -m "feat: add channel management UI with real-time progress updates"
```

---

### Task 12: Integration Test — End-to-End Channel Flow

**Files:**
- Create: `server/tests/test_channel_e2e.py`

- [ ] **Step 1: Write integration test**

```python
# server/tests/test_channel_e2e.py
"""End-to-end channel flow test via HTTP endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.db_models import Account, AccountGroup, AccountGroupMember, Device

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}
ADMIN_HEADERS = {}  # Will be set after login


@pytest.fixture(autouse=True)
def setup_data():
    """Seed test data for each test."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        # Create admin token
        from app.deps import create_admin_token
        global ADMIN_HEADERS
        token = create_admin_token("admin")
        ADMIN_HEADERS = {"Authorization": f"Bearer {token}"}

        # Create group + accounts
        group = AccountGroup(id="grp-e2e", name="e2e-group")
        db.merge(group)
        for aid in ["acc-e2e-1", "acc-e2e-2"]:
            db.merge(Account(id=aid, nickname=f"nick-{aid}", status="active"))
            db.merge(AccountGroupMember(group_id="grp-e2e", account_id=aid))

        # Create device
        db.merge(Device(id="dev-e2e", name="e2e-device", status="online"))
        db.commit()
    finally:
        db.close()
    yield
    # Cleanup
    db = SessionLocal()
    try:
        from app.db_models import Channel, ChannelItem, Task
        db.query(ChannelItem).delete()
        db.query(Channel).delete()
        db.query(Task).filter(Task.device_id == "dev-e2e").delete()
        db.commit()
    finally:
        db.close()


def test_full_channel_flow():
    """Create channel → device poll claims item → report result → channel completes."""
    # 1. Create channel
    resp = client.post("/api/channels", json={
        "group_id": "grp-e2e",
        "task_type": "search_comment",
        "account_mode": "single_account",
        "account_id": "acc-e2e-1",
        "keywords": ["test-keyword"],
        "params_template": {"content": "hello", "count": 1},
    }, headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    channel_id = resp.json()["id"]
    assert resp.json()["total"] == 1

    # 2. Device poll — should get the channel task
    resp = client.get("/api/device/poll", params={"device_id": "dev-e2e"}, headers=HEADERS)
    assert resp.status_code == 200
    task = resp.json().get("task")
    assert task is not None
    assert task["type"] == "search_comment"
    assert task["params"]["keyword"] == "test-keyword"

    # 3. Report result
    resp = client.post("/api/device/report", json={
        "task_id": task["id"],
        "status": "completed",
        "result": {"success_count": 1},
    }, headers=HEADERS)
    assert resp.status_code == 200

    # 4. Channel should be completed
    resp = client.get(f"/api/channels/{channel_id}", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["completed"] == 1
```

- [ ] **Step 2: Run test**

Run: `cd server && python -m pytest tests/test_channel_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_channel_e2e.py
git commit -m "test: add end-to-end channel flow integration test"
```

---

## Verification Checklist

After all tasks, verify:

- [ ] `cd server && python -m pytest tests/ -v` — all tests pass (target: 35+ tests)
- [ ] Create a channel via admin UI → verify items appear
- [ ] Device polls → receives channel task → completes → channel progresses
- [ ] Pause channel → device stops receiving new items
- [ ] Resume channel → device resumes
- [ ] Two devices online → concurrent execution
- [ ] Account risk_controlled → pending items auto-skipped
- [ ] Stale assigned item (>10min) → auto-recovered to pending
- [ ] Daily quota exceeded → channel task not assigned to that account
- [ ] Cooldown period respected between consecutive tasks
- [ ] Bound device only claims its account's items
- [ ] Soft-deleted channel not visible in list
- [ ] Appended keywords appear in channel detail

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | OPEN | 8 issues, 0 critical gaps |

- **UNRESOLVED:** 0 — all 8 issues resolved with user decisions
- **FIXES APPLIED:**
  1. ChannelItem 新增 `assigned_at` 字段，stale recovery 使用正确时间
  2. claim_channel_item 加入 `stats_service.check_quota()` 配额检查
  3. `_round_robin_assign` 按 DailyStats 今日用量升序排列后轮转
  4. report_result channel 处理位置修正为 chain advancement 之后、db.commit() 之前
  5. CreateChannelDialog 改用 `listGroupMembers` 接口查询分组内账号
  6. db fixture 提取到 `conftest.py` 共享
  7. 测试覆盖从 49% 提升到 100%（补充 18 个缺失测试）
  8. `list_channels` 改为批量查询 stats 避免 N+1
- **VERDICT:** ALL FIXES INTEGRATED — ready to implement

### Completion Summary
- Step 0: Scope Challenge — scope accepted as-is (16 files, 1 new service)
- Architecture Review: 7 issues found (4 critical/high, 3 medium/low)
- Code Quality Review: 2 issues found (1 DRY, 1 low-priority)
- Test Review: diagram produced, 18 gaps identified → all filled
- Performance Review: 2 issues found (1 N+1 fixed, 1 accepted)
- NOT in scope: written (N/A — no new artifacts)
- What already exists: written (task_service routing, ws_manager broadcast, account_groups members API)
- TODOS.md updates: 0 items (no deferred work)
- Failure modes: 0 critical gaps (all paths have tests + error handling)
- Outside voice: skipped (user chose to proceed)
- Parallelization: 3 lanes, 2 parallel / 1 sequential (backend+frontend parallel, integration sequential)
- Lake Score: 7/8 recommendations chose complete option
