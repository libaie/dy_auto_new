# 账号分组 + 任务链 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现账号分组管理、任务链编排、养号任务重构，以及关键词搜索快捷入口

**Architecture:** 新增 4 张表（account_groups, account_group_members, chain_templates, chain_instances），2 个新路由模块（account_groups, chains），1 个新服务（chain_service），3 个新前端页面。与现有任务系统通过 Task 表的 chain_instance_id 字段关联，利用现有 WS 推送管线实现链步骤状态同步。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite (auto-migration), Vue 3, Pinia, HeadlessUI, AutoJS6

**Spec:** `docs/superpowers/specs/2026-04-30-account-groups-task-chains-design.md`

---

## 文件结构

### 后端新增
- `server/app/routers/account_groups.py` — 账号分组 CRUD API
- `server/app/routers/chains.py` — 链模板 + 链实例 API
- `server/app/services/chain_service.py` — 链编排引擎

### 后端修改
- `server/app/db_models.py` — 新增 4 个 ORM 模型 + Task 表新增 2 字段
- `server/app/models.py` — 新增 Pydantic 模型
- `server/app/services/task_service.py` — 互斥检查 + 链推进集成
- `server/app/routers/tasks.py` — 养号参数校验支持 V2
- `server/app/main.py` — 注册新路由

### 设备端修改
- `device/handlers/nurture.js` — 重构为 sub_tasks 模式

### 前端新增
- `web/src/views/AccountGroupsPage.vue` — 账号分组管理页面
- `web/src/views/ChainTemplatesPage.vue` — 链模板编辑器
- `web/src/views/ChainInstancesPage.vue` — 链实例管理页面
- `web/src/api/accountGroups.js` — 账号分组 API 模块
- `web/src/api/chains.js` — 链 API 模块

### 前端修改
- `web/src/router/index.js` — 新增 3 条路由
- `web/src/views/AdminLayout.vue` — 导航栏新增 3 个入口
- `web/src/views/TasksPage.vue` — 养号参数表单 + 关键词搜索快捷入口

---

## Task 1: 数据模型 — 账号分组表

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/app/models.py`

- [ ] **Step 1: 在 db_models.py 中新增 AccountGroup 和 AccountGroupMember 模型**

在 `SensitiveWord` 类之后添加：

```python
class AccountGroup(Base):
    __tablename__ = "account_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    members = relationship("AccountGroupMember", back_populates="group", cascade="all, delete-orphan")


class AccountGroupMember(Base):
    __tablename__ = "account_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "account_id", name="uq_group_account"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    group = relationship("AccountGroup", back_populates="members")
    account = relationship("Account")
```

- [ ] **Step 2: 在 models.py 中新增 Pydantic 模型**

在 `SensitiveWordResponse` 类之后添加：

```python
class AccountGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class AccountGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class AccountGroupResponse(BaseModel):
    id: str
    name: str
    description: str
    member_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountGroupMemberRequest(BaseModel):
    account_ids: list[str] = Field(..., min_length=1)
```

- [ ] **Step 3: 验证自动迁移**

启动服务端，检查 `_migrate_add_columns()` 是否自动创建了新表。SQLite 的 `create_all()` 会创建不存在的表，所以新表会自动创建。

```bash
cd server && python -c "from app.database import init_db; init_db()"
```

Expected: 无报错，`account_groups` 和 `account_group_members` 表已创建。

- [ ] **Step 4: Commit**

```bash
git add server/app/db_models.py server/app/models.py
git commit -m "feat: add AccountGroup and AccountGroupMember data models"
```

---

## Task 2: 账号分组 API

**Files:**
- Create: `server/app/routers/account_groups.py`
- Modify: `server/app/main.py`

- [ ] **Step 1: 创建 account_groups.py 路由**

```python
"""Account groups CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.db_models import AccountGroup, AccountGroupMember, Account
from app.deps import verify_admin_token
from app.models import AccountGroupCreate, AccountGroupUpdate, AccountGroupMemberRequest

router = APIRouter(prefix="/api/account-groups", tags=["account-groups"])


def _group_to_dict(group: AccountGroup, member_count: int = 0) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description or "",
        "member_count": member_count,
        "created_at": str(group.created_at) if group.created_at else None,
        "updated_at": str(group.updated_at) if group.updated_at else None,
    }


@router.post("")
def create_group(
    request: AccountGroupCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    existing = db.query(AccountGroup).filter(AccountGroup.name == request.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="分组名称已存在")
    group = AccountGroup(name=request.name, description=request.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_to_dict(group, 0)


@router.get("")
def list_groups(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    # Subquery for member counts
    member_counts = (
        db.query(
            AccountGroupMember.group_id,
            func.count(AccountGroupMember.id).label("cnt"),
        )
        .group_by(AccountGroupMember.group_id)
        .subquery()
    )
    query = (
        db.query(AccountGroup, func.coalesce(member_counts.c.cnt, 0).label("member_count"))
        .outerjoin(member_counts, AccountGroup.id == member_counts.c.group_id)
        .order_by(AccountGroup.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = query.all()
    total = db.query(AccountGroup).count()
    return {
        "groups": [_group_to_dict(g, mc) for g, mc in results],
        "total": total,
    }


@router.get("/{group_id}")
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    return _group_to_dict(group, member_count)


@router.put("/{group_id}")
def update_group(
    group_id: str,
    request: AccountGroupUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if request.name is not None:
        dup = db.query(AccountGroup).filter(AccountGroup.name == request.name, AccountGroup.id != group_id).first()
        if dup:
            raise HTTPException(status_code=409, detail="分组名称已存在")
        group.name = request.name
    if request.description is not None:
        group.description = request.description
    db.commit()
    db.refresh(group)
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    return _group_to_dict(group, member_count)


@router.delete("/{group_id}")
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    db.delete(group)
    db.commit()
    return {"deleted": True, "id": group_id}


@router.get("/{group_id}/members")
def list_members(
    group_id: str,
    status: str = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    query = (
        db.query(Account)
        .join(AccountGroupMember, AccountGroupMember.account_id == Account.id)
        .filter(AccountGroupMember.group_id == group_id)
    )
    if status:
        query = query.filter(Account.status == status)
    accounts = query.order_by(Account.created_at.desc()).all()
    return {
        "members": [
            {
                "id": a.id,
                "nickname": a.nickname,
                "douyin_id": a.douyin_id,
                "status": a.status,
            }
            for a in accounts
        ],
        "total": len(accounts),
    }


@router.post("/{group_id}/members")
def add_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    added = []
    for account_id in request.account_ids:
        exists = db.query(AccountGroupMember).filter(
            AccountGroupMember.group_id == group_id,
            AccountGroupMember.account_id == account_id,
        ).first()
        if not exists:
            db.add(AccountGroupMember(group_id=group_id, account_id=account_id))
            added.append(account_id)
    db.commit()
    return {"added": added, "count": len(added)}


@router.delete("/{group_id}/members")
def remove_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    count = (
        db.query(AccountGroupMember)
        .filter(
            AccountGroupMember.group_id == group_id,
            AccountGroupMember.account_id.in_(request.account_ids),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"removed": count}
```

- [ ] **Step 2: 在 main.py 注册新路由**

在 `app.include_router(content_router.router)` 之后添加：

```python
from app.routers import account_groups
app.include_router(account_groups.router)
```

- [ ] **Step 3: 启动服务验证**

```bash
cd server && python -m uvicorn app.main:app --reload --port 8000
```

用 curl 或浏览器测试：
- `POST /api/account-groups` 创建分组
- `GET /api/account-groups` 列出分组
- `POST /api/account-groups/{id}/members` 添加成员
- `GET /api/account-groups/{id}/members` 列出成员

- [ ] **Step 4: Commit**

```bash
git add server/app/routers/account_groups.py server/app/main.py
git commit -m "feat: add account groups CRUD API"
```

---

## Task 3: 数据模型 — 任务链

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/app/models.py`

- [ ] **Step 1: 在 db_models.py 中新增 ChainTemplate 和 ChainInstance 模型**

在 `AccountGroupMember` 类之后添加：

```python
class ChainTemplate(Base):
    __tablename__ = "chain_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True, default="")
    steps = Column(JSON, nullable=False)  # [{step_order, type, label, params}, ...]
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    instances = relationship("ChainInstance", back_populates="template")


class ChainInstance(Base):
    __tablename__ = "chain_instances"

    id = Column(String(36), primary_key=True, default=_uuid)
    template_id = Column(String(36), ForeignKey("chain_templates.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    current_step = Column(Integer, nullable=False, default=1)
    total_steps = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    template = relationship("ChainTemplate", back_populates="instances")
    account = relationship("Account")
    tasks = relationship("Task", back_populates="chain_instance")
```

- [ ] **Step 2: 在 Task 模型上新增 chain_instance_id 和 step_order 字段**

在 `Task` 类中 `created_at` 字段之后添加：

```python
chain_instance_id = Column(String(36), ForeignKey("chain_instances.id"), nullable=True)
step_order = Column(Integer, nullable=True)
```

在 `Task` 类的 relationship 区域添加：

```python
chain_instance = relationship("ChainInstance", back_populates="tasks")
```

- [ ] **Step 3: 在 models.py 中新增链相关 Pydantic 模型**

在 `AccountGroupMemberRequest` 类之后添加：

```python
class ChainStep(BaseModel):
    step_order: int = Field(..., ge=1)
    type: str = Field(..., min_length=1)
    label: str = Field(default="", max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class ChainTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    steps: list[ChainStep] = Field(..., min_length=1)


class ChainTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    steps: Optional[list[ChainStep]] = None


class ChainTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    steps: list[dict[str, Any]]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChainInstanceCreateRequest(BaseModel):
    template_id: str
    account_ids: Optional[list[str]] = None
    group_ids: Optional[list[str]] = None


class ChainInstanceResponse(BaseModel):
    id: str
    template_id: str
    template_name: str = ""
    account_id: str
    account_nickname: str = ""
    current_step: int
    total_steps: int
    status: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

同步更新 Pydantic `Task` 模型，新增：

```python
chain_instance_id: Optional[str] = None
step_order: Optional[int] = None
```

- [ ] **Step 4: 验证自动迁移**

```bash
cd server && python -c "from app.database import init_db; init_db()"
```

Expected: `chain_templates` 和 `chain_instances` 表已创建，`tasks` 表新增 `chain_instance_id` 和 `step_order` 列。

- [ ] **Step 5: Commit**

```bash
git add server/app/db_models.py server/app/models.py
git commit -m "feat: add ChainTemplate and ChainInstance data models"
```

---

## Task 4: 链模板 API

**Files:**
- Create: `server/app/routers/chains.py`
- Modify: `server/app/main.py`

- [ ] **Step 1: 创建 chains.py 路由（模板部分）**

```python
"""Chain templates and instances API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.db_models import ChainTemplate, ChainInstance, Task as DBTask, Account, Device, AccountGroupMember
from app.deps import verify_admin_token
from app.models import ChainTemplateCreate, ChainTemplateUpdate, ChainInstanceCreateRequest

router = APIRouter(prefix="/api/chains", tags=["chains"])


def _template_to_dict(t: ChainTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description or "",
        "steps": t.steps or [],
        "created_at": str(t.created_at) if t.created_at else None,
        "updated_at": str(t.updated_at) if t.updated_at else None,
    }


def _instance_to_dict(inst: ChainInstance, template_name: str = "", account_nickname: str = "") -> dict:
    return {
        "id": inst.id,
        "template_id": inst.template_id,
        "template_name": template_name,
        "account_id": inst.account_id,
        "account_nickname": account_nickname,
        "current_step": inst.current_step,
        "total_steps": inst.total_steps,
        "status": inst.status,
        "created_at": str(inst.created_at) if inst.created_at else None,
        "started_at": str(inst.started_at) if inst.started_at else None,
        "completed_at": str(inst.completed_at) if inst.completed_at else None,
    }


# --- Chain Template CRUD ---

@router.post("/templates")
def create_template(
    request: ChainTemplateCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    # Validate step_order continuity
    orders = sorted(s.step_order for s in request.steps)
    if orders != list(range(1, len(request.steps) + 1)):
        raise HTTPException(status_code=422, detail="步骤序号必须从 1 连续递增")

    steps_data = [s.model_dump() for s in request.steps]
    tpl = ChainTemplate(name=request.name, description=request.description, steps=steps_data)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return _template_to_dict(tpl)


@router.get("/templates")
def list_templates(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    total = db.query(ChainTemplate).count()
    templates = db.query(ChainTemplate).order_by(ChainTemplate.created_at.desc()).offset(skip).limit(limit).all()
    return {"templates": [_template_to_dict(t) for t in templates], "total": total}


@router.get("/templates/{template_id}")
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    tpl = db.query(ChainTemplate).filter(ChainTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _template_to_dict(tpl)


@router.put("/templates/{template_id}")
def update_template(
    template_id: str,
    request: ChainTemplateUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    tpl = db.query(ChainTemplate).filter(ChainTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if request.name is not None:
        tpl.name = request.name
    if request.description is not None:
        tpl.description = request.description
    if request.steps is not None:
        orders = sorted(s.step_order for s in request.steps)
        if orders != list(range(1, len(request.steps) + 1)):
            raise HTTPException(status_code=422, detail="步骤序号必须从 1 连续递增")
        tpl.steps = [s.model_dump() for s in request.steps]
    db.commit()
    db.refresh(tpl)
    return _template_to_dict(tpl)


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    tpl = db.query(ChainTemplate).filter(ChainTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    # Check for active instances
    active = db.query(ChainInstance).filter(
        ChainInstance.template_id == template_id,
        ChainInstance.status.in_(["pending", "running"]),
    ).count()
    if active > 0:
        raise HTTPException(status_code=400, detail=f"该模板有 {active} 个活跃实例，无法删除")
    db.delete(tpl)
    db.commit()
    return {"deleted": True, "id": template_id}
```

- [ ] **Step 2: 在 main.py 注册新路由**

```python
from app.routers import chains
app.include_router(chains.router)
```

- [ ] **Step 3: 测试模板 CRUD**

```bash
# 创建模板
curl -X POST http://localhost:8000/api/chains/templates \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试链","steps":[{"step_order":1,"type":"nurture","label":"养号","params":{"duration":30}}]}'

# 列出模板
curl http://localhost:8000/api/chains/templates -H "Authorization: Bearer <token>"
```

- [ ] **Step 4: Commit**

```bash
git add server/app/routers/chains.py server/app/main.py
git commit -m "feat: add chain template CRUD API"
```

---

## Task 5: 互斥锁 + 链实例创建

**Files:**
- Create: `server/app/services/chain_service.py`
- Modify: `server/app/services/task_service.py`
- Modify: `server/app/routers/chains.py`

- [ ] **Step 1: 创建 chain_service.py**

```python
"""Chain orchestration service — step-by-step task release."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import (
    ChainTemplate, ChainInstance, Task as DBTask, Device, Account,
    AccountGroupMember,
)


class ChainService:
    def is_account_busy(self, db: Session, account_id: str) -> bool:
        """Check if account has pending or running tasks."""
        count = db.query(DBTask).filter(
            DBTask.account_id == account_id,
            DBTask.status.in_(["pending", "running"]),
        ).count()
        return count > 0

    def create_chain_instances(
        self,
        db: Session,
        template_id: str,
        account_ids: list[str],
    ) -> dict:
        """Create chain instances for each account, skipping busy ones."""
        template = db.query(ChainTemplate).filter(ChainTemplate.id == template_id).first()
        if not template:
            raise ValueError("模板不存在")

        total_steps = len(template.steps)
        results = {"created": [], "skipped_busy": [], "skipped_error": []}

        for account_id in account_ids:
            # Verify account exists
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                results["skipped_error"].append(account_id)
                continue

            # Mutual exclusion check
            if self.is_account_busy(db, account_id):
                results["skipped_busy"].append(account_id)
                continue

            # Create chain instance
            instance = ChainInstance(
                template_id=template_id,
                account_id=account_id,
                current_step=1,
                total_steps=total_steps,
                status="pending",
            )
            db.add(instance)
            db.flush()

            # Create first step task
            self._create_step_task(db, instance, 1, template)

            results["created"].append(account_id)

        db.commit()

        # Push first step tasks to devices
        self._push_pending_tasks(db, results["created"])

        return results

    def resolve_accounts_from_groups(self, db: Session, group_ids: list[str]) -> list[str]:
        """Expand group IDs to unique active account IDs."""
        account_ids = (
            db.query(AccountGroupMember.account_id)
            .join(Account, Account.id == AccountGroupMember.account_id)
            .filter(
                AccountGroupMember.group_id.in_(group_ids),
                Account.status == "active",
            )
            .distinct()
            .all()
        )
        return [a[0] for a in account_ids]

    def advance_chain(self, db: Session, task_id: str, status: str, result: dict = None):
        """Advance chain to next step after task completion/failure."""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task or not task.chain_instance_id:
            return

        chain = db.query(ChainInstance).filter(
            ChainInstance.id == task.chain_instance_id
        ).first()
        if not chain:
            return

        if status == "completed":
            next_step = task.step_order + 1
            if next_step > chain.total_steps:
                chain.status = "completed"
                chain.completed_at = datetime.now(timezone.utc)
            else:
                chain.current_step = next_step
                chain.status = "running"
                template = db.query(ChainTemplate).filter(ChainTemplate.id == chain.template_id).first()
                if template:
                    self._create_step_task(db, chain, next_step, template)
                    db.flush()
                    self._push_step_task(db, chain)
        elif status == "failed":
            chain.status = "failed"
            chain.completed_at = datetime.now(timezone.utc)

        db.commit()

    def _create_step_task(self, db: Session, chain: ChainInstance, step_order: int, template: ChainTemplate):
        """Create a Task for the given step. Caller is responsible for commit/flush."""
        step = next((s for s in template.steps if s["step_order"] == step_order), None)
        if not step:
            raise ValueError(f"Step {step_order} not found in template")

        task = DBTask(
            type=step["type"],
            account_id=chain.account_id,
            params=step.get("params", {}),
            status="pending",
            chain_instance_id=chain.id,
            step_order=step_order,
        )
        db.add(task)

    def _push_pending_tasks(self, db: Session, account_ids: list[str]):
        """Push pending tasks for chain instances to bound devices."""
        from app.ws_manager import pair_ws_manager
        import asyncio

        for account_id in account_ids:
            device = db.query(Device).filter(Device.bound_account_id == account_id).first()
            if not device:
                continue
            task = (
                db.query(DBTask)
                .filter(DBTask.account_id == account_id, DBTask.status == "pending", DBTask.chain_instance_id.isnot(None))
                .order_by(DBTask.created_at.desc())
                .first()
            )
            if task:
                asyncio.ensure_future(pair_ws_manager.send_to_device(device.id, {
                    "event": "task",
                    "task": _task_to_push_dict(task),
                }))

    def _push_step_task(self, db: Session, chain: ChainInstance):
        """Push the current step task to the bound device."""
        from app.ws_manager import pair_ws_manager
        import asyncio

        device = db.query(Device).filter(Device.bound_account_id == chain.account_id).first()
        if not device:
            return
        task = (
            db.query(DBTask)
            .filter(DBTask.chain_instance_id == chain.id, DBTask.status == "pending")
            .order_by(DBTask.step_order.desc())
            .first()
        )
        if task:
            asyncio.ensure_future(pair_ws_manager.send_to_device(device.id, {
                "event": "task",
                "task": _task_to_push_dict(task),
            }))


def _task_to_push_dict(task: DBTask) -> dict:
    return {
        "id": task.id,
        "type": task.type,
        "account_id": task.account_id,
        "device_id": task.device_id or "",
        "params": task.params or {},
        "status": task.status,
        "chain_instance_id": task.chain_instance_id,
        "step_order": task.step_order,
    }


# Module-level singleton
chain_service = ChainService()
```

- [ ] **Step 2: 在 task_service.py 的 report_result 中集成链推进**

在 `report_result` 方法的 `db.commit()` 之前，添加：

```python
# Advance chain if this task is part of one
if db_task.chain_instance_id:
    from app.services.chain_service import chain_service
    chain_service.advance_chain(db, task_id, db_task.status, result)
```

注意：`advance_chain` 内部会 `db.commit()`，所以要把原来的 `db.commit()` 改为在链推进之后调用，或者让 `advance_chain` 使用 `flush` 而非 `commit`。

更安全的做法是把 `task_service.report_result` 中的 `db.commit()` 移到链推进之后：

```python
# 在 report_result 方法中，替换最后的 db.commit() 和 db.refresh(db_task)：
# Advance chain if this task is part of one
if db_task.chain_instance_id and db_task.status in ("completed", "failed"):
    from app.services.chain_service import chain_service
    chain_service.advance_chain(db, task_id, db_task.status, result)

db.commit()
db.refresh(db_task)
```

同时修改 `chain_service.advance_chain` 中的 `db.commit()` 为 `db.flush()`，由 `report_result` 统一 commit。

- [ ] **Step 3: 在 chains.py 中添加链实例创建端点**

在 `delete_template` 函数之后添加：

```python
# --- Chain Instance Management ---

@router.post("/instances")
async def create_instances(
    request: ChainInstanceCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    from app.services.chain_service import chain_service

    # Resolve account IDs
    account_ids = list(request.account_ids or [])
    if request.group_ids:
        group_accounts = chain_service.resolve_accounts_from_groups(db, request.group_ids)
        account_ids = list(set(account_ids + group_accounts))

    if not account_ids:
        raise HTTPException(status_code=422, detail="未指定任何账号")

    results = chain_service.create_chain_instances(db, request.template_id, account_ids)

    return {
        "created_count": len(results["created"]),
        "skipped_busy_count": len(results["skipped_busy"]),
        "skipped_error_count": len(results["skipped_error"]),
        "created": results["created"],
        "skipped_busy": results["skipped_busy"],
        "skipped_error": results["skipped_error"],
    }


@router.get("/instances")
def list_instances(
    template_id: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(ChainInstance)
    if template_id:
        query = query.filter(ChainInstance.template_id == template_id)
    if account_id:
        query = query.filter(ChainInstance.account_id == account_id)
    if status:
        query = query.filter(ChainInstance.status == status)
    total = query.count()
    instances = query.order_by(ChainInstance.created_at.desc()).offset(skip).limit(limit).all()

    # Batch load template names and account nicknames
    template_ids = list(set(i.template_id for i in instances))
    account_ids = list(set(i.account_id for i in instances))
    templates = {t.id: t.name for t in db.query(ChainTemplate).filter(ChainTemplate.id.in_(template_ids)).all()}
    accounts = {a.id: a.nickname for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}

    return {
        "instances": [
            _instance_to_dict(i, templates.get(i.template_id, ""), accounts.get(i.account_id, ""))
            for i in instances
        ],
        "total": total,
    }


@router.get("/instances/{instance_id}")
def get_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    inst = db.query(ChainInstance).filter(ChainInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    template = db.query(ChainTemplate).filter(ChainTemplate.id == inst.template_id).first()
    account = db.query(Account).filter(Account.id == inst.account_id).first()

    # Get all tasks for this chain instance
    tasks = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id)
        .order_by(DBTask.step_order)
        .all()
    )

    result = _instance_to_dict(inst, template.name if template else "", account.nickname if account else "")
    result["tasks"] = [
        {
            "id": t.id,
            "step_order": t.step_order,
            "type": t.type,
            "status": t.status,
            "params": t.params,
            "result": t.result,
            "started_at": str(t.started_at) if t.started_at else None,
            "completed_at": str(t.completed_at) if t.completed_at else None,
        }
        for t in tasks
    ]
    return result


@router.post("/instances/{instance_id}/cancel")
async def cancel_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    inst = db.query(ChainInstance).filter(ChainInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    if inst.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"链实例已处于 {inst.status} 状态")

    # Cancel current running/pending task
    current_task = (
        db.query(DBTask)
        .filter(
            DBTask.chain_instance_id == instance_id,
            DBTask.status.in_(["pending", "running"]),
        )
        .first()
    )
    if current_task:
        current_task.status = "cancelled"
        current_task.completed_at = datetime.now(timezone.utc)

        # Push cancel to device if running
        if current_task.device_id:
            from app.ws_manager import pair_ws_manager
            await pair_ws_manager.send_to_device(current_task.device_id, {
                "event": "cancel_task",
                "task_id": current_task.id,
            })

    inst.status = "cancelled"
    inst.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "cancelled", "id": instance_id}


@router.post("/instances/{instance_id}/retry")
async def retry_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    from app.services.chain_service import chain_service

    inst = db.query(ChainInstance).filter(ChainInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    if inst.status != "failed":
        raise HTTPException(status_code=400, detail="只能重试失败的链实例")

    # Check account is not busy with other tasks
    if chain_service.is_account_busy(db, inst.account_id):
        raise HTTPException(status_code=400, detail="该账号当前有其他任务在执行")

    # Retry from the failed step
    failed_task = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id, DBTask.status == "failed")
        .order_by(DBTask.step_order)
        .first()
    )
    if not failed_task:
        raise HTTPException(status_code=400, detail="未找到失败的步骤")

    # Reset failed task to pending
    failed_task.status = "pending"
    failed_task.device_id = None
    failed_task.started_at = None
    failed_task.completed_at = None
    failed_task.result = None

    inst.status = "running"
    inst.current_step = failed_task.step_order
    inst.completed_at = None
    db.commit()

    # Push to device
    chain_service._push_step_task(db, inst)

    return {"status": "retrying", "id": instance_id, "step": failed_task.step_order}
```

- [ ] **Step 4: 在 task_service.py 中添加互斥检查**

在 `create_task` 方法开头，添加互斥检查（可选，对独立任务也生效）：

```python
# Optional: enforce mutual exclusion for all tasks
# Uncomment to make all tasks mutually exclusive per account
# if self.is_account_busy(db, account_id):
#     raise ValueError(f"Account {account_id} has pending/running tasks")
```

注意：这里先注释掉，因为独立任务目前不需要互斥。互斥锁主要在 `chain_service.create_chain_instances` 中生效。

- [ ] **Step 5: 测试完整流程**

```bash
# 1. 创建模板
curl -X POST http://localhost:8000/api/chains/templates \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试链","steps":[{"step_order":1,"type":"nurture","label":"养号","params":{"duration":1}}]}'

# 2. 创建链实例
curl -X POST http://localhost:8000/api/chains/instances \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"template_id":"<template_id>","account_ids":["<account_id>"]}'

# 3. 查看实例
curl http://localhost:8000/api/chains/instances -H "Authorization: Bearer <token>"
```

- [ ] **Step 6: Commit**

```bash
git add server/app/services/chain_service.py server/app/services/task_service.py server/app/routers/chains.py
git commit -m "feat: add chain orchestration engine with mutual exclusion lock"
```

---

## Task 6: 养号任务重构

**Files:**
- Modify: `server/app/models.py`
- Modify: `server/app/routers/tasks.py`
- Modify: `device/handlers/nurture.js`

- [ ] **Step 1: 在 models.py 中新增 NurtureParamsV2**

在 `NurtureParams` 类之后添加：

```python
class NurtureSubTask(BaseModel):
    type: str = Field(..., pattern="^(browse|watch|like|comment|follow)$")
    count: int = Field(default=1, ge=1, le=100)
    content_template_id: Optional[str] = None


class NurtureParamsV2(BaseModel):
    sub_tasks: list[NurtureSubTask] = Field(..., min_length=1)
    completion_mode: str = Field(default="all", pattern="^(all|any)$")
    duration: int = Field(default=60, ge=1, le=240, description="最大时长(分钟)")
```

- [ ] **Step 2: 更新 TASK_PARAMS_VALIDATORS**

将 `TASK_PARAMS_VALIDATORS` 中的 `nurture` 条目改为支持两种格式：

```python
def _validate_nurture_params(params: dict) -> dict:
    """Accept both legacy (duration only) and V2 (sub_tasks) formats."""
    if "sub_tasks" in params:
        validated = NurtureParamsV2(**params)
        return validated.model_dump(exclude_none=True)
    else:
        validated = NurtureParams(**params)
        return validated.model_dump(exclude_none=True)

TASK_PARAMS_VALIDATORS = {
    "nurture": _validate_nurture_params,
    "search_comment": SearchCommentParams,
    "search_like": SearchLikeParams,
    "search_dm": SearchDMParams,
    "reply_comment": ReplyCommentParams,
}
```

注意：`TASK_PARAMS_VALIDATORS` 的值类型从 `Type[BaseModel]` 变为 `callable`。需要更新 `tasks.py` 中的校验逻辑：

```python
# 在 create_task 中，将：
validator = TASK_PARAMS_VALIDATORS.get(request.type.value)
if validator:
    try:
        validated = validator(**request.params)
        params = validated.model_dump(exclude_none=True)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"参数校验失败: {e}")

# 改为：
validator = TASK_PARAMS_VALIDATORS.get(request.type.value)
if validator:
    try:
        if isinstance(validator, type) and issubclass(validator, BaseModel):
            # Pydantic model validator
            validated = validator(**request.params)
            params = validated.model_dump(exclude_none=True)
        else:
            # Function validator (e.g., nurture)
            params = validator(request.params)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"参数校验失败: {e}")
```

- [ ] **Step 3: 重构 device/handlers/nurture.js**

```javascript
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "养号";

var NurtureHandler = Object.create(BaseHandler);

NurtureHandler.execute = function (params) {
  // V2 format: sub_tasks + completion_mode
  if (params.sub_tasks) {
    return this._executeV2(params);
  }
  // Legacy format: duration + actions
  return this._legacyExecute(params);
};

NurtureHandler._executeV2 = function (params) {
  var subTasks = params.sub_tasks;
  var completionMode = params.completion_mode || "all";
  var maxDuration = (params.duration || 60) * 60 * 1000;
  var startTime = Date.now();

  logger.info(TAG, "开始养号 V2, 子任务数=" + subTasks.length + ", 模式=" + completionMode);

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  // Initialize progress for each sub-task
  var progress = subTasks.map(function (st) {
    return {
      type: st.type,
      target: st.count,
      done: 0,
      contentTemplateId: st.content_template_id || null,
    };
  });

  while (Date.now() - startTime < maxDuration) {
    // Find incomplete sub-tasks
    var pending = progress.filter(function (p) { return p.done < p.target; });
    if (pending.length === 0) {
      logger.info(TAG, "所有子任务已完成");
      break;
    }

    // Randomly pick one incomplete sub-task
    var task = pending[Math.floor(Math.random() * pending.length)];
    try {
      this._executeSubTask(task);
      task.done++;
    } catch (e) {
      logger.error(TAG, "子任务 '" + task.type + "' 出错: " + e.message);
    }

    // Check completion condition
    if (completionMode === "any") {
      var anyDone = progress.some(function (p) { return p.done >= p.target; });
      if (anyDone) {
        logger.info(TAG, "任一子任务完成，结束养号");
        break;
      }
    }

    antiDetect.humanSwipeUp();
  }

  // Build stats
  var stats = {};
  progress.forEach(function (p) {
    stats[p.type] = { target: p.target, done: p.done };
  });

  logger.info(TAG, "养号 V2 完成: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

NurtureHandler._executeSubTask = function (task) {
  switch (task.type) {
    case "browse":
      this._browseFeed();
      break;
    case "watch":
      this._watchVideo();
      break;
    case "like":
      this._likeCurrentVideo();
      break;
    case "comment":
      this._commentOnVideo(task.contentTemplateId);
      break;
    case "follow":
      this._followCurrentUser();
      break;
    default:
      this._browseFeed();
  }
};

NurtureHandler._browseFeed = function () {
  var watchTime = Math.floor(Math.random() * 10000 + 5000);
  logger.debug(TAG, "浏览推荐页 " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

NurtureHandler._watchVideo = function () {
  var watchTime = Math.floor(Math.random() * 20000 + 10000);
  logger.debug(TAG, "观看视频 " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

NurtureHandler._likeCurrentVideo = function () {
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "点赞成功");
  }
};

NurtureHandler._commentOnVideo = function (templateId) {
  // Open comment box, type content, submit
  var opened = this.safeClick("comment_input", 3);
  if (!opened) return;
  sleep(500);
  // Content would come from template or be pre-generated
  var content = "好视频！"; // Placeholder — actual content from params
  uiOperator.typeText(content);
  sleep(300);
  this.safeClick("comment_submit", 2);
  logger.info(TAG, "评论成功");
};

NurtureHandler._followCurrentUser = function () {
  var clicked = this.safeClick("follow_button", 2);
  if (clicked) {
    logger.info(TAG, "关注成功");
  }
};

// --- Legacy support ---
NurtureHandler._legacyExecute = function (params) {
  var duration = params.duration || 30;
  var actions = params.actions || [
    { type: "browse_feed", weight: 70 },
    { type: "like", weight: 20 },
    { type: "follow", weight: 10 },
  ];

  logger.info(TAG, "开始养号(旧版) " + duration + " 分钟");

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  var startTime = Date.now();
  var endTime = startTime + duration * 60 * 1000;
  var stats = { videos_watched: 0, likes: 0, follows: 0, errors: 0 };

  while (Date.now() < endTime) {
    var action = this._weightedRandom(actions);
    try {
      switch (action.type) {
        case "browse_feed":
          this._browseFeed();
          break;
        case "like":
          this._likeCurrentVideo();
          break;
        case "follow":
          this._followCurrentUser();
          break;
        default:
          this._browseFeed();
      }
    } catch (e) {
      logger.error(TAG, "养号操作 '" + action.type + "' 出错: " + e.message);
      stats.errors++;
    }
    antiDetect.humanSwipeUp();
    stats.videos_watched++;
  }

  logger.info(TAG, "养号完成. 统计: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

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

- [ ] **Step 4: 测试**

用两种参数格式创建养号任务，验证服务端校验通过：
- 旧版：`{ "duration": 30 }`
- 新版：`{ "sub_tasks": [{"type":"browse","count":5},{"type":"like","count":3}], "completion_mode": "all", "duration": 30 }`

- [ ] **Step 5: Commit**

```bash
git add server/app/models.py server/app/routers/tasks.py device/handlers/nurture.js
git commit -m "feat: refactor nurture task to support sub_tasks + completion_mode"
```

---

## Task 7: 前端 — 账号分组页面

**Files:**
- Create: `web/src/api/accountGroups.js`
- Create: `web/src/views/AccountGroupsPage.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/views/AdminLayout.vue`

- [ ] **Step 1: 创建 API 模块 web/src/api/accountGroups.js**

```javascript
import client from './client.js'

export function listGroups(params = {}) {
  return client.get('/api/account-groups', { params })
}

export function getGroup(id) {
  return client.get(`/api/account-groups/${id}`)
}

export function createGroup(data) {
  return client.post('/api/account-groups', data)
}

export function updateGroup(id, data) {
  return client.put(`/api/account-groups/${id}`, data)
}

export function deleteGroup(id) {
  return client.delete(`/api/account-groups/${id}`)
}

export function listMembers(groupId, params = {}) {
  return client.get(`/api/account-groups/${groupId}/members`, { params })
}

export function addMembers(groupId, accountIds) {
  return client.post(`/api/account-groups/${groupId}/members`, { account_ids: accountIds })
}

export function removeMembers(groupId, accountIds) {
  return client.delete(`/api/account-groups/${groupId}/members`, { data: { account_ids: accountIds } })
}
```

- [ ] **Step 2: 创建 AccountGroupsPage.vue**

基于 `AccountsPage.vue` 的模式创建分组管理页面：
- 表格列：名称、描述、成员数、操作（编辑、管理成员、删除）
- 创建/编辑分组弹窗
- 成员管理弹窗：左侧可选账号列表（仅 active），右侧已选账号

- [ ] **Step 3: 在 router/index.js 添加路由**

在 `children` 数组中 `accounts` 路由之后添加：

```javascript
{
  path: 'account-groups',
  name: 'AccountGroups',
  component: () => import('../views/AccountGroupsPage.vue'),
},
```

- [ ] **Step 4: 在 AdminLayout.vue 导航栏添加入口**

在「账号管理」导航项之后添加「账号分组」。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/accountGroups.js web/src/views/AccountGroupsPage.vue web/src/router/index.js web/src/views/AdminLayout.vue
git commit -m "feat: add account groups management page"
```

---

## Task 8: 前端 — 链模板编辑器

**Files:**
- Create: `web/src/api/chains.js`
- Create: `web/src/views/ChainTemplatesPage.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/views/AdminLayout.vue`

- [ ] **Step 1: 创建 API 模块 web/src/api/chains.js**

```javascript
import client from './client.js'

// Templates
export function listTemplates(params = {}) {
  return client.get('/api/chains/templates', { params })
}

export function getTemplate(id) {
  return client.get(`/api/chains/templates/${id}`)
}

export function createTemplate(data) {
  return client.post('/api/chains/templates', data)
}

export function updateTemplate(id, data) {
  return client.put(`/api/chains/templates/${id}`, data)
}

export function deleteTemplate(id) {
  return client.delete(`/api/chains/templates/${id}`)
}

// Instances
export function listInstances(params = {}) {
  return client.get('/api/chains/instances', { params })
}

export function getInstance(id) {
  return client.get(`/api/chains/instances/${id}`)
}

export function createInstances(data) {
  return client.post('/api/chains/instances', data)
}

export function cancelInstance(id) {
  return client.post(`/api/chains/instances/${id}/cancel`)
}

export function retryInstance(id) {
  return client.post(`/api/chains/instances/${id}/retry`)
}
```

- [ ] **Step 2: 创建 ChainTemplatesPage.vue**

模板管理页面：
- 模板列表表格（名称、步骤数、操作）
- 创建/编辑模板弹窗：
  - 模板名称、描述
  - 步骤编辑器：
    - 每步：任务类型下拉 → 动态参数表单
    - 添加步骤 / 删除步骤按钮
    - 步骤排序（上下移动按钮）

- [ ] **Step 3: 添加路由和导航**

```javascript
{
  path: 'chain-templates',
  name: 'ChainTemplates',
  component: () => import('../views/ChainTemplatesPage.vue'),
},
```

- [ ] **Step 4: Commit**

```bash
git add web/src/api/chains.js web/src/views/ChainTemplatesPage.vue web/src/router/index.js web/src/views/AdminLayout.vue
git commit -m "feat: add chain template editor page"
```

---

## Task 9: 前端 — 链实例管理

**Files:**
- Create: `web/src/views/ChainInstancesPage.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/views/AdminLayout.vue`

- [ ] **Step 1: 创建 ChainInstancesPage.vue**

链实例管理页面：
- 实例列表表格（模板名、账号、当前步骤、状态、操作）
- 批量创建弹窗：
  - 选择模板
  - 选择账号（直接选 / 选分组）
  - 账号显示繁忙状态
  - 创建结果展示
- 链详情弹窗：
  - 步骤时间线（当前步骤高亮，已完成显示结果）
  - 操作：取消、重试

- [ ] **Step 2: 添加路由和导航**

```javascript
{
  path: 'chain-instances',
  name: 'ChainInstances',
  component: () => import('../views/ChainInstancesPage.vue'),
},
```

- [ ] **Step 3: Commit**

```bash
git add web/src/views/ChainInstancesPage.vue web/src/router/index.js web/src/views/AdminLayout.vue
git commit -m "feat: add chain instances management page"
```

---

## Task 10: 前端 — TasksPage 养号表单更新 + 关键词搜索

**Files:**
- Modify: `web/src/views/TasksPage.vue`

- [ ] **Step 1: 更新养号参数表单**

当任务类型为 `nurture` 时，显示新的子任务配置界面：
- 子任务列表（每行：类型下拉 + 次数输入 + 删除按钮）
- 添加子任务按钮
- 完成模式下拉（全部完成 / 任一完成）
- 最大时长输入

保留旧版「简单模式」切换开关，方便快速创建。

- [ ] **Step 2: 添加关键词搜索快捷入口**

在任务列表上方添加「关键词搜索」按钮：
- 点击弹出对话框：
  1. 输入种子关键词
  2. 调用 `POST /api/content/generate-keywords` 获取关键词矩阵
  3. 可编辑关键词列表
  4. 选择操作类型（search_comment / reply_comment / search_dm）
  5. 选择账号/分组
  6. 批量创建任务

- [ ] **Step 3: Commit**

```bash
git add web/src/views/TasksPage.vue
git commit -m "feat: update nurture form + add keyword search shortcut"
```

---

## Task 11: 后端 — 关键词矩阵生成 API

**Files:**
- Modify: `server/app/services/content_service.py`
- Modify: `server/app/routers/content.py`

- [ ] **Step 1: 在 content_service.py 添加关键词矩阵生成方法**

```python
async def generate_keyword_matrix(self, keyword: str, count: int = 10) -> list[str]:
    """Generate expanded keyword matrix from a seed keyword using AI."""
    prompt = f"""基于关键词「{keyword}」，生成 {count} 个相关的抖音搜索关键词。
要求：
1. 包含同义词、长尾词、热门话题标签
2. 适合抖音搜索场景
3. 每个关键词 2-8 个字
4. 只返回 JSON 数组格式，不要其他内容
示例：["关键词1", "关键词2", "关键词3"]"""

    response = await self._call_ai(prompt)
    try:
        keywords = json.loads(response)
        if isinstance(keywords, list):
            return [str(k) for k in keywords][:count]
    except json.JSONDecodeError:
        pass
    # Fallback: return the seed keyword itself
    return [keyword]
```

- [ ] **Step 2: 在 content.py 添加端点**

```python
class KeywordMatrixRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50)
    count: int = Field(default=10, ge=1, le=30)


@router.post("/generate-keywords")
async def generate_keywords(
    request: KeywordMatrixRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    keywords = await content_service.generate_keyword_matrix(request.keyword, request.count)
    return {"keywords": keywords, "seed": request.keyword}
```

- [ ] **Step 3: Commit**

```bash
git add server/app/services/content_service.py server/app/routers/content.py
git commit -m "feat: add keyword matrix generation API"
```

---

## 实施顺序

```
Task 1  ──→ Task 2  ──→ Task 5  ──→ Task 6  ──→ Task 7  ──→ Task 8  ──→ Task 9
(Task 3 也可并行)  ──→ Task 4  ─────────┘                    ──→ Task 10
                                                        Task 11 (独立)
```

建议按以下批次执行：
1. **批次 1:** Task 1 + Task 3（数据模型，无依赖，可并行）
2. **批次 2:** Task 2 + Task 4（API 端点，依赖数据模型）
3. **批次 3:** Task 5（互斥锁 + 链引擎，依赖 Task 4）
4. **批次 4:** Task 6（养号重构，独立）
5. **批次 5:** Task 7 + Task 8 + Task 9（前端页面，可并行）
6. **批次 6:** Task 10 + Task 11（关键词搜索，依赖前面所有）
