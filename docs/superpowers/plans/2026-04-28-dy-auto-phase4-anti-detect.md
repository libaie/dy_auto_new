# Phase 4: 反检测增强 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善反检测体系：每日操作配额强制执行、操作时间窗口、设备端代理集成、风控检测上报、增强拟人行为

**Architecture:** 服务端新增 `DailyStats` 模型追踪每日操作量，`task_service` 在分配任务前检查配额。设备端增强 `anti-detect.js` 添加时间分布逻辑和代理配置，`crash-recovery` 检测风控后上报服务端标记账号状态。通过 poll 响应传递代理配置和反检测参数。

**Tech Stack:** Python/FastAPI/SQLAlchemy (server), AutoJS6 JavaScript (device), pytest (tests)

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `server/app/services/stats_service.py` | 每日统计服务：记录/查询/配额检查 |
| Modify | `server/app/db_models.py` | 新增 DailyStats 模型 |
| Modify | `server/app/services/task_service.py` | 分配任务前检查每日配额 |
| Modify | `server/app/models.py` | PollResponse 新增 anti_detect_config 字段 |
| Modify | `server/app/routers/device.py` | poll 响应附加反检测配置 |
| Modify | `server/app/config.py` | 新增反检测默认配置常量 |
| Create | `server/tests/test_stats_service.py` | 统计服务测试 |
| Modify | `server/tests/test_task_service.py` | 新增配额限制测试 |
| Modify | `device/core/anti-detect.js` | 新增时间分布检查、代理应用 |
| Modify | `device/core/api-client.js` | 代理配置应用到 HTTP 请求 |
| Modify | `device/core/crash-recovery.js` | 风控检测后上报服务端 |
| Modify | `device/main.js` | 启动时应用代理、传递反检测配置 |
| Modify | `device/config.js` | 新增代理和时间窗口配置 |

---

### Task 1: DailyStats 模型与统计服务

**Files:**
- Modify: `server/app/db_models.py`
- Create: `server/app/services/stats_service.py`
- Create: `server/tests/test_stats_service.py`

- [ ] **Step 1: 在 db_models.py 中添加 DailyStats 模型**

在 `UISelector` 类之后添加：

```python
from sqlalchemy import UniqueConstraint

class DailyStats(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_daily_stats_account_date"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    likes = Column(Integer, nullable=False, default=0)
    comments = Column(Integer, nullable=False, default=0)
    follows = Column(Integer, nullable=False, default=0)
    dms = Column(Integer, nullable=False, default=0)
    replies = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    account = relationship("Account")
```

- [ ] **Step 2: 创建 stats_service.py**

```python
"""Daily stats tracking service — operation counts per account per day."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db_models import DailyStats, Account


# Task type -> daily_stats column mapping
_TASK_TYPE_TO_COLUMN = {
    "search_like": "likes",
    "nurture": "likes",       # nurture 中的 like 操作计入 likes
    "search_comment": "comments",
    "reply_comment": "replies",
    "search_dm": "dms",
    "follow": "follows",
}


class StatsService:
    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _get_or_create(self, db: Session, account_id: str, date: str) -> DailyStats:
        """Get or create daily stats row for an account+date."""
        stats = db.query(DailyStats).filter(
            and_(DailyStats.account_id == account_id, DailyStats.date == date)
        ).first()
        if not stats:
            stats = DailyStats(account_id=account_id, date=date)
            db.add(stats)
            db.flush()
        return stats

    def increment(self, db: Session, account_id: str, task_type: str, count: int = 1) -> None:
        """Increment operation count for a task type. Only flushes — caller must commit."""
        column = _TASK_TYPE_TO_COLUMN.get(task_type)
        if not column:
            return
        date = self._today()
        stats = self._get_or_create(db, account_id, date)
        current = getattr(stats, column, 0)
        setattr(stats, column, current + count)
        db.flush()

    def get_today_counts(self, db: Session, account_id: str) -> dict[str, int]:
        """Get today's operation counts for an account."""
        date = self._today()
        stats = self._get_or_create(db, account_id, date)
        return {
            "likes": stats.likes,
            "comments": stats.comments,
            "follows": stats.follows,
            "dms": stats.dms,
            "replies": stats.replies,
        }

    def check_quota(self, db: Session, account_id: str, task_type: str) -> bool:
        """Check if account has remaining quota for this task type today.

        Returns True if quota is available, False if limit reached.
        """
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return True  # no account found, don't block

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        column = _TASK_TYPE_TO_COLUMN.get(task_type)
        if not column:
            return True  # unknown type, don't block

        limit = limits.get(column, 999)
        used = counts.get(column, 0)
        return used < limit

    def get_remaining_quotas(self, db: Session, account_id: str) -> dict[str, int]:
        """Get remaining quotas for all operation types."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {}

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        remaining = {}
        for key in ("likes", "comments", "follows", "dms", "replies"):
            limit = limits.get(key, 999)
            used = counts.get(key, 0)
            remaining[key] = max(0, limit - used)
        return remaining


stats_service = StatsService()
```

- [ ] **Step 3: 编写 stats_service 测试**

```python
"""Stats service tests — daily operation counting and quota checks."""
import pytest
from app.services.stats_service import stats_service
from app.models import TaskType
from app.database import get_db
from app.main import app


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


def test_increment_and_get_counts(db):
    """Incrementing likes should be reflected in get_today_counts."""
    stats_service.increment(db, "acc-001", "search_like", count=3)
    counts = stats_service.get_today_counts(db, "acc-001")
    assert counts["likes"] >= 3


def test_increment_comments(db):
    stats_service.increment(db, "acc-002", "search_comment", count=2)
    counts = stats_service.get_today_counts(db, "acc-002")
    assert counts["comments"] >= 2


def test_check_quota_within_limit(db):
    """Fresh account should have quota available."""
    assert stats_service.check_quota(db, "acc-new", "search_like") is True


def test_check_quota_exceeded(db):
    """After hitting the daily limit, quota check should return False."""
    # Default limit for likes is 50
    stats_service.increment(db, "acc-limit-test", "search_like", count=50)
    assert stats_service.check_quota(db, "acc-limit-test", "search_like") is False


def test_check_quota_exact_boundary(db):
    """At exactly the limit (used == limit), quota should be exhausted."""
    stats_service.increment(db, "acc-boundary", "search_like", count=49)
    assert stats_service.check_quota(db, "acc-boundary", "search_like") is True
    stats_service.increment(db, "acc-boundary", "search_like", count=1)
    assert stats_service.check_quota(db, "acc-boundary", "search_like") is False


def test_check_quota_unknown_account(db):
    """Non-existent account should not be blocked (fail-open)."""
    assert stats_service.check_quota(db, "nonexistent-account", "search_like") is True


def test_get_remaining_quotas(db):
    stats_service.increment(db, "acc-remaining", "search_comment", count=5)
    remaining = stats_service.get_remaining_quotas(db, "acc-remaining")
    assert remaining["comments"] == 15  # 20 - 5
    assert remaining["likes"] == 50     # untouched


def test_unknown_task_type_no_block(db):
    """Unknown task types should not be blocked."""
    assert stats_service.check_quota(db, "acc-001", "unknown_type") is True
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd server && python -m pytest tests/test_stats_service.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add server/app/db_models.py server/app/services/stats_service.py server/tests/test_stats_service.py
git commit -m "feat(server): add DailyStats model and stats service for operation counting"
```

---

### Task 2: 任务调度器集成每日配额

**Files:**
- Modify: `server/app/services/task_service.py`
- Modify: `server/tests/test_task_service.py`

- [ ] **Step 1: 修改 task_service.get_pending_task 添加配额检查**

在 `task_service.py` 的 `get_pending_task` 方法中，找到待分配任务后、乐观锁之前，添加配额检查：

```python
# 在文件顶部 import
from app.services.stats_service import stats_service

# 修改 get_pending_task 方法
def get_pending_task(self, db: Session, device_id: str) -> Optional[PydanticTask]:
    """Claim a pending task using optimistic locking, respecting daily quotas."""
    # Find oldest pending tasks (get a few candidates for quota filtering)
    candidates = db.query(DBTask).filter(
        DBTask.status == TaskStatus.PENDING.value,
    ).order_by(DBTask.created_at.asc()).limit(10).all()

    if not candidates:
        return None

    # Filter by daily quota
    for db_task in candidates:
        if stats_service.check_quota(db, db_task.account_id, db_task.type):
            # Quota available — try to claim this task
            result = db.execute(
                update(DBTask)
                .where(DBTask.id == db_task.id, DBTask.status == TaskStatus.PENDING.value)
                .values(status=TaskStatus.RUNNING.value, device_id=device_id, started_at=datetime.now(timezone.utc))
            )
            db.commit()

            if result.rowcount == 0:
                # Another device claimed it — try next candidate
                continue

            db.refresh(db_task)
            return _db_task_to_pydantic(db_task)

    # All candidates are over quota — return None (tasks stay pending for next day)
    return None
```

- [ ] **Step 2: 在 report_result 中自动记录操作量**

修改 `report_result` 方法，在任务完成时自动递增统计：

```python
def report_result(
    self, db: Session, task_id: str, status: TaskStatus,
    result: Optional[dict] = None, ui_snapshot: Optional[dict] = None,
) -> PydanticTask:
    db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
    if not db_task:
        raise ValueError(f"Task {task_id} not found")

    if status == TaskStatus.COMPLETED:
        db_task.status = TaskStatus.COMPLETED.value
        db_task.result = result
        db_task.completed_at = datetime.now(timezone.utc)
        # Record operation count
        success_count = (result or {}).get("success_count", 1)
        stats_service.increment(db, db_task.account_id, db_task.type, count=success_count)
    elif status == TaskStatus.FAILED:
        db_task.retry_count += 1
        if db_task.retry_count >= MAX_RETRIES:
            db_task.status = TaskStatus.FAILED.value
            db_task.result = result
            db_task.completed_at = datetime.now(timezone.utc)
        else:
            db_task.status = TaskStatus.PENDING.value
            db_task.device_id = None
            db_task.started_at = None

    db.commit()
    db.refresh(db_task)
    return _db_task_to_pydantic(db_task)
```

- [ ] **Step 3: 添加配额限制测试**

在 `test_task_service.py` 末尾添加：

```python
def test_quota_blocks_task_assignment(db):
    """When ALL pending tasks are over quota, get_pending_task returns None."""
    from app.services.stats_service import stats_service
    from app.db_models import Task as DBTask

    quota_account = "acc-quota-test"
    # Exhaust likes quota (default 50)
    stats_service.increment(db, quota_account, "search_like", count=50)

    # Cancel all existing pending tasks to isolate this test
    db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).update(
        {"status": TaskStatus.CANCELLED.value}
    )
    db.commit()

    # Create ONLY a search_like task for the quota-exhausted account
    task_service.create_task(db, TaskType.SEARCH_LIKE, quota_account, {"keyword": "test"})

    # Try to claim — should get None because the only pending task is over quota
    claimed = task_service.get_pending_task(db, "dev-quota")
    assert claimed is None

    # Verify the task is still pending (not silently dropped)
    remaining = db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).all()
    assert len(remaining) == 1
    assert remaining[0].account_id == quota_account


def test_quota_allows_non_exhausted_tasks(db):
    """Tasks of non-exhausted types should still be assignable."""
    from app.services.stats_service import stats_service
    from app.db_models import Task as DBTask

    quota_account2 = "acc-quota-test2"
    stats_service.increment(db, quota_account2, "search_like", count=50)

    # Cancel all existing pending tasks to isolate this test
    db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).update(
        {"status": TaskStatus.CANCELLED.value}
    )
    db.commit()

    # Create a search_comment task (comment quota not exhausted)
    task_service.create_task(db, TaskType.SEARCH_COMMENT, quota_account2, {"keyword": "test"})
    claimed = task_service.get_pending_task(db, "dev-quota2")
    assert claimed is not None
    assert claimed.type == TaskType.SEARCH_COMMENT


def test_report_completed_increments_stats(db):
    """Completing a task should increment daily stats."""
    from app.services.stats_service import stats_service

    stats_account = "acc-stats-test"
    task = task_service.create_task(db, TaskType.SEARCH_LIKE, stats_account, {"keyword": "test"})
    task_service.get_pending_task(db, "dev-stats")

    counts_before = stats_service.get_today_counts(db, stats_account)
    task_service.report_result(db, task.id, TaskStatus.COMPLETED, {"success_count": 3})
    counts_after = stats_service.get_today_counts(db, stats_account)

    assert counts_after["likes"] - counts_before["likes"] == 3


def test_all_candidates_over_quota_returns_none(db):
    """When all 10+ candidates are over quota, returns None."""
    from app.services.stats_service import stats_service
    from app.db_models import Task as DBTask

    # Cancel all existing pending tasks
    db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).update(
        {"status": TaskStatus.CANCELLED.value}
    )
    db.commit()

    # Create 12 tasks for quota-exhausted accounts
    for i in range(12):
        acc = f"acc-overquota-{i}"
        stats_service.increment(db, acc, "search_like", count=50)
        task_service.create_task(db, TaskType.SEARCH_LIKE, acc, {"keyword": "test"})

    claimed = task_service.get_pending_task(db, "dev-overquota")
    assert claimed is None
```

- [ ] **Step 4: 运行测试**

Run: `cd server && python -m pytest tests/test_task_service.py -v`
Expected: All tests pass including 2 new quota tests

- [ ] **Step 5: Commit**

```bash
git add server/app/services/task_service.py server/tests/test_task_service.py
git commit -m "feat(server): enforce daily operation quotas in task scheduler"
```

---

### Task 3: 设备端代理配置集成

**Files:**
- Modify: `device/core/api-client.js`
- Modify: `device/main.js`
- Modify: `device/config.js`

- [ ] **Step 1: 在 config.js 中添加代理配置占位**

在 `antiDetect` 配置之后添加：

```javascript
  // 代理配置（从服务端 poll 响应获取后动态设置）
  proxy: null,  // { type: "http", host: "...", port: 8080, username: "...", password: "..." }

  // 反检测配置版本（用于增量更新）
  antiDetectVersion: 0,
```

- [ ] **Step 2: 在 api-client.js 中添加代理配置方法**

在 `apiClient` 对象中添加：

```javascript
  /**
   * 应用代理配置到 HTTP 请求
   * @param {Object} proxyConfig - { type, host, port, username, password }
   */
  setProxy: function (proxyConfig) {
    if (!proxyConfig || !proxyConfig.host) {
      logger.info(TAG, "No proxy configured");
      config.proxy = null;
      return;
    }

    config.proxy = proxyConfig;
    logger.info(TAG, "Proxy configured: " + proxyConfig.type + "://" +
      proxyConfig.host + ":" + proxyConfig.port);
  },

  /**
   * 获取当前代理配置的 HTTP 选项
   * @returns {Object} 适合 http.get/http.post 的选项
   */
  _getProxyOptions: function () {
    if (!config.proxy) return {};

    var proxy = config.proxy;
    var proxyUrl = proxy.type + "://" + proxy.host + ":" + proxy.port;
    if (proxy.username) {
      proxyUrl = proxy.type + "://" + proxy.username + ":" + proxy.password +
        "@" + proxy.host + ":" + proxy.port;
    }
    return { proxy: proxyUrl };
  },
```

- [ ] **Step 3: 修改 _requestWithRetry 集成代理**

在 `_requestWithRetry` 中的 `reqOpts` 构建处，合并代理选项：

```javascript
        var reqOpts = {
          headers: { "X-Device-Secret": config.deviceSecret },
          timeout: timeout,
        };
        // 合并代理配置
        var proxyOpts = this._getProxyOptions();
        for (var pk in proxyOpts) {
          reqOpts[pk] = proxyOpts[pk];
        }
```

- [ ] **Step 4: 在 main.js 中处理 poll 返回的代理配置**

在 `main.js` 的 poll 响应处理中，检查并应用代理：

```javascript
      if (response) {
        // 应用代理配置
        if (response.proxy) {
          apiClient.setProxy(response.proxy);
        }

        // 检查选择器版本
        // ... existing code ...
```

- [ ] **Step 5: Commit**

```bash
git add device/core/api-client.js device/main.js device/config.js
git commit -m "feat(device): integrate proxy configuration from server poll response"
```

---

### Task 4: 操作时间分布与增强反检测

**Files:**
- Modify: `device/core/anti-detect.js`
- Modify: `device/config.js`

- [ ] **Step 1: 在 config.js 中添加时间窗口配置**

在 `antiDetect` 对象中添加：

```javascript
    // 操作时间窗口（24小时制，模拟真实用户活跃时段）
    activeHours: {
      start: 7,    // 早上7点开始
      end: 23,     // 晚上11点结束
      // 各时段权重（模拟早中晚高峰）
      peaks: [
        { start: 7, end: 9, weight: 20 },    // 早高峰
        { start: 11, end: 13, weight: 25 },   // 午间
        { start: 17, end: 20, weight: 30 },   // 晚高峰
        { start: 20, end: 23, weight: 25 },   // 晚间
      ],
    },
```

- [ ] **Step 2: 在 anti-detect.js 中添加时间分布检查**

在 `antiDetect` 对象中添加方法：

```javascript
  /**
   * 检查当前是否在活跃时间窗口内
   * @returns {boolean}
   */
  isActiveHour: function () {
    var hour = new Date().getHours();
    var hours = settings.activeHours;
    if (!hours) return true; // 未配置则不限制
    return hour >= hours.start && hour < hours.end;
  },

  /**
   * 获取当前时段的操作建议延迟倍率
   * 高峰时段延迟短、低谷时段延迟长
   * @returns {number} 倍率 (0.5 ~ 2.0)
   */
  getTimeMultiplier: function () {
    var hour = new Date().getHours();
    var hours = settings.activeHours;
    if (!hours || !hours.peaks) return 1.0;

    for (var i = 0; i < hours.peaks.length; i++) {
      var peak = hours.peaks[i];
      if (hour >= peak.start && hour < peak.end) {
        // 高峰时段：权重越高，延迟越短
        return Math.max(0.5, 1.0 - (peak.weight / 100));
      }
    }
    // 非高峰时段：延迟稍长
    return 1.5;
  },

  /**
   * 增强的拟人滑动 — 带速度变化和微抖动
   * @param {number} startX
   * @param {number} startY
   * @param {number} endX
   * @param {number} endY
   */
  humanSwipeEnhanced: function (startX, startY, endX, endY) {
    // 添加起点微抖动（手指按下时不完全静止）
    var jitterX = Math.floor(Math.random() * 6 - 3);
    var jitterY = Math.floor(Math.random() * 6 - 3);
    startX += jitterX;
    startY += jitterY;

    // 滑动距离越长，速度越快
    var distance = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
    var speedFactor = Math.min(1.5, distance / 500);

    var path = bezier.generateSwipePath(startX, startY, endX, endY);
    logger.debug(TAG, "Enhanced swipe: " + path.length + " points, speed=" + speedFactor.toFixed(2));

    var gesturePoints = path.map(function (p) {
      return [p.x, p.y];
    });

    var totalDuration = path.reduce(function (sum, p) {
      return sum + Math.round(p.duration / speedFactor);
    }, 0);

    var args = [totalDuration];
    for (var i = 0; i < gesturePoints.length; i++) {
      args.push(gesturePoints[i]);
    }
    gestures.apply(null, args);
  },

  /**
   * 模拟随机点击偏移 — 不总是精确点击控件中心
   * @param {number} centerX - 控件中心 X
   * @param {number} centerY - 控件中心 Y
   * @param {number} radius - 偏移半径（像素），默认 10
   * @returns {{x: number, y: number}}
   */
  randomClickOffset: function (centerX, centerY, radius) {
    radius = radius || 10;
    var angle = Math.random() * Math.PI * 2;
    var r = Math.random() * radius;
    return {
      x: Math.round(centerX + r * Math.cos(angle)),
      y: Math.round(centerY + r * Math.sin(angle)),
    };
  },
```

- [ ] **Step 3: 修改 wrapAction 集成时间分布**

修改 `wrapAction` 方法，加入时间感知：

```javascript
  wrapAction: function (actionName, actionFn) {
    // 时间窗口检查
    if (!this.isActiveHour()) {
      logger.info(TAG, "Outside active hours, adding long delay");
      sleep(Math.floor(Math.random() * 60000 + 30000)); // 30-90秒
      return false;
    }

    var timeMultiplier = this.getTimeMultiplier();
    this.randomDelay(actionName);

    // 概率跳过（低谷时段偶尔跳过操作，更像真人）
    if (Math.random() < 0.05 * timeMultiplier) {
      logger.info(TAG, "Skipping action (rhythm variation)");
      return false;
    }

    this.maybePause();
    var result = actionFn();
    this.postActionDelay();
    return result;
  },
```

- [ ] **Step 4: Commit**

```bash
git add device/core/anti-detect.js device/config.js
git commit -m "feat(device): add time-distribution and enhanced anti-detect behaviors"
```

---

### Task 5: 风控检测与账号状态上报

**Files:**
- Modify: `device/core/crash-recovery.js`
- Modify: `device/core/api-client.js`
- Modify: `device/main.js`
- Modify: `server/app/routers/device.py`
- Modify: `server/app/models.py`

- [ ] **Step 1: 在 api-client.js 添加风控上报方法**

```javascript
  /**
   * 上报风控检测结果
   * @param {string} accountId - 账号 ID
   * @param {string} riskType - 风控类型 (captcha, risk_control, verify)
   * @param {Object} detail - 风控详情
   */
  reportRiskControl: function (accountId, riskType, detail) {
    return this.post("/api/device/risk-report", {
      account_id: accountId,
      risk_type: riskType,
      detail: detail || {},
      device_id: config.deviceId,
      timestamp: new Date().toISOString(),
    });
  },
```

- [ ] **Step 2: 在 crash-recovery.js 中增强风控检测**

修改 `handleDialogs` 方法，增加更精确的风控检测和上报：

```javascript
  /**
   * 设置当前执行的账号 ID（由 task-executor 调用）
   */
  setAccountId: function (accountId) {
    this._currentAccountId = accountId;
  },

  handleDialogs: function () {
    var dialogButtons = [
      "知道了", "确定", "关闭", "重试",
      "允许", "暂不", "稍后再说", "下次再说",
    ];

    for (var i = 0; i < dialogButtons.length; i++) {
      try {
        var btn = text(dialogButtons[i]).findOnce();
        if (btn) {
          logger.info(TAG, "Found dialog button: " + dialogButtons[i]);
          btn.click();
          sleep(1000);
          return true;
        }
      } catch (e) { /* ignore */ }
    }

    // 风控关键词检测
    var riskPatterns = [
      { keywords: ["验证", "安全验证", "滑动验证"], type: "captcha" },
      { keywords: ["风控", "操作频繁", "请稍后再试"], type: "rate_limit" },
      { keywords: ["异常", "账号异常", "登录异常"], type: "account_risk" },
      { keywords: ["安全检查", "身份验证"], type: "security_check" },
    ];

    for (var j = 0; j < riskPatterns.length; j++) {
      var pattern = riskPatterns[j];
      for (var k = 0; k < pattern.keywords.length; k++) {
        try {
          var riskEl = textContains(pattern.keywords[k]).findOnce();
          if (riskEl) {
            logger.warn(TAG, "Risk detected: " + pattern.type + " (" + pattern.keywords[k] + ")");
            // 上报服务端
            if (this._currentAccountId) {
              try {
                var apiClient = require("./api-client");
                apiClient.reportRiskControl(
                  this._currentAccountId,
                  pattern.type,
                  { keyword: pattern.keywords[k] }
                );
              } catch (e) {
                logger.warn(TAG, "Failed to report risk: " + e.message);
              }
            }
            return "risk_controlled";
          }
        } catch (e) { /* ignore */ }
      }
    }

    return false;
  },
```

- [ ] **Step 3: 在 models.py 添加风控上报模型**

```python
class RiskReport(BaseModel):
    account_id: str
    risk_type: str  # captcha, rate_limit, account_risk, security_check
    detail: dict[str, Any] = Field(default_factory=dict)
    device_id: str = ""
    timestamp: str = ""
```

- [ ] **Step 4: 在 device.py 路由添加风控上报端点**

```python
@router.post("/risk-report")
def report_risk(
    report: RiskReport,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Device reports risk control detection. Marks account as risk_controlled."""
    from app.db_models import Account
    account = db.query(Account).filter(Account.id == report.account_id).first()
    if account and account.status == "active":
        account.status = "risk_controlled"
        db.commit()
    return {"status": "acknowledged", "account_status": "risk_controlled"}
```

- [ ] **Step 5: 在 task-executor.js 中设置当前账号 ID**

修改 `task-executor.js`，在执行任务前设置账号 ID 给 crash-recovery：

```javascript
// 在 execute 方法中，handler.execute 之前添加：
    var crashRecovery = require("./crash-recovery");
    if (task.account_id) {
      crashRecovery.setAccountId(task.account_id);
    }
```

- [ ] **Step 6: Commit**

```bash
git add device/core/crash-recovery.js device/core/api-client.js device/main.js device/handlers/base-handler.js server/app/models.py server/app/routers/device.py
git commit -m "feat: add risk control detection and account status reporting"
```

---

### Task 6: 服务端反检测配置与统计 API

**Files:**
- Modify: `server/app/routers/device.py`
- Modify: `server/app/config.py`
- Create: `server/tests/test_anti_detect_api.py`

- [ ] **Step 1: 在 config.py 添加反检测默认配置**

```python
# 反检测默认配置（可通过环境变量覆盖）
ANTI_DETECT_CONFIG_VERSION = 1  # 修改配置时递增此版本号

ANTI_DETECT_CONFIG = {
    "delay_min": 1000,
    "delay_max": 5000,
    "rhythm_variation": 0.3,
    "pause_probability": 0.1,
    "pause_min": 5000,
    "pause_max": 15000,
    "active_hours": {
        "start": 7,
        "end": 23,
        "peaks": [
            {"start": 7, "end": 9, "weight": 20},
            {"start": 11, "end": 13, "weight": 25},
            {"start": 17, "end": 20, "weight": 30},
            {"start": 20, "end": 23, "weight": 25},
        ],
    },
}
```

- [ ] **Step 2: 在 poll 响应中附加反检测配置**

修改 `device.py` 的 `poll_tasks` 端点，将反检测配置附加到响应中：

```python
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION

@router.get("/poll", response_model=PollResponse)
def poll_tasks(
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.get_pending_task(db, device_id)
    version = selector_service.get_version(db)

    from app.services.device_service import device_service
    device_info = device_service.get_device_status(db, device_id)
    proxy = device_info.get("proxy_config") if device_info else None

    cancelled_task = task_service.check_cancelled_running(db, device_id)

    return PollResponse(
        task=task,
        selectors_version=version,
        proxy=proxy,
        cancelled_task_id=cancelled_task.id if cancelled_task else None,
        anti_detect_config=ANTI_DETECT_CONFIG,
        anti_detect_config_version=ANTI_DETECT_CONFIG_VERSION,
    )
```

- [ ] **Step 3: 在 models.py 的 PollResponse 添加字段**

```python
class PollResponse(BaseModel):
    task: Optional[Task] = None
    selectors_version: int = 1
    proxy: Optional[dict[str, Any]] = None
    cancelled_task_id: Optional[str] = None
    anti_detect_config: Optional[dict[str, Any]] = None
    anti_detect_config_version: int = 1
```

- [ ] **Step 4: 编写反检测 API 测试**

```python
"""Anti-detect configuration API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.deps import verify_device_secret


@pytest.fixture
def client():
    app.dependency_overrides[verify_device_secret] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_poll_includes_anti_detect_config(client):
    response = client.get("/api/device/poll", params={"device_id": "test-dev"})
    assert response.status_code == 200
    data = response.json()
    assert "anti_detect_config" in data
    config = data["anti_detect_config"]
    assert "delay_min" in config
    assert "active_hours" in config
    assert "peaks" in config["active_hours"]


def test_poll_includes_anti_detect_config_version(client):
    response = client.get("/api/device/poll", params={"device_id": "test-dev"})
    assert response.status_code == 200
    data = response.json()
    assert "anti_detect_config_version" in data
    assert isinstance(data["anti_detect_config_version"], int)
    assert data["anti_detect_config_version"] >= 1


def test_poll_includes_proxy_when_configured(client):
    response = client.get("/api/device/poll", params={"device_id": "test-dev"})
    assert response.status_code == 200
    # proxy may be None if device has no proxy configured, but field should exist
    assert "proxy" in response.json()


def test_risk_report_marks_account(client):
    """Risk report should mark active account as risk_controlled."""
    # First get an account from seed data
    from app.database import get_db
    from app.main import app as _app
    gen = _app.dependency_overrides[get_db]()
    db = next(gen)
    from app.db_models import Account
    account = db.query(Account).filter(Account.status == "active").first()
    db.close()
    gen.close()

    if not account:
        pytest.skip("No active account in test DB")

    response = client.post("/api/device/risk-report", json={
        "account_id": account.id,
        "risk_type": "captcha",
        "detail": {"keyword": "验证"},
        "device_id": "test-dev",
    })
    assert response.status_code == 200
    assert response.json()["account_status"] == "risk_controlled"


def test_risk_report_unknown_account(client):
    """Risk report with unknown account should not error."""
    response = client.post("/api/device/risk-report", json={
        "account_id": "nonexistent",
        "risk_type": "captcha",
    })
    assert response.status_code == 200
```

- [ ] **Step 5: 运行测试**

Run: `cd server && python -m pytest tests/test_anti_detect_api.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add server/app/config.py server/app/models.py server/app/routers/device.py server/tests/test_anti_detect_api.py
git commit -m "feat(server): add anti-detect config in poll response and risk report endpoint"
```

---

### Task 7: 设备端集成反检测配置动态更新

**Files:**
- Modify: `device/main.js`
- Modify: `device/core/anti-detect.js`

- [ ] **Step 1: 在 anti-detect.js 添加配置动态更新方法**

```javascript
  /**
   * 从服务端配置更新反检测参数
   * @param {Object} serverConfig - 服务端下发的反检测配置
   */
  updateFromServer: function (serverConfig) {
    if (!serverConfig) return;

    if (serverConfig.delay_min !== undefined) settings.delayMin = serverConfig.delay_min;
    if (serverConfig.delay_max !== undefined) settings.delayMax = serverConfig.delay_max;
    if (serverConfig.rhythm_variation !== undefined) settings.rhythmVariation = serverConfig.rhythm_variation;
    if (serverConfig.pause_probability !== undefined) settings.pauseProbability = serverConfig.pause_probability;
    if (serverConfig.pause_min !== undefined) settings.pauseMin = serverConfig.pause_min;
    if (serverConfig.pause_max !== undefined) settings.pauseMax = serverConfig.pause_max;
    if (serverConfig.active_hours !== undefined) settings.activeHours = serverConfig.active_hours;

    logger.info(TAG, "Anti-detect config updated from server");
  },
```

- [ ] **Step 2: 在 main.js 的 poll 响应处理中调用更新**

在 `main.js` 的 poll 响应处理中添加：

```javascript
      if (response) {
        // 应用代理配置
        if (response.proxy) {
          apiClient.setProxy(response.proxy);
        }

        // 更新反检测配置（仅版本变化时）
        if (response.anti_detect_config_version &&
            response.anti_detect_config_version !== config.antiDetectVersion) {
          if (response.anti_detect_config) {
            antiDetect.updateFromServer(response.anti_detect_config);
            config.antiDetectVersion = response.anti_detect_config_version;
          }
        }

        // ... existing code ...
```

在文件顶部确认 `antiDetect` 已导入（应该通过 `taskExecutor` 间接导入，但 main.js 需要直接引用）：

```javascript
var antiDetect = require("./core/anti-detect");
```

- [ ] **Step 3: 运行全量服务端测试确认无回归**

Run: `cd server && python -m pytest -v`
Expected: All existing tests pass + new tests pass

- [ ] **Step 4: Commit**

```bash
git add device/main.js device/core/anti-detect.js
git commit -m "feat(device): dynamically update anti-detect config from server poll"
```

---

### Task 8: 全量测试与验证

- [ ] **Step 1: 运行服务端全量测试**

Run: `cd server && python -m pytest -v`
Expected: All tests pass (existing + Phase 4 new tests)

- [ ] **Step 2: 检查 git log 确认所有提交**

Run: `git log --oneline -15`
Expected: Phase 4 commits visible in order

- [ ] **Step 3: 验证选择器种子数据**

Run: `cd server && python -m app.seed`
Expected: Selectors seeded, no errors

---

## TODOS (deferred)

- **N+1 查询优化**: `get_pending_task` 的配额检查对每个候选任务执行 2 次查询（Account + DailyStats）。当前规模（LIMIT 10）可接受，任务量增长后需批量查询优化。路径: `server/app/services/task_service.py:60-78`

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 7 issues found, all resolved |

- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED — ready to implement

### Review Changes Applied

1. `stats_service.increment()` 改为 `db.flush()`（不 commit），由调用方统一 commit — 保证原子性
2. `DailyStats` 添加 `UniqueConstraint("account_id", "date")` — 防止并发重复行
3. `wrapAction()` 跳过时返回 `false` 而非 `null` — 语义更清晰
4. `test_quota_blocks_task_assignment` 测试隔离修复 — 清理已有 pending 任务
5. 反检测配置添加版本检查机制 — 减少 poll 响应冗余数据
6. 补全 5 个测试缺口：check_quota 边界/无账号、report_result 统计递增、/risk-report 端点、候选全超配额
