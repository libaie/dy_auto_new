# 抖音自动化助手 MVP 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 AutoJS6 操控抖音的核心可行性 — 单设备 + 单账号 + 养号功能 + 配置文件驱动

**Architecture:** FastAPI 后端提供任务管理和配置接口，AutoJS6 设备端通过 HTTP 轮询获取任务并执行。MVP 阶段使用配置文件管理账号和选择器，不使用数据库和 Web 后台。

**Tech Stack:** Python 3.11+ / FastAPI / Pydantic / AutoJS6 (JavaScript)

---

## 文件结构

```
dy_auto/
├── server/                          # Python 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口，挂载路由
│   │   ├── config.py                # 配置加载（从 YAML 文件）
│   │   ├── models.py                # Pydantic 数据模型
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── device.py            # 设备端 API（poll / report / heartbeat）
│   │   │   └── tasks.py             # 任务管理 API（CRUD）
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── task_service.py      # 任务调度逻辑
│   │   │   └── selector_service.py  # 选择器配置读取
│   │   └── data/                    # 运行时数据目录
│   │       └── .gitkeep
│   ├── config/
│   │   ├── accounts.yaml            # 账号配置
│   │   ├── selectors.yaml           # UI 选择器配置
│   │   └── tasks.yaml               # 任务模板配置
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_task_service.py
│   │   ├── test_selector_service.py
│   │   └── test_device_api.py
│   ├── requirements.txt
│   └── pytest.ini
│
├── device/                          # AutoJS6 设备端脚本
│   ├── main.js                      # 入口，主循环
│   ├── config.js                    # 设备配置（后端地址、轮询间隔等）
│   ├── core/
│   │   ├── api-client.js            # HTTP 客户端，与后端通信
│   │   ├── task-executor.js         # 任务执行器，分发到 handler
│   │   ├── ui-operator.js           # UI 操作层（app 生命周期、控件查找）
│   │   ├── selector-loader.js       # 选择器动态加载和缓存
│   │   └── anti-detect.js           # 反检测引擎（延迟、滑动、节奏）
│   ├── handlers/
│   │   ├── nurture.js               # 养号 handler（刷推荐、关注、互动）
│   │   └── base-handler.js          # handler 基类
│   └── utils/
│       ├── logger.js                # 日志工具
│       └── bezier.js                # 贝塞尔曲线工具（拟人滑动）
│
├── .gitignore
├── .env.example
└── docs/
    ├── superpowers/specs/           # 设计文档（已有）
    └── superpowers/plans/           # 实现计划（本文件）
```

---

## Task 1: 项目初始化与环境搭建

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `server/requirements.txt`
- Create: `server/pytest.ini`
- Create: `server/app/__init__.py`
- Create: `server/app/data/.gitkeep`

- [ ] **Step 1: 创建 .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
venv/
.venv/
*.egg

# Environment
.env
*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Runtime data
server/app/data/*.json
server/app/data/*.log

# Node (AutoJS6 device scripts don't use node_modules, but just in case)
node_modules/
```

- [ ] **Step 2: 创建 .env.example**

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Device secret (shared between server and device)
DEVICE_SECRET=change-me-to-a-random-string
```

- [ ] **Step 3: 创建 server/requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.1
pyyaml==6.0.2
python-dotenv==1.0.1
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.24.0
```

- [ ] **Step 4: 创建 server/pytest.ini**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

- [ ] **Step 5: 创建目录结构和 __init__.py**

```bash
mkdir -p server/app/routers server/app/services server/app/data server/config server/tests
mkdir -p device/core device/handlers device/utils
touch server/app/__init__.py server/app/routers/__init__.py server/app/services/__init__.py server/tests/__init__.py
touch server/app/data/.gitkeep
```

- [ ] **Step 6: 安装依赖并验证**

```bash
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"
```

Expected: `FastAPI 0.115.6`

- [ ] **Step 7: Commit**

```bash
git init
git add .
git commit -m "chore: initialize project structure with server dependencies"
```

---

## Task 2: 数据模型定义

**Files:**
- Create: `server/app/models.py`
- Create: `server/tests/test_models.py`

- [ ] **Step 1: 编写数据模型测试**

```python
# server/tests/test_models.py
import pytest
from datetime import datetime
from app.models import Task, TaskType, TaskStatus, AccountConfig, SelectorConfig, SelectorStrategy


def test_task_creation():
    task = Task(
        id="test-001",
        type=TaskType.NURTURE,
        account_id="acc-001",
        device_id="dev-001",
        params={"duration": 30},
    )
    assert task.id == "test-001"
    assert task.type == TaskType.NURTURE
    assert task.status == TaskStatus.PENDING
    assert task.params == {"duration": 30}


def test_task_status_transitions():
    task = Task(
        id="test-002",
        type=TaskType.SEARCH_COMMENT,
        account_id="acc-001",
        device_id="dev-001",
        params={"keyword": "美食", "count": 5},
    )
    assert task.status == TaskStatus.PENDING

    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now()
    assert task.status == TaskStatus.RUNNING

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now()
    task.result = {"success_count": 4, "fail_count": 1}
    assert task.status == TaskStatus.COMPLETED
    assert task.result["success_count"] == 4


def test_account_config():
    account = AccountConfig(
        id="acc-001",
        nickname="测试账号",
        douyin_id="test_user_123",
        daily_limits={"likes": 50, "comments": 20},
    )
    assert account.id == "acc-001"
    assert account.daily_limits["likes"] == 50


def test_selector_config():
    selector = SelectorConfig(
        action_name="like_video",
        strategies=[
            SelectorStrategy(type="text", value="赞", priority=1),
            SelectorStrategy(type="id", value="com.ss.android.ugc.aweme:id/like_btn", priority=2),
        ],
    )
    assert selector.action_name == "like_video"
    assert len(selector.strategies) == 2
    assert selector.strategies[0].type == "text"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server
python -m pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: 实现数据模型**

```python
# server/app/models.py
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class TaskType(str, Enum):
    NURTURE = "nurture"
    SEARCH_COMMENT = "search_comment"
    SEARCH_LIKE = "search_like"
    SEARCH_DM = "search_dm"
    REPLY_COMMENT = "reply_comment"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    account_id: str
    device_id: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    retry_count: int = 0


class AccountConfig(BaseModel):
    id: str
    nickname: str
    douyin_id: str
    status: str = "active"
    daily_limits: dict[str, int] = Field(default_factory=lambda: {
        "likes": 50,
        "comments": 20,
        "follows": 20,
        "dms": 10,
        "replies": 15,
    })


class SelectorStrategy(BaseModel):
    type: str  # text, id, desc, coordinate
    value: Optional[str] = None
    x_percent: Optional[float] = None
    y_percent: Optional[float] = None
    priority: int


class SelectorConfig(BaseModel):
    action_name: str
    platform_version: str = "default"
    strategies: list[SelectorStrategy]
    version: int = 1


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None


class TaskResultReport(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[dict[str, Any]] = None
    ui_snapshot: Optional[dict[str, Any]] = None


class PollResponse(BaseModel):
    task: Optional[Task] = None
    selectors_version: int = 1
    proxy: Optional[dict[str, Any]] = None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd server
python -m pytest tests/test_models.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add server/app/models.py server/tests/test_models.py
git commit -m "feat: add Pydantic data models for tasks, accounts, selectors"
```

---

## Task 3: 配置加载服务

**Files:**
- Create: `server/app/config.py`
- Create: `server/config/accounts.yaml`
- Create: `server/config/selectors.yaml`
- Create: `server/config/tasks.yaml`

- [ ] **Step 1: 创建配置文件**

```yaml
# server/config/accounts.yaml
accounts:
  - id: "acc-001"
    nickname: "测试账号1"
    douyin_id: "test_user_001"
    status: "active"
    daily_limits:
      likes: 50
      comments: 20
      follows: 20
      dms: 10
      replies: 15
```

```yaml
# server/config/selectors.yaml
# UI 选择器配置 — 抖音 UI 变更时在此修改
# 策略类型: text(控件文本), id(控件ID), desc(内容描述), coordinate(坐标百分比)
version: 1
selectors:
  - action_name: "open_app"
    strategies:
      - { type: "package", value: "com.ss.android.ugc.aweme", priority: 1 }

  - action_name: "search_tab"
    strategies:
      - { type: "text", value: "搜索", priority: 1 }
      - { type: "id", value: "com.ss.android.ugc.aweme:id/et_search_kw", priority: 2 }
      - { type: "desc", value: "搜索", priority: 3 }

  - action_name: "search_input"
    strategies:
      - { type: "id", value: "com.ss.android.ugc.aweme:id/et_search_kw", priority: 1 }
      - { type: "className", value: "android.widget.EditText", priority: 2 }

  - action_name: "search_button"
    strategies:
      - { type: "text", value: "搜索", priority: 1 }
      - { type: "desc", value: "搜索", priority: 2 }

  - action_name: "like_button"
    strategies:
      - { type: "text", value: "赞", priority: 1 }
      - { type: "desc", value: "点赞", priority: 2 }
      - { type: "id", value: "com.ss.android.ugc.aweme:id/like_icon", priority: 3 }

  - action_name: "comment_input"
    strategies:
      - { type: "text", value: "善语结善缘，恶语伤人心", priority: 1 }
      - { type: "id", value: "com.ss.android.ugc.aweme:id/comment_et", priority: 2 }
      - { type: "desc", value: "评论", priority: 3 }

  - action_name: "comment_submit"
    strategies:
      - { type: "text", value: "发送", priority: 1 }
      - { type: "desc", value: "发送", priority: 2 }

  - action_name: "follow_button"
    strategies:
      - { type: "text", value: "关注", priority: 1 }
      - { type: "desc", value: "关注", priority: 2 }

  - action_name: "profile_more"
    strategies:
      - { type: "desc", value: "更多", priority: 1 }
      - { type: "id", value: "com.ss.android.ugc.aweme:id/detail_right_arrow", priority: 2 }

  - action_name: "message_button"
    strategies:
      - { type: "text", value: "私信", priority: 1 }
      - { type: "desc", value: "私信", priority: 2 }

  - action_name: "dm_input"
    strategies:
      - { type: "id", value: "com.ss.android.ugc.aweme:id/et_input", priority: 1 }
      - { type: "className", value: "android.widget.EditText", priority: 2 }

  - action_name: "dm_send"
    strategies:
      - { type: "text", value: "发送", priority: 1 }
      - { type: "desc", value: "发送", priority: 2 }
```

```yaml
# server/config/tasks.yaml
# 任务模板 — 预定义常用任务配置
task_templates:
  - name: "养号30分钟"
    type: "nurture"
    params:
      duration: 30
      actions:
        - type: "browse_feed"
          weight: 70
        - type: "like"
          weight: 20
        - type: "follow"
          weight: 10

  - name: "搜索关键词评论"
    type: "search_comment"
    params:
      keyword: ""
      count: 10
      content_template_id: ""

  - name: "搜索关键词点赞"
    type: "search_like"
    params:
      keyword: ""
      count: 20
```

- [ ] **Step 2: 实现配置加载模块**

```python
# server/app/config.py
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

# 项目根目录 (server/)
SERVER_DIR = Path(__file__).parent.parent
CONFIG_DIR = SERVER_DIR / "config"
DATA_DIR = SERVER_DIR / "app" / "data"

# 环境变量
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
DEVICE_SECRET = os.getenv("DEVICE_SECRET", "change-me-to-a-random-string")


def _load_yaml(filename: str) -> dict[str, Any]:
    """加载 YAML 配置文件"""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_accounts_config() -> list[dict[str, Any]]:
    """加载账号配置"""
    data = _load_yaml("accounts.yaml")
    return data.get("accounts", [])


def load_selectors_config() -> tuple[int, list[dict[str, Any]]]:
    """加载选择器配置，返回 (version, selectors)"""
    data = _load_yaml("selectors.yaml")
    version = data.get("version", 1)
    selectors = data.get("selectors", [])
    return version, selectors


def load_task_templates() -> list[dict[str, Any]]:
    """加载任务模板"""
    data = _load_yaml("tasks.yaml")
    return data.get("task_templates", [])


def save_tasks_to_file(tasks: list[dict[str, Any]]) -> None:
    """持久化任务列表到文件（MVP 简单存储）"""
    filepath = DATA_DIR / "tasks.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    import json
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)


def load_tasks_from_file() -> list[dict[str, Any]]:
    """从文件加载任务列表"""
    filepath = DATA_DIR / "tasks.json"
    if not filepath.exists():
        return []
    import json
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 3: 验证配置加载**

```bash
cd server
python -c "
from app.config import load_accounts_config, load_selectors_config, load_task_templates
accounts = load_accounts_config()
print(f'Accounts: {len(accounts)} - {accounts[0][\"nickname\"]}')
version, selectors = load_selectors_config()
print(f'Selectors: v{version}, {len(selectors)} actions')
templates = load_task_templates()
print(f'Templates: {len(templates)}')
"
```

Expected:
```
Accounts: 1 - 测试账号1
Selectors: v1, 12 actions
Templates: 3
```

- [ ] **Step 4: Commit**

```bash
git add server/app/config.py server/config/
git commit -m "feat: add YAML config loading for accounts, selectors, task templates"
```

---

## Task 4: 任务调度服务

**Files:**
- Create: `server/app/services/__init__.py`
- Create: `server/app/services/task_service.py`
- Create: `server/tests/test_task_service.py`

- [ ] **Step 1: 编写任务服务测试**

```python
# server/tests/test_task_service.py
import pytest
from app.models import Task, TaskType, TaskStatus
from app.services.task_service import TaskService


@pytest.fixture
def service():
    return TaskService()


def test_create_task(service):
    task = service.create_task(
        task_type=TaskType.NURTURE,
        account_id="acc-001",
        params={"duration": 30},
    )
    assert task.type == TaskType.NURTURE
    assert task.account_id == "acc-001"
    assert task.status == TaskStatus.PENDING
    assert task.id is not None


def test_get_pending_task(service):
    service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    task = service.get_pending_task("dev-001")
    assert task is not None
    assert task.status == TaskStatus.RUNNING
    assert task.device_id == "dev-001"
    assert task.started_at is not None


def test_no_duplicate_assignment(service):
    service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    task1 = service.get_pending_task("dev-001")
    task2 = service.get_pending_task("dev-002")
    assert task1 is not None
    assert task2 is None  # 已被 dev-001 领取


def test_report_result(service):
    task = service.create_task(TaskType.SEARCH_COMMENT, "acc-001", {"keyword": "美食", "count": 5})
    service.get_pending_task("dev-001")

    updated = service.report_result(
        task_id=task.id,
        status=TaskStatus.COMPLETED,
        result={"success_count": 4, "fail_count": 1},
    )
    assert updated.status == TaskStatus.COMPLETED
    assert updated.result["success_count"] == 4
    assert updated.completed_at is not None


def test_report_failure_increments_retry(service):
    task = service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    service.get_pending_task("dev-001")

    service.report_result(task.id, TaskStatus.FAILED, {"error": "UI not found"})
    updated = service.get_task(task.id)
    assert updated.retry_count == 1
    assert updated.status == TaskStatus.PENDING  # 重试


def test_max_retries(service):
    task = service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})

    for i in range(3):
        service.get_pending_task("dev-001")
        service.report_result(task.id, TaskStatus.FAILED, {"error": "fail"})

    updated = service.get_task(task.id)
    assert updated.status == TaskStatus.FAILED  # 超过最大重试次数
    assert updated.retry_count == 3


def test_list_tasks(service):
    service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    service.create_task(TaskType.SEARCH_LIKE, "acc-001", {"keyword": "美食", "count": 10})

    tasks = service.list_tasks()
    assert len(tasks) == 2

    pending = service.list_tasks(status=TaskStatus.PENDING)
    assert len(pending) == 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server
python -m pytest tests/test_task_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 3: 实现任务调度服务**

```python
# server/app/services/task_service.py
from datetime import datetime
from typing import Optional

from app.models import Task, TaskType, TaskStatus

MAX_RETRIES = 3


class TaskService:
    """MVP 任务调度服务 — 内存存储，单设备模式"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def create_task(
        self,
        task_type: TaskType,
        account_id: str,
        params: dict,
        scheduled_at: Optional[datetime] = None,
    ) -> Task:
        task = Task(
            type=task_type,
            account_id=account_id,
            params=params,
            scheduled_at=scheduled_at,
        )
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_pending_task(self, device_id: str) -> Optional[Task]:
        """领取一个待执行任务（乐观锁：原子性 status 更新）"""
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.RUNNING
                task.device_id = device_id
                task.started_at = datetime.now()
                return task
        return None

    def report_result(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        ui_snapshot: Optional[dict] = None,
    ) -> Task:
        task = self._tasks[task_id]
        if status == TaskStatus.COMPLETED:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
        elif status == TaskStatus.FAILED:
            task.retry_count += 1
            if task.retry_count >= MAX_RETRIES:
                task.status = TaskStatus.FAILED
                task.result = result
                task.completed_at = datetime.now()
            else:
                task.status = TaskStatus.PENDING  # 重新排队
                task.device_id = ""
                task.started_at = None
        return task

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks


# 模块级单例 — 设备端 API 和任务管理 API 共用同一实例
task_service = TaskService()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd server
python -m pytest tests/test_task_service.py -v
```

Expected: 7 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add server/app/services/task_service.py server/tests/test_task_service.py
git commit -m "feat: add task scheduling service with retry logic"
```

---

## Task 5: 选择器服务

**Files:**
- Create: `server/app/services/selector_service.py`
- Create: `server/tests/test_selector_service.py`

- [ ] **Step 1: 编写选择器服务测试**

```python
# server/tests/test_selector_service.py
import pytest
from app.services.selector_service import SelectorService


@pytest.fixture
def service():
    return SelectorService()


def test_get_selectors(service):
    version, selectors = service.get_all_selectors()
    assert version == 1
    assert len(selectors) > 0


def test_get_selector_by_action(service):
    selector = service.get_selector("like_video")
    assert selector is not None
    assert selector["action_name"] == "like_video"
    assert len(selector["strategies"]) > 0


def test_get_nonexistent_selector(service):
    selector = service.get_selector("nonexistent_action")
    assert selector is None


def test_selectors_version(service):
    version, _ = service.get_all_selectors()
    assert isinstance(version, int)
    assert version >= 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server
python -m pytest tests/test_selector_service.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现选择器服务**

```python
# server/app/services/selector_service.py
from typing import Any, Optional

from app.config import load_selectors_config


class SelectorService:
    """选择器配置服务 — 从 YAML 加载，支持按 action_name 查询"""

    def __init__(self):
        self._version: int = 0
        self._selectors: dict[str, dict] = {}
        self._load()

    def _load(self):
        version, selectors_list = load_selectors_config()
        self._version = version
        self._selectors = {s["action_name"]: s for s in selectors_list}

    def get_all_selectors(self) -> tuple[int, list[dict[str, Any]]]:
        """返回 (version, selectors_list)"""
        return self._version, list(self._selectors.values())

    def get_selector(self, action_name: str) -> Optional[dict[str, Any]]:
        """按 action_name 获取单个选择器配置"""
        return self._selectors.get(action_name)

    def get_version(self) -> int:
        return self._version
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd server
python -m pytest tests/test_selector_service.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add server/app/services/selector_service.py server/tests/test_selector_service.py
git commit -m "feat: add selector service for UI element config management"
```

---

## Task 6: 设备端 API 路由

**Files:**
- Create: `server/app/routers/device.py`
- Create: `server/tests/test_device_api.py`
- Modify: `server/app/main.py`

- [ ] **Step 1: 编写设备端 API 测试**

```python
# server/tests/test_device_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import DEVICE_SECRET

client = TestClient(app)


def test_device_poll_no_task():
    response = client.get(
        "/api/device/poll",
        params={"device_id": "dev-001"},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] is None
    assert "selectors_version" in data


def test_device_poll_with_task():
    # 先创建一个任务
    client.post(
        "/api/tasks",
        json={"type": "nurture", "account_id": "acc-001", "params": {"duration": 30}},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )

    response = client.get(
        "/api/device/poll",
        params={"device_id": "dev-001"},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] is not None
    assert data["task"]["status"] == "running"


def test_device_report():
    # 创建任务并领取
    create_resp = client.post(
        "/api/tasks",
        json={"type": "nurture", "account_id": "acc-001", "params": {"duration": 30}},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    task_id = create_resp.json()["id"]

    poll_resp = client.get(
        "/api/device/poll",
        params={"device_id": "dev-001"},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )

    # 上报结果
    report_resp = client.post(
        "/api/device/report",
        json={
            "task_id": task_id,
            "status": "completed",
            "result": {"success_count": 1, "fail_count": 0},
        },
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    assert report_resp.status_code == 200
    assert report_resp.json()["status"] == "completed"


def test_device_auth_required():
    response = client.get("/api/device/poll", params={"device_id": "dev-001"})
    assert response.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server
python -m pytest tests/test_device_api.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现设备端 API 路由**

```python
# server/app/routers/device.py
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional

from app.config import DEVICE_SECRET
from app.models import TaskResultReport, PollResponse
from app.services.task_service import task_service
from app.services.selector_service import SelectorService

router = APIRouter(prefix="/api/device", tags=["device"])

selector_service = SelectorService()


def _verify_device_secret(x_device_secret: Optional[str] = Header(None)):
    if x_device_secret != DEVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid device secret")


@router.get("/poll", response_model=PollResponse)
def poll_tasks(
    device_id: str = Query(...),
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)

    task = task_service.get_pending_task(device_id)
    version = selector_service.get_version()

    return PollResponse(
        task=task,
        selectors_version=version,
    )


@router.post("/report")
def report_result(
    report: TaskResultReport,
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)

    task = task_service.report_result(
        task_id=report.task_id,
        status=report.status,
        result=report.result,
        ui_snapshot=report.ui_snapshot,
    )
    return task


@router.post("/heartbeat")
def heartbeat(
    device_id: str = Query(...),
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)
    return {"status": "ok", "device_id": device_id}


@router.get("/selectors")
def get_selectors(
    version: int = Query(0),
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)

    current_version, selectors = selector_service.get_all_selectors()
    if version == current_version:
        return {"version": current_version, "selectors": None, "changed": False}

    return {
        "version": current_version,
        "selectors": selectors,
        "changed": True,
    }
```

- [ ] **Step 4: 实现 FastAPI 主入口**

```python
# server/app/main.py
from fastapi import FastAPI
from app.routers import device
from app.config import DEBUG

app = FastAPI(
    title="抖音自动化助手",
    version="0.1.0-mvp",
    debug=DEBUG,
)

app.include_router(device.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0-mvp"}
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd server
python -m pytest tests/test_device_api.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add server/app/routers/device.py server/app/main.py server/tests/test_device_api.py
git commit -m "feat: add device API endpoints (poll, report, heartbeat, selectors)"
```

---

## Task 7: 任务管理 API 路由

**Files:**
- Create: `server/app/routers/tasks.py`
- Modify: `server/app/main.py`

- [ ] **Step 1: 实现任务管理路由**

```python
# server/app/routers/tasks.py
from fastapi import APIRouter, Header, Query
from typing import Optional

from app.config import DEVICE_SECRET
from app.models import TaskCreateRequest, TaskStatus
from app.services.task_service import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
def create_task(
    request: TaskCreateRequest,
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    task = task_service.create_task(
        task_type=request.type,
        account_id=request.account_id,
        params=request.params,
        scheduled_at=request.scheduled_at,
    )
    return task


@router.get("")
def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    tasks = task_service.list_tasks(status=status)
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    task = task_service.get_task(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

- [ ] **Step 2: 挂载路由到主入口**

```python
# server/app/main.py (更新)
from fastapi import FastAPI
from app.routers import device, tasks
from app.config import DEBUG

app = FastAPI(
    title="抖音自动化助手",
    version="0.1.0-mvp",
    debug=DEBUG,
)

app.include_router(device.router)
app.include_router(tasks.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0-mvp"}
```

- [ ] **Step 3: 启动服务验证**

```bash
cd server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
sleep 2
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-Device-Secret: change-me-to-a-random-string" \
  -d '{"type": "nurture", "account_id": "acc-001", "params": {"duration": 30}}'
```

Expected: Health check returns `{"status":"ok"}`, task creation returns task JSON with `"status":"pending"`

- [ ] **Step 4: Commit**

```bash
git add server/app/routers/tasks.py server/app/main.py
git commit -m "feat: add task management API (create, list, get)"
```

---

## Task 8: AutoJS6 设备配置与工具模块

**Files:**
- Create: `device/config.js`
- Create: `device/utils/logger.js`
- Create: `device/utils/bezier.js`

- [ ] **Step 1: 创建设备配置**

```javascript
// device/config.js
var config = {
  // 后端服务地址
  serverUrl: "http://192.168.1.100:8000",

  // 设备标识（首次运行自动生成并保存）
  deviceId: "",

  // 设备密钥（与后端 DEVICE_SECRET 一致）
  deviceSecret: "change-me-to-a-random-string",

  // 轮询间隔（毫秒）
  pollInterval: 10000,

  // 心跳间隔（毫秒）
  heartbeatInterval: 60000,

  // 反检测配置
  antiDetect: {
    // 操作前随机延迟范围（毫秒）
    delayMin: 1000,
    delayMax: 5000,
    // 操作节奏波动（±百分比）
    rhythmVariation: 0.3,
    // 随机停顿概率（0-1）
    pauseProbability: 0.1,
    // 随机停顿时长范围（毫秒）
    pauseMin: 5000,
    pauseMax: 15000,
  },

  // 日志级别: "debug", "info", "warn", "error"
  logLevel: "info",
};

// 生成或读取设备 ID
(function () {
  var storage = storages.create("dy_auto");
  var savedId = storage.get("device_id", "");
  if (!savedId) {
    savedId = "dev-" + new Date().getTime() + "-" + Math.random().toString(36).substr(2, 6);
    storage.put("device_id", savedId);
  }
  config.deviceId = savedId;
})();

module.exports = config;
```

- [ ] **Step 2: 创建日志工具**

```javascript
// device/utils/logger.js
var config = require("../config");

var LOG_LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };

var logger = {
  _level: LOG_LEVELS[config.logLevel] || 0,

  _log: function (level, tag, msg) {
    if (LOG_LEVELS[level] >= this._level) {
      var timestamp = new Date().toISOString();
      var prefix = "[" + timestamp + "] [" + level.toUpperCase() + "] [" + tag + "]";
      console.log(prefix + " " + msg);
    }
  },

  debug: function (tag, msg) { this._log("debug", tag, msg); },
  info: function (tag, msg) { this._log("info", tag, msg); },
  warn: function (tag, msg) { this._log("warn", tag, msg); },
  error: function (tag, msg) { this._log("error", tag, msg); },
};

module.exports = logger;
```

- [ ] **Step 3: 创建贝塞尔曲线工具（拟人滑动）**

```javascript
// device/utils/bezier.js
/**
 * 贝塞尔曲线计算 — 用于生成拟人滑动轨迹
 */

function factorial(n) {
  var result = 1;
  for (var i = 2; i <= n; i++) result *= i;
  return result;
}

function bernstein(t, i, n) {
  return (
    (factorial(n) / (factorial(i) * factorial(n - i))) *
    Math.pow(t, i) *
    Math.pow(1 - t, n - i)
  );
}

/**
 * 计算贝塞尔曲线上的点
 * @param {Array} controlPoints - 控制点数组 [{x, y}, ...]
 * @param {number} t - 参数 (0-1)
 * @returns {{x: number, y: number}}
 */
function bezierPoint(controlPoints, t) {
  var n = controlPoints.length - 1;
  var x = 0, y = 0;
  for (var i = 0; i <= n; i++) {
    var b = bernstein(t, i, n);
    x += controlPoints[i].x * b;
    y += controlPoints[i].y * b;
  }
  return { x: Math.round(x), y: Math.round(y) };
}

/**
 * 生成拟人滑动轨迹
 * @param {number} startX - 起点 X
 * @param {number} startY - 起点 Y
 * @param {number} endX - 终点 X
 * @param {number} endY - 终点 Y
 * @param {number} steps - 轨迹点数 (默认 10-20 之间的随机值)
 * @returns {Array} 轨迹点数组 [{x, y, duration}, ...]
 */
function generateSwipePath(startX, startY, endX, endY, steps) {
  steps = steps || (Math.floor(Math.random() * 11) + 10); // 10-20

  // 生成 2 个随机中间控制点，模拟手指不走直线
  var midX1 = startX + (endX - startX) * 0.3 + (Math.random() - 0.5) * 50;
  var midY1 = startY + (endY - startY) * 0.3 + (Math.random() - 0.5) * 50;
  var midX2 = startX + (endX - startX) * 0.7 + (Math.random() - 0.5) * 50;
  var midY2 = startY + (endY - startY) * 0.7 + (Math.random() - 0.5) * 50;

  var controlPoints = [
    { x: startX, y: startY },
    { x: midX1, y: midY1 },
    { x: midX2, y: midY2 },
    { x: endX, y: endY },
  ];

  var path = [];
  for (var i = 0; i <= steps; i++) {
    var t = i / steps;
    var point = bezierPoint(controlPoints, t);
    // 变速：中间快两头慢
    var duration = Math.round(10 + 20 * Math.sin(t * Math.PI));
    path.push({ x: point.x, y: point.y, duration: duration });
  }
  return path;
}

module.exports = {
  generateSwipePath: generateSwipePath,
  bezierPoint: bezierPoint,
};
```

- [ ] **Step 4: Commit**

```bash
git add device/config.js device/utils/
git commit -m "feat: add device config, logger, and bezier curve utils"
```

---

## Task 9: HTTP 客户端模块

**Files:**
- Create: `device/core/api-client.js`

- [ ] **Step 1: 实现 HTTP 客户端**

```javascript
// device/core/api-client.js
var config = require("../config");
var logger = require("../utils/logger");

var TAG = "API";

var apiClient = {
  /**
   * 发送 HTTP GET 请求
   * @param {string} path - API 路径 (如 "/api/device/poll")
   * @param {Object} params - 查询参数
   * @returns {Object|null} 响应 JSON 或 null
   */
  get: function (path, params) {
    var url = config.serverUrl + path;
    if (params) {
      var queryParts = [];
      for (var key in params) {
        queryParts.push(encodeURIComponent(key) + "=" + encodeURIComponent(params[key]));
      }
      url += "?" + queryParts.join("&");
    }

    try {
      var response = http.get(url, {
        headers: { "X-Device-Secret": config.deviceSecret },
        timeout: 10000,
      });

      if (response.statusCode === 200) {
        return JSON.parse(response.body);
      } else {
        logger.error(TAG, "GET " + path + " failed: " + response.statusCode + " " + response.body);
        return null;
      }
    } catch (e) {
      logger.error(TAG, "GET " + path + " error: " + e.message);
      return null;
    }
  },

  /**
   * 发送 HTTP POST 请求
   * @param {string} path - API 路径
   * @param {Object} body - 请求体
   * @returns {Object|null} 响应 JSON 或 null
   */
  post: function (path, body) {
    var url = config.serverUrl + path;

    try {
      var response = http.post(url, {
        headers: {
          "Content-Type": "application/json",
          "X-Device-Secret": config.deviceSecret,
        },
        body: JSON.stringify(body),
        timeout: 10000,
      });

      if (response.statusCode === 200) {
        return JSON.parse(response.body);
      } else {
        logger.error(TAG, "POST " + path + " failed: " + response.statusCode + " " + response.body);
        return null;
      }
    } catch (e) {
      logger.error(TAG, "POST " + path + " error: " + e.message);
      return null;
    }
  },

  /**
   * 轮询任务
   * @returns {Object|null} poll response
   */
  poll: function () {
    return this.get("/api/device/poll", { device_id: config.deviceId });
  },

  /**
   * 上报任务结果
   * @param {string} taskId
   * @param {string} status - "completed" | "failed"
   * @param {Object} result
   * @param {Object} uiSnapshot
   * @returns {Object|null}
   */
  report: function (taskId, status, result, uiSnapshot) {
    return this.post("/api/device/report", {
      task_id: taskId,
      status: status,
      result: result || {},
      ui_snapshot: uiSnapshot || null,
    });
  },

  /**
   * 发送心跳
   */
  heartbeat: function () {
    this.post("/api/device/heartbeat?device_id=" + config.deviceId, {});
  },

  /**
   * 获取选择器配置
   * @param {number} currentVersion - 本地缓存版本号
   * @returns {Object|null}
   */
  fetchSelectors: function (currentVersion) {
    return this.get("/api/device/selectors", {
      version: currentVersion || 0,
    });
  },
};

module.exports = apiClient;
```

- [ ] **Step 2: Commit**

```bash
git add device/core/api-client.js
git commit -m "feat: add HTTP client for device-server communication"
```

---

## Task 10: 选择器加载器

**Files:**
- Create: `device/core/selector-loader.js`

- [ ] **Step 1: 实现选择器动态加载器**

```javascript
// device/core/selector-loader.js
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "SELECTOR";

var selectorLoader = {
  _cache: {},       // action_name -> selector config
  _version: 0,      // 本地缓存版本号
  _initialized: false,

  /**
   * 初始化 — 从后端拉取全量选择器
   */
  init: function () {
    logger.info(TAG, "Loading selectors from server...");
    var response = apiClient.fetchSelectors(0);
    if (response && response.selectors) {
      this._applySelectors(response.selectors);
      this._version = response.version;
      this._initialized = true;
      logger.info(TAG, "Loaded " + Object.keys(this._cache).length + " selectors, version=" + this._version);
    } else {
      logger.warn(TAG, "Failed to load selectors, using empty cache");
      this._initialized = true;
    }
  },

  /**
   * 检查并增量更新选择器
   * @param {number} serverVersion - 服务端版本号
   */
  checkAndUpdate: function (serverVersion) {
    if (serverVersion > this._version) {
      logger.info(TAG, "Selectors outdated (local=" + this._version + ", server=" + serverVersion + "), updating...");
      var response = apiClient.fetchSelectors(this._version);
      if (response && response.changed && response.selectors) {
        this._applySelectors(response.selectors);
        this._version = response.version;
        logger.info(TAG, "Selectors updated to version " + this._version);
      }
    }
  },

  /**
   * 获取指定操作的选择器配置
   * @param {string} actionName - 操作名称 (如 "like_video")
   * @returns {Object|null} { strategies: [...] }
   */
  get: function (actionName) {
    return this._cache[actionName] || null;
  },

  /**
   * 应用选择器配置到缓存
   * @param {Array} selectors
   */
  _applySelectors: function (selectors) {
    for (var i = 0; i < selectors.length; i++) {
      var s = selectors[i];
      this._cache[s.action_name] = s;
    }
  },

  /**
   * 获取当前版本号
   */
  getVersion: function () {
    return this._version;
  },
};

module.exports = selectorLoader;
```

- [ ] **Step 2: Commit**

```bash
git add device/core/selector-loader.js
git commit -m "feat: add dynamic selector loader with cache and incremental update"
```

---

## Task 11: UI 操作层

**Files:**
- Create: `device/core/ui-operator.js`

- [ ] **Step 1: 实现 UI 操作层（App 生命周期 + 控件查找）**

```javascript
// device/core/ui-operator.js
var selectorLoader = require("./selector-loader");
var logger = require("../utils/logger");

var TAG = "UI";

var uiOperator = {
  /**
   * 启动抖音
   * @returns {boolean}
   */
  openApp: function () {
    logger.info(TAG, "Opening Douyin...");
    app.launchApp("抖音");
    sleep(3000); // 等待 App 启动
    if (currentPackage() === "com.ss.android.ugc.aweme") {
      logger.info(TAG, "Douyin opened successfully");
      return true;
    }
    logger.error(TAG, "Failed to open Douyin");
    return false;
  },

  /**
   * 关闭抖音
   */
  closeApp: function () {
    logger.info(TAG, "Closing Douyin...");
    app.stop("com.ss.android.ugc.aweme");
    sleep(1000);
  },

  /**
   * 检查抖音是否在前台
   * @returns {boolean}
   */
  isAppActive: function () {
    return currentPackage() === "com.ss.android.ugc.aweme";
  },

  /**
   * 使用选择器查找控件
   * 按策略优先级依次尝试：text -> id -> desc -> coordinate
   * @param {string} actionName - 操作名称
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {UiObject|null} 找到的控件，或 null
   */
  findElement: function (actionName, timeout) {
    timeout = timeout || 5000;
    var selector = selectorLoader.get(actionName);
    if (!selector) {
      logger.error(TAG, "No selector config for action: " + actionName);
      return null;
    }

    var strategies = selector.strategies.sort(function (a, b) {
      return a.priority - b.priority;
    });

    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      for (var i = 0; i < strategies.length; i++) {
        var s = strategies[i];
        var element = this._findByStrategy(s);
        if (element) {
          logger.debug(TAG, "Found element for '" + actionName + "' via " + s.type);
          return element;
        }
      }
      sleep(500);
    }

    logger.warn(TAG, "Element not found for action: " + actionName);
    return null;
  },

  /**
   * 按策略类型查找控件
   * @param {Object} strategy - { type, value, x_percent, y_percent }
   * @returns {UiObject|null}
   */
  _findByStrategy: function (strategy) {
    switch (strategy.type) {
      case "text":
        return text(strategy.value).findOnce();
      case "id":
        return id(strategy.value).findOnce();
      case "desc":
        return desc(strategy.value).findOnce();
      case "className":
        return className(strategy.value).findOnce();
      case "coordinate":
        // 坐标点击不返回控件对象，返回一个模拟对象
        var x = Math.round(strategy.x_percent * device.width);
        var y = Math.round(strategy.y_percent * device.height);
        return { isCoordinate: true, x: x, y: y };
      default:
        return null;
    }
  },

  /**
   * 点击元素（支持控件点击和坐标点击）
   * @param {UiObject} element
   * @returns {boolean}
   */
  clickElement: function (element) {
    if (!element) return false;

    if (element.isCoordinate) {
      logger.debug(TAG, "Clicking coordinate: (" + element.x + ", " + element.y + ")");
      return click(element.x, element.y);
    }

    if (element.clickable()) {
      return element.click();
    } else {
      // 控件不可点击，尝试点击其父元素或坐标
      var bounds = element.bounds();
      if (bounds) {
        return click(bounds.centerX(), bounds.centerY());
      }
    }
    return false;
  },

  /**
   * 输入文本
   * @param {UiObject} element - 输入框控件
   * @param {string} text - 要输入的文本
   * @returns {boolean}
   */
  inputText: function (element, text) {
    if (!element) return false;
    element.setText(text);
    return true;
  },

  /**
   * 执行上滑操作（浏览下一条视频）
   * @returns {boolean}
   */
  swipeUp: function () {
    var startX = device.width / 2 + Math.floor(Math.random() * 50 - 25);
    var startY = device.height * 0.7;
    var endX = device.width / 2 + Math.floor(Math.random() * 50 - 25);
    var endY = device.height * 0.3;
    return swipe(startX, startY, endX, endY, Math.floor(Math.random() * 200 + 300));
  },

  /**
   * 截取当前页面控件树快照（用于选择器调试）
   * @returns {Object} 控件树摘要
   */
  captureUISnapshot: function () {
    var snapshot = { elements: [] };
    try {
      var allElements = className("android.widget.TextView").find();
      for (var i = 0; i < Math.min(allElements.length, 50); i++) {
        var el = allElements[i];
        snapshot.elements.push({
          text: el.text() || "",
          id: el.id() || "",
          desc: el.desc() || "",
          className: el.className() || "",
          bounds: el.bounds() ? {
            left: el.bounds().left,
            top: el.bounds().top,
            right: el.bounds().right,
            bottom: el.bounds().bottom,
          } : null,
        });
      }
    } catch (e) {
      logger.warn(TAG, "Failed to capture UI snapshot: " + e.message);
    }
    return snapshot;
  },
};

module.exports = uiOperator;
```

- [ ] **Step 2: Commit**

```bash
git add device/core/ui-operator.js
git commit -m "feat: add UI operator with dynamic selector lookup and human-like gestures"
```

---

## Task 12: 反检测引擎

**Files:**
- Create: `device/core/anti-detect.js`

- [ ] **Step 1: 实现反检测引擎**

```javascript
// device/core/anti-detect.js
var config = require("../config");
var logger = require("../utils/logger");
var bezier = require("../utils/bezier");

var TAG = "ANTI_DETECT";
var settings = config.antiDetect;

var antiDetect = {
  /**
   * 操作前随机延迟
   * @param {string} actionName - 操作名称（用于日志）
   */
  randomDelay: function (actionName) {
    var delay = Math.floor(
      Math.random() * (settings.delayMax - settings.delayMin) + settings.delayMin
    );
    logger.debug(TAG, "Delay " + delay + "ms before " + (actionName || "action"));
    sleep(delay);
  },

  /**
   * 操作后随机延迟（比操作前稍短）
   */
  postActionDelay: function () {
    var delay = Math.floor(
      Math.random() * (settings.delayMax - settings.delayMin) * 0.5 + settings.delayMin * 0.5
    );
    sleep(delay);
  },

  /**
   * 随机停顿 — 模拟用户走神
   * @returns {boolean} 是否执行了停顿
   */
  maybePause: function () {
    if (Math.random() < settings.pauseProbability) {
      var pauseDuration = Math.floor(
        Math.random() * (settings.pauseMax - settings.pauseMin) + settings.pauseMin
      );
      logger.info(TAG, "Random pause for " + Math.round(pauseDuration / 1000) + "s (simulating user distraction)");
      sleep(pauseDuration);
      return true;
    }
    return false;
  },

  /**
   * 拟人滑动 — 使用贝塞尔曲线
   * @param {number} startX
   * @param {number} startY
   * @param {number} endX
   * @param {number} endY
   */
  humanSwipe: function (startX, startY, endX, endY) {
    var path = bezier.generateSwipePath(startX, startY, endX, endY);
    logger.debug(TAG, "Human swipe with " + path.length + " points");

    // 使用 gestures 模拟多点触控轨迹
    var gesturePoints = path.map(function (p) {
      return [p.x, p.y];
    });

    var totalDuration = path.reduce(function (sum, p) {
      return sum + p.duration;
    }, 0);

    // AutoJS6 gestures API: gestures(duration, [x, y], [x, y], ...)
    var args = [totalDuration];
    for (var i = 0; i < gesturePoints.length; i++) {
      args.push(gesturePoints[i]);
    }
    gestures.apply(null, args);
  },

  /**
   * 拟人上滑（浏览下一条视频）
   * 比普通 swipe 更自然
   */
  humanSwipeUp: function () {
    var startX = device.width / 2 + Math.floor(Math.random() * 60 - 30);
    var startY = device.height * (0.65 + Math.random() * 0.1);
    var endX = device.width / 2 + Math.floor(Math.random() * 60 - 30);
    var endY = device.height * (0.25 + Math.random() * 0.1);

    this.humanSwipe(startX, startY, endX, endY);
  },

  /**
   * 操作节奏波动 — 基于基础间隔添加随机偏移
   * @param {number} baseInterval - 基础间隔（毫秒）
   * @returns {number} 波动后的间隔
   */
  varyRhythm: function (baseInterval) {
    var variation = baseInterval * settings.rhythmVariation;
    var offset = (Math.random() - 0.5) * 2 * variation;
    return Math.max(500, Math.round(baseInterval + offset));
  },

  /**
   * 包装一个操作，自动添加反检测行为
   * @param {string} actionName
   * @param {Function} actionFn - 实际操作函数
   * @returns {*} 操作返回值
   */
  wrapAction: function (actionName, actionFn) {
    this.randomDelay(actionName);
    this.maybePause();

    var result = actionFn();

    this.postActionDelay();
    return result;
  },
};

module.exports = antiDetect;
```

- [ ] **Step 2: Commit**

```bash
git add device/core/anti-detect.js
git commit -m "feat: add anti-detection engine with random delays, human swipe, rhythm variation"
```

---

## Task 13: Handler 基类与养号 Handler

**Files:**
- Create: `device/handlers/base-handler.js`
- Create: `device/handlers/nurture.js`

- [ ] **Step 1: 实现 Handler 基类**

```javascript
// device/handlers/base-handler.js
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "HANDLER";

/**
 * Handler 基类 — 所有任务 handler 继承此对象
 */
var BaseHandler = {
  /**
   * 执行任务（子类必须实现）
   * @param {Object} params - 任务参数
   * @returns {Object} { success: boolean, result: Object, error?: string }
   */
  execute: function (params) {
    throw new Error("execute() not implemented");
  },

  /**
   * 确保抖音在前台，不在则启动
   * @returns {boolean}
   */
  ensureAppActive: function () {
    if (!uiOperator.isAppActive()) {
      return uiOperator.openApp();
    }
    return true;
  },

  /**
   * 安全地查找并点击元素（带重试）
   * @param {string} actionName
   * @param {number} retries
   * @returns {boolean}
   */
  safeClick: function (actionName, retries) {
    retries = retries || 3;
    for (var i = 0; i < retries; i++) {
      var element = uiOperator.findElement(actionName, 3000);
      if (element) {
        return antiDetect.wrapAction(actionName, function () {
          return uiOperator.clickElement(element);
        });
      }
      logger.warn(TAG, "Retry " + (i + 1) + "/" + retries + " for action: " + actionName);
      sleep(2000 * (i + 1)); // 递增等待
    }
    logger.error(TAG, "Failed to click after " + retries + " retries: " + actionName);
    return false;
  },

  /**
   * 安全地输入文本
   * @param {string} actionName - 输入框选择器
   * @param {string} text
   * @returns {boolean}
   */
  safeInput: function (actionName, text) {
    var element = uiOperator.findElement(actionName, 5000);
    if (element) {
      return antiDetect.wrapAction("input_text", function () {
        return uiOperator.inputText(element, text);
      });
    }
    return false;
  },
};

module.exports = BaseHandler;
```

- [ ] **Step 2: 实现养号 Handler**

```javascript
// device/handlers/nurture.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "NURTURE";

/**
 * 养号 Handler
 * params:
 *   - duration: number (养号时长，分钟)
 *   - actions: Array<{ type: string, weight: number }> (可选，自定义行为权重)
 */
var NurtureHandler = Object.create(BaseHandler);

NurtureHandler.execute = function (params) {
  var duration = params.duration || 30; // 默认 30 分钟
  var actions = params.actions || [
    { type: "browse_feed", weight: 70 },
    { type: "like", weight: 20 },
    { type: "follow", weight: 10 },
  ];

  logger.info(TAG, "Starting nurture for " + duration + " minutes");

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  var startTime = Date.now();
  var endTime = startTime + duration * 60 * 1000;
  var stats = { videos_watched: 0, likes: 0, follows: 0, errors: 0 };

  while (Date.now() < endTime) {
    // 随机选择行为
    var action = this._weightedRandom(actions);

    try {
      switch (action.type) {
        case "browse_feed":
          this._browseFeed(stats);
          break;
        case "like":
          this._likeCurrentVideo(stats);
          break;
        case "follow":
          this._followCurrentUser(stats);
          break;
        default:
          this._browseFeed(stats);
      }
    } catch (e) {
      logger.error(TAG, "Error during nurture action '" + action.type + "': " + e.message);
      stats.errors++;
    }

    // 随机上滑浏览下一条
    antiDetect.humanSwipeUp();
    stats.videos_watched++;

    logger.info(TAG, "Progress: watched=" + stats.videos_watched +
      " likes=" + stats.likes + " follows=" + stats.follows +
      " errors=" + stats.errors);
  }

  logger.info(TAG, "Nurture completed. Stats: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 浏览推荐页（不做额外操作，只是等待观看）
 */
NurtureHandler._browseFeed = function (stats) {
  // 模拟观看视频 5-15 秒
  var watchTime = Math.floor(Math.random() * 10000 + 5000);
  logger.debug(TAG, "Watching video for " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

/**
 * 对当前视频点赞
 */
NurtureHandler._likeCurrentVideo = function (stats) {
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    stats.likes++;
    logger.info(TAG, "Liked video (total: " + stats.likes + ")");
  }
};

/**
 * 关注当前视频的作者
 */
NurtureHandler._followCurrentUser = function (stats) {
  var clicked = this.safeClick("follow_button", 2);
  if (clicked) {
    stats.follows++;
    logger.info(TAG, "Followed user (total: " + stats.follows + ")");
  }
};

/**
 * 按权重随机选择行为
 */
NurtureHandler._weightedRandom = function (actions) {
  var totalWeight = actions.reduce(function (sum, a) { return sum + a.weight; }, 0);
  var random = Math.random() * totalWeight;
  var cumulative = 0;
  for (var i = 0; i < actions.length; i++) {
    cumulative += actions[i].weight;
    if (random < cumulative) return actions[i];
  }
  return actions[0];
};

module.exports = NurtureHandler;
```

- [ ] **Step 3: Commit**

```bash
git add device/handlers/
git commit -m "feat: add base handler and nurture handler (browse, like, follow)"
```

---

## Task 14: 任务执行器与主循环

**Files:**
- Create: `device/core/task-executor.js`
- Create: `device/main.js`

- [ ] **Step 1: 实现任务执行器**

```javascript
// device/core/task-executor.js
var apiClient = require("./api-client");
var selectorLoader = require("./selector-loader");
var logger = require("../utils/logger");

var TAG = "EXECUTOR";

// Handler 注册表
var handlers = {
  nurture: require("../handlers/nurture"),
};

var taskExecutor = {
  /**
   * 执行单个任务
   * @param {Object} task - 任务对象
   * @returns {Object} { status, result }
   */
  execute: function (task) {
    logger.info(TAG, "Executing task: " + task.id + " type=" + task.type);

    var handler = handlers[task.type];
    if (!handler) {
      logger.error(TAG, "No handler for task type: " + task.type);
      return { status: "failed", result: { error: "Unknown task type: " + task.type } };
    }

    try {
      var result = handler.execute(task.params);
      if (result.success) {
        logger.info(TAG, "Task " + task.id + " completed successfully");
        return { status: "completed", result: result.result };
      } else {
        logger.warn(TAG, "Task " + task.id + " failed: " + result.error);
        return { status: "failed", result: { error: result.error } };
      }
    } catch (e) {
      logger.error(TAG, "Task " + task.id + " threw exception: " + e.message);
      return { status: "failed", result: { error: e.message } };
    }
  },

  /**
   * 注册新的 handler
   * @param {string} type
   * @param {Object} handler
   */
  registerHandler: function (type, handler) {
    handlers[type] = handler;
  },
};

module.exports = taskExecutor;
```

- [ ] **Step 2: 实现主循环**

```javascript
// device/main.js
var config = require("./config");
var apiClient = require("./core/api-client");
var selectorLoader = require("./core/selector-loader");
var taskExecutor = require("./core/task-executor");
var logger = require("./utils/logger");

var TAG = "MAIN";

/**
 * 主循环
 */
function main() {
  logger.info(TAG, "=== 抖音自动化助手 MVP 启动 ===");
  logger.info(TAG, "Device ID: " + config.deviceId);
  logger.info(TAG, "Server: " + config.serverUrl);
  logger.info(TAG, "Poll interval: " + config.pollInterval + "ms");

  // 初始化选择器
  selectorLoader.init();

  // 启动心跳定时器
  var heartbeatTimer = setInterval(function () {
    try {
      apiClient.heartbeat();
    } catch (e) {
      logger.warn(TAG, "Heartbeat failed: " + e.message);
    }
  }, config.heartbeatInterval);

  // 主轮询循环
  logger.info(TAG, "Starting main poll loop...");

  while (true) {
    try {
      // 轮询任务
      var response = apiClient.poll();

      if (response) {
        // 检查选择器版本
        if (response.selectors_version) {
          selectorLoader.checkAndUpdate(response.selectors_version);
        }

        // 执行任务
        if (response.task) {
          logger.info(TAG, "Got task: " + response.task.id + " (" + response.task.type + ")");

          var result = taskExecutor.execute(response.task);

          // 上报结果
          var uiSnapshot = null;
          if (result.status === "failed") {
            // 失败时附带控件树快照，用于分析选择器问题
            try {
              var uiOperator = require("./core/ui-operator");
              uiSnapshot = uiOperator.captureUISnapshot();
            } catch (e) {
              logger.warn(TAG, "Failed to capture UI snapshot: " + e.message);
            }
          }

          apiClient.report(response.task.id, result.status, result.result, uiSnapshot);
          logger.info(TAG, "Task result reported: " + result.status);
        } else {
          logger.debug(TAG, "No pending tasks");
        }
      }
    } catch (e) {
      logger.error(TAG, "Main loop error: " + e.message);
    }

    // 等待下次轮询
    sleep(config.pollInterval);
  }
}

// 启动
main();
```

- [ ] **Step 3: 验证服务端启动并测试端到端流程**

```bash
# 终端 1: 启动服务端
cd server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2: 创建任务
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-Device-Secret: change-me-to-a-random-string" \
  -d '{"type": "nurture", "account_id": "acc-001", "params": {"duration": 5}}'

# 终端 3: 模拟设备轮询
curl "http://localhost:8000/api/device/poll?device_id=dev-test" \
  -H "X-Device-Secret: change-me-to-a-random-string"
```

Expected: 轮询返回任务数据，`status` 为 `"running"`

- [ ] **Step 4: Commit**

```bash
git add device/core/task-executor.js device/main.js
git commit -m "feat: add task executor and main poll loop"
```

---

## Task 15: 端到端集成验证

- [ ] **Step 1: 启动服务端**

```bash
cd server
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: 创建养号任务**

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-Device-Secret: change-me-to-a-random-string" \
  -d '{"type": "nurture", "account_id": "acc-001", "params": {"duration": 5}}'
```

Expected: 返回任务 JSON，`"status": "pending"`

- [ ] **Step 3: 确认任务列表**

```bash
curl http://localhost:8000/api/tasks \
  -H "X-Device-Secret: change-me-to-a-random-string"
```

Expected: `{"tasks": [...], "total": 1}`

- [ ] **Step 4: 将 device/ 目录推送到手机**

使用 ADB 或文件管理器将 `device/` 目录推送到手机的 AutoJS6 脚本目录。

```bash
# 通过 ADB 推送
adb push device/ /sdcard/Scripts/dy_auto/
```

- [ ] **Step 5: 在 AutoJS6 中运行 main.js**

在 AutoJS6 中打开 `main.js`，修改 `config.serverUrl` 为服务端实际 IP 地址，运行脚本。

预期行为：
1. 控制台输出设备 ID 和服务端地址
2. 加载选择器配置
3. 开始轮询
4. 领取养号任务
5. 打开抖音
6. 按权重随机执行：浏览视频、点赞、关注
7. 任务完成后上报结果

- [ ] **Step 6: 查看服务端日志确认结果**

```bash
curl http://localhost:8000/api/tasks \
  -H "X-Device-Secret: change-me-to-a-random-string"
```

Expected: 任务 `status` 为 `"completed"`，`result` 包含统计数据

- [ ] **Step 7: 最终 Commit**

```bash
git add .
git commit -m "chore: MVP complete — server + device integration verified"
```

---

## 任务依赖关系

```
Task 1 (项目初始化)
  └─> Task 2 (数据模型)
       └─> Task 3 (配置加载)
            ├─> Task 4 (任务调度服务)
            │    ├─> Task 6 (设备端 API)
            │    └─> Task 7 (任务管理 API)
            └─> Task 5 (选择器服务)
                 └─> Task 6 (设备端 API)

Task 8 (设备配置与工具)  [可与后端并行]
  └─> Task 9 (HTTP 客户端)
       ├─> Task 10 (选择器加载器)
       │    └─> Task 11 (UI 操作层)
       │         └─> Task 13 (Handler)
       └─> Task 12 (反检测引擎)
            └─> Task 13 (Handler)
                 └─> Task 14 (任务执行器与主循环)
                      └─> Task 15 (端到端验证)
```

---

## 后续计划（MVP 之后）

MVP 验证通过后，按以下顺序扩展：

1. **数据库层** — 替换内存存储为 SQLAlchemy + SQLite/PostgreSQL
2. **多设备支持** — 设备注册、认证、任务分配优化
3. **更多 Handler** — SearchHandler、CommentHandler、LikeHandler、DMHandler
4. **选择器管理页面** — Vue 前端，可视化编辑选择器
5. **AI 内容生成** — 对接 Claude/GPT API，模板 + AI 混合生成评论/私信
6. **Web 管理后台** — 完整的 Vue 仪表盘
7. **数据统计与优化** — 每日统计、性能调优
