# Autoplan 审查修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 autoplan 审查发现的规范缺失和代码缺陷

**Architecture:** 修复分为三类：Critical bug（BaseModel 未导入）、规范缺失（TasksPage.vue 养号 V2 表单 + 关键词搜索入口）、代码改进（链实例初始状态修正）

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, Pinia, HeadlessUI

**Spec:** `docs/superpowers/specs/2026-04-30-account-groups-task-chains-design.md`
**Original Plan:** `docs/superpowers/plans/2026-04-30-account-groups-task-chains.md`

---

## 文件结构

### 修改文件
- `server/app/routers/tasks.py` — 修复 BaseModel 导入
- `web/src/api/content.js` — 添加 generateKeywords API 函数
- `web/src/views/TasksPage.vue` — 养号 V2 表单 + 关键词搜索入口
- `server/app/services/chain_service.py` — 链实例初始状态修正

---

## Task 1: 修复 tasks.py BaseModel 导入 [CRITICAL]

**问题:** `tasks.py:63` 使用 `BaseModel` 但未导入，非养号任务（search_comment 等）创建时抛 `NameError`。

**Files:**
- Modify: `server/app/routers/tasks.py:6-7`

- [x] **Step 1: 修复导入**

将：
```python
from app.models import TaskCreateRequest, TaskStatus, TASK_PARAMS_VALIDATORS, KeywordMatrixRequest
```
改为：
```python
from pydantic import BaseModel
from app.models import TaskCreateRequest, TaskStatus, TASK_PARAMS_VALIDATORS
```

同时移除未使用的 `KeywordMatrixRequest` 导入。

- [x] **Step 2: 验证导入**

```bash
cd server && python -c "from app.routers.tasks import router; print('OK')"
```

Expected: `OK`

- [x] **Step 3: 运行测试**

```bash
cd server && python -m pytest tests/ -x -q
```

Expected: 全部通过

---

## Task 2: 添加 generateKeywords API 函数

**问题:** `content.js` 缺少 `generateKeywords` 导出函数，前端无法调用关键词矩阵生成 API。

**Files:**
- Modify: `web/src/api/content.js`

- [x] **Step 1: 添加函数**

在 `content.js` 末尾追加：

```javascript
export function generateKeywords(keyword, count = 10) {
  return client.post('/content/generate-keywords', { keyword, count })
}
```

---

## Task 3: TasksPage 养号 V2 表单

**问题:** TasksPage.vue 养号参数只有单个 `duration` 输入框，无法使用 V2 格式（sub_tasks + completion_mode）。

**Files:**
- Modify: `web/src/views/TasksPage.vue`

- [x] **Step 1: 添加 V2 状态变量**

在 `form` reactive 之后添加：

```javascript
// --- Nurture V2 state ---
const nurtureMode = ref('simple') // 'simple' or 'advanced'
const subTasks = ref([{ type: 'browse', count: 10, content_template_id: '' }])
const completionMode = ref('all')
const maxDuration = ref(60)

const subTaskTypeOptions = [
  { value: 'browse', label: '浏览' },
  { value: 'watch', label: '观看' },
  { value: 'like', label: '点赞' },
  { value: 'comment', label: '评论' },
  { value: 'follow', label: '关注' },
]

function addSubTask() {
  subTasks.value.push({ type: 'browse', count: 5, content_template_id: '' })
}

function removeSubTask(index) {
  subTasks.value.splice(index, 1)
}
```

- [x] **Step 2: 更新 buildParams()**

将养号参数构建改为：

```javascript
if (form.type === 'nurture') {
  if (nurtureMode.value === 'advanced' && subTasks.value.length > 0) {
    return {
      sub_tasks: subTasks.value.map(st => ({
        type: st.type,
        count: st.count,
        ...(st.type === 'comment' && st.content_template_id ? { content_template_id: st.content_template_id } : {}),
      })),
      completion_mode: completionMode.value,
      duration: maxDuration.value,
    }
  }
  return {
    duration: form.duration,
  }
}
```

- [x] **Step 3: 更新养号表单模板**

将原有的单个 duration 输入替换为简单/高级模式切换：
- 简单模式：保留原有 duration 输入
- 高级模式：子任务列表（类型+次数+模板选择）、完成模式、最大时长

---

## Task 4: TasksPage 关键词搜索入口

**问题:** 设计规范 §6.4 要求在 TasksPage 添加关键词搜索快捷入口，未实现。

**Files:**
- Modify: `web/src/views/TasksPage.vue`

- [x] **Step 1: 添加关键词搜索状态**

```javascript
const showKeywordDialog = ref(false)
const keywordSeed = ref('')
const keywordList = ref([])
const keywordGenerating = ref(false)
const keywordError = ref(null)
const keywordActionType = ref('search_comment')
const keywordAccountId = ref('')
const keywordCount = ref(10)
```

- [x] **Step 2: 添加搜索函数**

- `openKeywordDialog()` — 重置状态，打开对话框
- `handleGenerateKeywords()` — 调用 `generateKeywords` API
- `removeKeyword(idx)` — 从列表移除关键词
- `handleBatchCreateKeywordTasks()` — 批量创建任务

- [x] **Step 3: 添加按钮和对话框**

在 header 区域添加「关键词搜索」按钮（绿色），在 Cancel Confirmation Dialog 之后添加关键词搜索对话框：
- 种子关键词输入 + 数量 + AI 扩展按钮
- 关键词标签云（可删除）
- 操作类型下拉
- 账号选择
- 批量创建按钮

---

## Task 5: 链实例初始状态修正

**问题:** `chain_service.py:51` 创建链实例时 `status="running"`，规范定义初始状态应为 `pending`。

**Files:**
- Modify: `server/app/services/chain_service.py:46-53`

- [ ] **Step 1: 修改初始状态**

将：
```python
instance = ChainInstance(
    template_id=template_id,
    account_id=account_id,
    current_step=1,
    total_steps=total_steps,
    status="running",
    started_at=datetime.now(timezone.utc),
)
```

改为：
```python
instance = ChainInstance(
    template_id=template_id,
    account_id=account_id,
    current_step=1,
    total_steps=total_steps,
    status="pending",
)
```

注意：`started_at` 不在创建时设置，而是在任务被设备领取时设置。

- [ ] **Step 2: 确保 advance_chain 更新 started_at**

在 `advance_chain` 中，当链从 pending 转为 running 时设置 `started_at`：

```python
if status == "completed":
    next_step = task.step_order + 1
    if next_step > chain.total_steps:
        chain.status = "completed"
        chain.completed_at = datetime.now(timezone.utc)
    else:
        chain.current_step = next_step
        chain.status = "running"
        if not chain.started_at:
            chain.started_at = datetime.now(timezone.utc)
        template = db.query(ChainTemplate).filter(ChainTemplate.id == chain.template_id).first()
        if template:
            self._create_step_task(db, chain, next_step, template)
            db.flush()
            self._push_step_task(db, chain)
elif status == "failed":
    chain.status = "failed"
    chain.completed_at = datetime.now(timezone.utc)
```

同时在 `create_chain_instances` 中，第一步任务被创建后将状态改为 running：

```python
self._create_step_task(db, instance, 1, template)
instance.status = "running"
instance.started_at = datetime.now(timezone.utc)
results["created"].append(account_id)
```

- [ ] **Step 3: 运行测试**

```bash
cd server && python -m pytest tests/ -x -q
```

Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add server/app/services/chain_service.py
git commit -m "fix: chain instance initial status should be pending per spec"
```

---

## 实施状态

| Task | 状态 | 说明 |
|------|------|------|
| Task 1: BaseModel 导入 | ✅ 已完成 | Critical bug，已修复 |
| Task 2: generateKeywords API | ✅ 已完成 | 已添加到 content.js |
| Task 3: 养号 V2 表单 | ✅ 已完成 | 简单/高级模式切换 |
| Task 4: 关键词搜索入口 | ✅ 已完成 | 按钮 + 对话框 + 批量创建 |
| Task 5: 链实例初始状态 | ✅ 已完成 | 规范偏差修正 |

---

## 验证

1. 创建 search_comment 任务 → 不再报 NameError ✅
2. TasksPage 养号任务 → 可切换简单/高级模式 ✅
3. TasksPage 关键词搜索 → AI 扩展 + 批量创建 ✅
4. 链实例初始状态 → pending → running ✅
5. 全部测试通过 → 190 passed ✅
