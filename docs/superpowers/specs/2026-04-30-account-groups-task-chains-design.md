# 账号分组 + 任务链 设计文档

> 本文档覆盖两大功能模块：**账号分组** 和 **任务链**，以及对现有养号任务的重构。所有设计均基于项目已有架构（FastAPI + SQLAlchemy + Vue 3 + AutoJS6 设备端），与现有 8 个后端路由、8 个前端页面、5 种任务类型、WS 推送管线完全整合。

---

## 1. 现有架构概览

### 后端（FastAPI）

| 路由模块 | 前缀 | 职责 |
|----------|------|------|
| `auth.py` | `/api/auth` | 管理员认证 |
| `device.py` | `/api/device` | 设备端 API（注册、心跳、轮询、上报） |
| `devices.py` | `/api/devices` | 管理端设备 CRUD + 配对审批 |
| `tasks.py` | `/api/tasks` | 任务 CRUD + WS 推送 |
| `accounts.py` | `/api/accounts` | 账号 CRUD |
| `selectors.py` | `/api/selectors` | UI 选择器管理 |
| `stats.py` | `/api/stats` | 统计数据 |
| `content.py` | `/api/content` | 内容模板 + 敏感词 + AI 生成 |

### 服务层

| 服务 | 职责 |
|------|------|
| `task_service.py` | 任务创建、领取（乐观锁）、上报、取消 |
| `device_service.py` | 设备注册、心跳、离线检测 |
| `stats_service.py` | 每日操作计数、配额检查 |
| `content_service.py` | 模板管理、AI 内容生成 |
| `risk_service.py` | 风控事件记录 |

### 设备端（AutoJS6）

| 模块 | 职责 |
|------|------|
| `main.js` | 入口：配对 → 注册 → WS → 心跳 → 任务执行 |
| `task-executor.js` | 任务分发到 handler，支持取消 |
| `device-ws.js` | WebSocket 连接管理 + 消息分发 |
| `handlers/nurture.js` | 养号：按权重随机执行 browse/like/follow |
| `handlers/search-base.js` | 搜索基类：关键词导航 |
| `handlers/search-comment.js` | 搜索评论 |
| `handlers/search-like.js` | 搜索点赞 |
| `handlers/search-dm.js` | 搜索私信 |
| `handlers/reply-comment.js` | 评论回复（AI 评分 → 回复/关注/私信） |
| `ai-analyzer.js` | 五维 AI 评论分析模型 |

### 前端（Vue 3 + Pinia）

| 页面 | 路由 | 职责 |
|------|------|------|
| `DashboardPage` | `/` | 仪表盘 |
| `AccountsPage` | `/accounts` | 账号 CRUD |
| `DevicesPage` | `/devices` | 设备管理 + 配对审批 |
| `TasksPage` | `/tasks` | 任务创建/列表/取消 |
| `SelectorsPage` | `/selectors` | 选择器管理 |
| `StatsPage` | `/stats` | 统计图表 |
| `ContentPage` | `/content` | 内容模板 + 敏感词 |

### 任务类型

| 类型 | 参数 | 设备端 Handler |
|------|------|---------------|
| `nurture` | `duration` | `nurture.js` — 按权重随机浏览/点赞/关注 |
| `search_comment` | `keyword`, `content`, `count`, `sort_by` | `search-comment.js` |
| `search_like` | `keyword`, `count`, `sort_by` | `search-like.js` |
| `search_dm` | `keyword`, `content`, `count`, `sort_by` | `search-dm.js` |
| `reply_comment` | `keyword`, `content`, `count`, `video_count`, `sort_by`, `max_age_days` | `reply-comment.js` |

### WS 推送协议

服务端通过 `/ws/status` 连接推送：
- `task` — 新任务分配
- `cancel_task` — 取消任务
- `selectors_updated` — 选择器版本变更
- `config_updated` — 设备配置/代理变更
- `device_removed` — 设备被删除

---

## 2. 账号分组

### 2.1 设计目标

- 独立的分组实体，与账号是 **多对多** 关系
- 一个账号可以属于多个分组
- 创建任务链时可以按分组批量选择账号
- 只有 `active` 状态的账号可被选中

### 2.2 数据模型

**新增表 `account_groups`：**

```python
class AccountGroup(Base):
    __tablename__ = "account_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

**新增关联表 `account_group_members`：**

```python
class AccountGroupMember(Base):
    __tablename__ = "account_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "account_id", name="uq_group_account"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("account_groups.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

### 2.3 API 端点

新增路由模块 `server/app/routers/account_groups.py`，前缀 `/api/account-groups`：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/` | 创建分组 |
| `GET` | `/` | 列出所有分组（含成员数量） |
| `GET` | `/{group_id}` | 获取分组详情（含成员列表） |
| `PUT` | `/{group_id}` | 更新分组名称/描述 |
| `DELETE` | `/{group_id}` | 删除分组（同时删除关联） |
| `POST` | `/{group_id}/members` | 批量添加成员（接收 `account_ids` 列表） |
| `DELETE` | `/{group_id}/members` | 批量移除成员（接收 `account_ids` 列表） |
| `GET` | `/{group_id}/members` | 获取分组成员列表（支持 `status=active` 过滤） |

### 2.4 前端页面

新增 `AccountGroupsPage.vue`，路由 `/account-groups`：

- 分组列表（表格：名称、描述、成员数、操作）
- 创建/编辑分组弹窗
- 成员管理弹窗：
  - 左侧：可选账号列表（仅 `active` 状态，支持搜索）
  - 右侧：已选账号列表
  - 支持批量添加/移除

在 `AdminLayout.vue` 导航栏添加「账号分组」入口。

### 2.5 与现有功能的关系

- `Account` 表的 `group` 字段（`String(50)`）保留不变，它是账号的简单标签，用于前端筛选
- 新增的 `AccountGroup` 是独立实体，通过关联表实现多对多
- 创建任务链时，选择分组 → 展开为该分组下所有 `active` 账号 → 逐个创建链实例

---

## 3. 账号互斥锁

### 3.1 设计目标

- 一个账号同时只能执行一条任务链
- 如果账号有 `pending` 或 `running` 状态的任务，不能接受新任务
- 三层一致性：服务端 DB、设备端执行器、前端显示

### 3.2 实现方式

**服务端检查（创建任务时）：**

在 `task_service.create_task()` 和新的链创建逻辑中，创建任务前检查：

```python
def is_account_busy(self, db: Session, account_id: str) -> bool:
    """检查账号是否有正在执行或待执行的任务。"""
    count = db.query(DBTask).filter(
        DBTask.account_id == account_id,
        DBTask.status.in_(["pending", "running"]),
    ).count()
    return count > 0
```

**链创建时的批量检查：**

```python
def create_chain_instances(self, db: Session, chain_def, account_ids: list[str]):
    """为每个账号创建链实例，跳过繁忙账号。"""
    results = {"created": [], "skipped_busy": [], "skipped_error": []}
    for account_id in account_ids:
        if self.is_account_busy(db, account_id):
            results["skipped_busy"].append(account_id)
            continue
        # 创建链实例...
    return results
```

**前端展示：**

- 选择账号时，繁忙账号显示「执行中」标签并禁用选择
- 批量创建后，展示结果：成功 N 个，跳过 N 个（繁忙）

### 3.3 状态流转

```
账号空闲 → 领取任务 → 执行中 → 完成/失败 → 账号空闲
                ↑                              |
                └──────── 重试（失败时）──────────┘
```

---

## 4. 任务链

### 4.1 设计目标

- 自由组合现有任务类型为有序步骤
- 链模板可复用
- 服务端编排，逐步释放任务到设备
- 每个步骤是独立的 Task 记录
- 实时步骤状态推送到前端

### 4.2 数据模型

**新增表 `chain_templates`：**

```python
class ChainTemplate(Base):
    __tablename__ = "chain_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True, default="")
    steps = Column(JSON, nullable=False)  # 见下方 steps 结构
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

**`steps` JSON 结构：**

```json
[
  {
    "step_order": 1,
    "type": "nurture",
    "label": "养号 30 分钟",
    "params": { "duration": 30 }
  },
  {
    "step_order": 2,
    "type": "search_comment",
    "label": "搜索评论",
    "params": { "keyword": "美食", "count": 5, "content": "不错！" }
  },
  {
    "step_order": 3,
    "type": "reply_comment",
    "label": "回复评论",
    "params": { "keyword": "美食", "video_count": 3, "count": 5 }
  }
]
```

每个 step 包含：
- `step_order`：步骤顺序（从 1 开始）
- `type`：任务类型（现有 5 种之一）
- `label`：步骤显示名称（前端展示用）
- `params`：该步骤的任务参数（与现有 TaskCreateRequest.params 一致）

**新增表 `chain_instances`：**

```python
class ChainInstance(Base):
    __tablename__ = "chain_instances"

    id = Column(String(36), primary_key=True, default=_uuid)
    template_id = Column(String(36), ForeignKey("chain_templates.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    current_step = Column(Integer, nullable=False, default=1)  # 当前执行到第几步
    total_steps = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    template = relationship("ChainTemplate")
    account = relationship("Account")
```

**Task 表新增字段：**

```python
# 在现有 Task 模型上新增
chain_instance_id = Column(String(36), ForeignKey("chain_instances.id"), nullable=True)
step_order = Column(Integer, nullable=True)  # 在链中的步骤序号

# 新增 relationship
chain_instance = relationship("ChainInstance")
```

同步更新 Pydantic `Task` 模型：
```python
chain_instance_id: Optional[str] = None
step_order: Optional[int] = None
```

### 4.3 链状态机

```
pending ──→ running ──→ (步骤完成) ──→ running ──→ ... ──→ completed
                    │         │
                    │         ↓ (某步骤失败)
                    │      failed
                    │
                    └──→ cancelled (手动取消)
```

注意：`step_completed` 不是持久状态，只是链内部的瞬时转换。DB 中链实例的 status 只有 `pending`, `running`, `completed`, `failed`, `cancelled` 五种。当一个步骤完成时，`advance_chain` 立即创建下一步任务并将 status 保持为 `running`。

- `pending`：链实例已创建，等待第一步执行
- `running`：当前步骤正在执行
- `completed`：所有步骤执行完成
- `failed`：某步骤执行失败且无法重试
- `cancelled`：手动取消

### 4.4 API 端点

**链模板 CRUD — 新增路由 `server/app/routers/chains.py`，前缀 `/api/chains`：**

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/templates` | 创建链模板 |
| `GET` | `/templates` | 列出所有模板 |
| `GET` | `/templates/{id}` | 获取模板详情 |
| `PUT` | `/templates/{id}` | 更新模板 |
| `DELETE` | `/templates/{id}` | 删除模板 |

**链实例管理：**

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/instances` | 批量创建链实例（指定模板 + 账号列表/分组） |
| `GET` | `/instances` | 列出链实例（支持按状态、账号、模板过滤） |
| `GET` | `/instances/{id}` | 获取链实例详情（含当前步骤状态） |
| `POST` | `/instances/{id}/cancel` | 取消链实例（取消当前执行中的步骤 + 后续步骤） |
| `POST` | `/instances/{id}/retry` | 重试失败的链实例（从失败步骤重新开始） |

**创建链实例请求体：**

```python
class ChainInstanceCreateRequest(BaseModel):
    template_id: str
    account_ids: Optional[list[str]] = None       # 直接指定账号列表
    group_ids: Optional[list[str]] = None          # 或指定分组（展开为账号列表）
```

服务端逻辑：
1. 如果指定了 `group_ids`，查询所有分组内的 `active` 账号，合并去重
2. 对每个账号执行互斥检查（`is_account_busy`）
3. 为空闲账号创建 `ChainInstance` 记录
4. 为每个链实例创建第 1 步的 `Task` 记录
5. 通过 WS 推送第 1 步任务到设备
6. 返回创建结果（成功/跳过的账号列表）

### 4.5 链编排引擎

新增服务 `server/app/services/chain_service.py`：

```python
class ChainService:
    def advance_chain(self, db: Session, task_id: str, status: str, result: dict):
        """任务完成后推进链到下一步。"""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task or not task.chain_instance_id:
            return  # 非链任务，忽略

        chain = db.query(ChainInstance).filter(
            ChainInstance.id == task.chain_instance_id
        ).first()
        if not chain:
            return

        if status == "completed":
            next_step = task.step_order + 1
            if next_step > chain.total_steps:
                # 所有步骤完成
                chain.status = "completed"
                chain.completed_at = datetime.now(timezone.utc)
            else:
                # 创建下一步任务
                chain.current_step = next_step
                self._create_step_task(db, chain, next_step)
        elif status == "failed":
            chain.status = "failed"
            chain.completed_at = datetime.now(timezone.utc)

        db.commit()

    def _create_step_task(self, db: Session, chain: ChainInstance, step_order: int):
        """从模板中提取步骤参数，创建 Task 记录并推送。调用方负责 commit。"""
        template = chain.template
        step = next(s for s in template.steps if s["step_order"] == step_order)

        task = DBTask(
            type=step["type"],
            account_id=chain.account_id,
            params=step["params"],
            status="pending",
            chain_instance_id=chain.id,
            step_order=step_order,
        )
        db.add(task)
        db.flush()  # 获取 task.id，但不 commit（由 advance_chain 统一 commit）

        # WS 推送（复用 task_service 中已有的 _db_task_to_pydantic 转换）
        from app.ws_manager import pair_ws_manager
        from app.services.task_service import _db_task_to_pydantic
        device = db.query(Device).filter(Device.bound_account_id == chain.account_id).first()
        if device:
            pydantic_task = _db_task_to_pydantic(task)
            pair_ws_manager.send_to_device(device.id, {
                "event": "task",
                "task": pydantic_task.model_dump(mode="json"),
            })
```

**与 `task_service.report_result()` 的集成：**

在现有的 `report_result` 方法末尾，调用链推进：

```python
# 在 task_service.report_result() 中，status 更新后：
from app.services.chain_service import chain_service
chain_service.advance_chain(db, task_id, status.value, result)
```

### 4.6 实时步骤状态报告

**设备端 → 服务端：**

设备每完成一个步骤，通过现有的 `POST /api/device/report` 上报结果。如果任务是链的一部分，服务端自动推进到下一步。

新增 WS 消息类型 `chain_step_update`，服务端推送到前端：

```json
{
  "event": "chain_step_update",
  "chain_instance_id": "xxx",
  "step_order": 2,
  "step_status": "running",
  "step_label": "搜索评论",
  "account_id": "xxx",
  "timestamp": "2026-04-30T10:00:00Z"
}
```

**服务端 → 前端：**

前端通过已有的 admin WS 连接（`/api/devices/ws/pair-events`）接收链步骤更新事件。

### 4.7 前端页面

**链模板管理 — 新增 `ChainTemplatesPage.vue`，路由 `/chain-templates`：**

- 模板列表（表格：名称、步骤数、操作）
- 创建/编辑模板弹窗：
  - 模板名称、描述
  - 步骤编辑器：
    - 可拖拽排序的步骤列表
    - 每步选择任务类型 → 动态显示对应参数表单
    - 添加/删除步骤按钮
    - 步骤预览（类型图标 + 参数摘要）

**链实例管理 — 新增 `ChainInstancesPage.vue`，路由 `/chain-instances`：**

- 链实例列表（表格：模板名、账号、当前步骤、状态、进度条、操作）
- 批量创建弹窗：
  - 选择模板
  - 选择账号方式：直接选账号 / 选分组
  - 账号选择器（显示繁忙状态）
  - 创建结果展示（成功/跳过数量）
- 链详情弹窗：
  - 步骤时间线（当前步骤高亮，已完成步骤显示结果）
  - 操作按钮：取消、重试（失败时）

在 `AdminLayout.vue` 导航栏添加「任务链模板」和「链实例」入口。

---

## 5. 养号任务重构

### 5.1 设计目标

- 从单一 `duration` 参数重构为可配置的子任务组合
- 支持子任务级 AI 内容生成
- `completion_mode` 控制结束条件

### 5.2 新参数结构

```python
class NurtureSubTask(BaseModel):
    type: str = Field(..., pattern="^(browse|watch|like|comment|follow)$")
    count: int = Field(default=1, ge=1, le=100)
    content_template_id: Optional[str] = None  # comment 类型可用

class NurtureParamsV2(BaseModel):
    sub_tasks: list[NurtureSubTask] = Field(..., min_length=1)
    completion_mode: str = Field(default="all", pattern="^(all|any)$")
    duration: int = Field(default=60, ge=1, le=240, description="最大时长(分钟)")
```

- `sub_tasks`：子任务列表，每个子任务指定类型和目标次数
- `completion_mode`：`all` = 全部完成才结束；`any` = 任一完成即结束
- `duration`：最大时长上限（防止无限执行）

### 5.3 示例

```json
{
  "sub_tasks": [
    { "type": "browse", "count": 10 },
    { "type": "like", "count": 5 },
    { "type": "comment", "count": 2, "content_template_id": "tpl_xxx" },
    { "type": "follow", "count": 3 }
  ],
  "completion_mode": "all",
  "duration": 60
}
```

### 5.4 设备端 Handler 重构

`nurture.js` 重构为：

```javascript
NurtureHandler.execute = function (params) {
  // 兼容旧版：如果传入 duration 但没有 sub_tasks，使用旧逻辑
  if (!params.sub_tasks) {
    return this._legacyExecute(params);
  }

  var subTasks = params.sub_tasks;
  var completionMode = params.completion_mode || "all";
  var maxDuration = (params.duration || 60) * 60 * 1000;
  var startTime = Date.now();

  // 初始化每个子任务的进度
  var progress = subTasks.map(function (st) {
    return { type: st.type, target: st.count, done: 0, contentTemplateId: st.content_template_id };
  });

  while (Date.now() - startTime < maxDuration) {
    // 找到未完成的子任务
    var pending = progress.filter(function (p) { return p.done < p.target; });
    if (pending.length === 0) break; // 全部完成

    // 随机选一个未完成的子任务执行
    var task = pending[Math.floor(Math.random() * pending.length)];
    this._executeSubTask(task);
    task.done++;

    // 检查完成条件
    if (completionMode === "any") {
      var anyDone = progress.some(function (p) { return p.done >= p.target; });
      if (anyDone) break;
    }

    antiDetect.humanSwipeUp();
  }

  // 统计结果
  var stats = {};
  progress.forEach(function (p) {
    stats[p.type] = { target: p.target, done: p.done };
  });
  return { success: true, result: stats };
};
```

### 5.5 向后兼容

- `TaskCreateRequest.params` 接受旧格式 `{ "duration": 30 }` 和新格式 `{ "sub_tasks": [...], "completion_mode": "all", "duration": 60 }`
- 服务端 `NurtureParams` 保留，新增 `NurtureParamsV2`
- 设备端 handler 同时支持两种格式

---

## 6. 关键词搜索工作流

### 6.1 设计目标

- 用户输入关键词 → 服务端 AI 生成关键词矩阵 → 设备搜索每个关键词
- 对搜索结果中的视频评论进行 AI 五维评分
- 根据评分阈值触发不同动作（回复/关注/私信）

### 6.2 工作流

```
用户输入关键词（如"美食"）
  ↓
服务端 AI 生成关键词矩阵
  ["美食做法", "家常菜", "美食推荐", "好吃的", ...]
  ↓
为每个关键词创建搜索任务（或作为链的步骤）
  ↓
设备执行搜索 → 获取视频列表
  ↓
对每个视频的评论进行 AI 五维评分
  ↓
根据评分阈值触发动作：
  - 高分（lead_quality >= 8）→ 回复 + 关注 + 私信
  - 中分（lead_quality >= 5）→ 回复 + 关注
  - 低分（lead_quality >= 3）→ 仅回复
  - 极低分 → 跳过
```

### 6.3 服务端 AI 关键词生成

新增 `content_service.py` 方法：

```python
async def generate_keyword_matrix(self, keyword: str, count: int = 10) -> list[str]:
    """基于种子关键词生成扩展关键词矩阵。"""
    prompt = f"""基于关键词「{keyword}」，生成 {count} 个相关的抖音搜索关键词。
要求：
1. 包含同义词、长尾词、热门话题标签
2. 适合抖音搜索场景
3. 每个关键词 2-8 个字
4. 返回 JSON 数组格式"""

    response = await self._call_ai(prompt)
    return json.loads(response)  # ["关键词1", "关键词2", ...]
```

### 6.4 集成方式

关键词搜索不是一个新任务类型，而是通过 **任务链** 组合实现：

1. 用户在链模板编辑器中创建「关键词搜索」模板
2. 第一步：`search_comment`（搜索主关键词）
3. 后续步骤：`reply_comment`（对搜索结果进行回复）
4. 或者使用批量创建：AI 生成关键词矩阵 → 为每个关键词创建独立的搜索任务

**前端快捷入口：**

在 `TasksPage.vue` 添加「关键词搜索」快捷按钮：
1. 输入种子关键词
2. AI 自动生成关键词矩阵（可编辑）
3. 选择要执行的操作类型
4. 选择账号/分组
5. 批量创建任务

---

## 7. 前端导航结构更新

```
AdminLayout 导航栏：
├── 仪表盘          /
├── 账号管理        /accounts
├── 账号分组        /account-groups       ← 新增
├── 设备管理        /devices
├── 任务中心        /tasks
├── 任务链模板      /chain-templates      ← 新增
├── 链实例          /chain-instances      ← 新增
├── 选择器管理      /selectors
├── 数据统计        /stats
└── 内容管理        /content
```

---

## 8. 文件变更清单

### 后端新增

| 文件 | 说明 |
|------|------|
| `server/app/routers/account_groups.py` | 账号分组 CRUD API |
| `server/app/routers/chains.py` | 链模板 + 链实例 API |
| `server/app/services/chain_service.py` | 链编排引擎 |
| `server/app/db_models.py` | 新增 AccountGroup, AccountGroupMember, ChainTemplate, ChainInstance 模型 |
| `server/app/models.py` | 新增 NurtureParamsV2, ChainTemplateCreate/Update/Response, ChainInstanceCreateRequest |

### 后端修改

| 文件 | 变更 |
|------|------|
| `server/app/db_models.py` | Task 表新增 `chain_instance_id`, `step_order` 字段 |
| `server/app/services/task_service.py` | `create_task()` 新增互斥检查；`report_result()` 末尾调用链推进 |
| `server/app/routers/tasks.py` | 参数校验支持 NurtureParamsV2 |
| `server/app/main.py` | 注册新路由 |
| `server/app/services/content_service.py` | 新增 `generate_keyword_matrix()` |

### 设备端修改

| 文件 | 变更 |
|------|------|
| `device/handlers/nurture.js` | 重构为支持 sub_tasks + completion_mode，保留旧版兼容 |

### 前端新增

| 文件 | 说明 |
|------|------|
| `web/src/views/AccountGroupsPage.vue` | 账号分组管理页面 |
| `web/src/views/ChainTemplatesPage.vue` | 链模板编辑器 |
| `web/src/views/ChainInstancesPage.vue` | 链实例管理页面 |
| `web/src/api/accountGroups.js` | 账号分组 API 模块 |
| `web/src/api/chains.js` | 链模板 + 链实例 API 模块 |

### 前端修改

| 文件 | 变更 |
|------|------|
| `web/src/router/index.js` | 新增 3 条路由 |
| `web/src/views/AdminLayout.vue` | 导航栏新增 3 个入口 |
| `web/src/views/TasksPage.vue` | 养号参数表单更新 + 关键词搜索快捷入口 |

---

## 9. 实施优先级

| 阶段 | 内容 | 依赖 |
|------|------|------|
| P1 | 账号分组（数据模型 + API + 前端） | 无 |
| P2 | 互斥锁（服务端检查 + 前端繁忙标识） | 无 |
| P3 | 链模板（数据模型 + API + 前端编辑器） | 无 |
| P4 | 链实例 + 编排引擎 | P3 |
| P5 | 养号重构（sub_tasks + completion_mode） | 无 |
| P6 | 关键词搜索快捷入口 | P1 + P3 + P4 |
| P7 | 实时步骤状态推送 | P4 |

P1-P3 可并行开发；P4 依赖 P3；P5 独立；P6 依赖 P1+P3+P4；P7 依赖 P4。
