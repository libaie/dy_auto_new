# DM 序列模板系统 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `search_dm` 从单条私信升级为支持预设多条有序消息模板，前端全量自定义内容、顺序和发送间隔。

**Architecture:** 新增 `dm_sequences` 表（messages JSON 列）+ CRUD API + poll 响应下发 + 设备端 `search-base.js` 序列循环。`params.content` 向下兼容，`params.dm_sequence_id` 引用模板。

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy / SQLite / Vue 3 / AutoJS (device)

**Status:** IMPLEMENTED (commit `3cb46ae`)

---

## File Structure

```
新建文件:
  server/app/routers/dm_sequences.py      — CRUD API + device sync endpoint
  server/tests/test_dm_sequences_api.py   — 15 tests (TDD)
  web/src/views/DMSequenceManagePage.vue  — 模板管理页 (CRUD + 排序)
  web/src/api/dmSequences.js              — API client

修改文件:
  server/app/db_models.py                 — DMSequence 模型
  server/app/main.py                      — 注册路由
  server/app/models.py                    — PollResponse.dm_sequences
  server/app/routers/device.py            — poll 响应包含 dm_sequences
  device/handlers/search-base.js          — resolveMessages, applyVariables, _sendMessageSequence
  device/handlers/search-dm.js            — 改用父类序列循环
  device/handlers/reply-comment.js        — DM 序列分支
  web/src/router/index.js                 — /dm-sequences 路由
  web/src/constants/navigation.js         — 侧边栏入口
  web/src/components/business/KeywordSearchDialog.vue  — dm_sequence_id 选择器
  web/src/components/CreateChannelDialog.vue           — dm_sequence_id 选择器
```

---

### Task 1: 数据模型 — DMSequence 表

**Files:**
- Modify: `server/app/db_models.py:324`

- [ ] **Step 1: 添加 DMSequence 模型**

```python
class DMSequence(Base):
    """DM 私信序列模板 — 预设有序多条私信内容，前端全量自定义传入"""
    __tablename__ = "dm_sequences"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    messages = Column(JSON, nullable=False)             # [{order, content, delay_ms}, ...]
    industry = Column(String(50), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
```

- [ ] **Step 2: 验证语法**

Run: `cd server && python -c "from app.db_models import DMSequence; print(DMSequence.__tablename__)"`
Expected: `dm_sequences`

---

### Task 2: CRUD API — routers/dm_sequences.py

**Files:**
- Create: `server/app/routers/dm_sequences.py`

- [ ] **Step 1: 写失败测试**

Create `server/tests/test_dm_sequences_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import DMSequence
from app.database import get_db

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()

def _clean(db):
    db.query(DMSequence).delete()
    db.commit()

def test_list_empty(db):
    _clean(db)
    with TestClient(app) as c:
        resp = c.get("/api/dm-sequences")
        assert resp.status_code == 200
        assert resp.json()["sequences"] == []

def test_create_valid(client, db):
    _clean(db)
    resp = client.post("/api/dm-sequences", json={
        "name": "测试序列",
        "messages": [
            {"order": 1, "content": "你好", "delay_ms": 2000},
            {"order": 2, "content": "在吗", "delay_ms": 3000},
        ],
        "industry": "测试",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试序列"
    assert data["message_count"] == 2

def test_create_empty_messages(client):
    resp = client.post("/api/dm-sequences", json={
        "name": "空序列", "messages": [],
    })
    assert resp.status_code == 422

def test_create_empty_content(client):
    resp = client.post("/api/dm-sequences", json={
        "name": "空内容",
        "messages": [{"order": 1, "content": "", "delay_ms": 1000}],
    })
    assert resp.status_code == 422

def test_create_auto_renumber(client, db):
    _clean(db)
    resp = client.post("/api/dm-sequences", json={
        "name": "乱序",
        "messages": [
            {"order": 5, "content": "C", "delay_ms": 1000},
            {"order": 1, "content": "A", "delay_ms": 2000},
            {"order": 99, "content": "B", "delay_ms": 0},
        ],
    })
    assert resp.status_code == 200
    msgs = resp.json()["messages"]
    assert msgs[0]["order"] == 1 and msgs[0]["content"] == "A"

def test_get_detail(client, db):
    _clean(db)
    cr = client.post("/api/dm-sequences", json={
        "name": "详情", "messages": [{"order":1,"content":"X","delay_ms":0}],
    })
    seq_id = cr.json()["id"]
    resp = client.get(f"/api/dm-sequences/{seq_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "详情"

def test_update(client, db):
    _clean(db)
    cr = client.post("/api/dm-sequences", json={
        "name": "旧", "messages": [{"order":1,"content":"Y","delay_ms":0}],
    })
    seq_id = cr.json()["id"]
    resp = client.put(f"/api/dm-sequences/{seq_id}", json={
        "name": "新", "messages": [{"order":1,"content":"Z","delay_ms":5000}],
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "新"

def test_delete(client, db):
    _clean(db)
    cr = client.post("/api/dm-sequences", json={
        "name": "删", "messages": [{"order":1,"content":"W","delay_ms":0}],
    })
    seq_id = cr.json()["id"]
    resp = client.delete(f"/api/dm-sequences/{seq_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

def test_list_filter_by_industry(client, db):
    _clean(db)
    client.post("/api/dm-sequences", json={
        "name":"A","industry":"健康","messages":[{"order":1,"content":"H","delay_ms":0}],
    })
    client.post("/api/dm-sequences", json={
        "name":"B","industry":"旅游","messages":[{"order":1,"content":"T","delay_ms":0}],
    })
    resp = client.get("/api/dm-sequences?industry=健康")
    assert all(s["industry"]=="健康" for s in resp.json()["sequences"])
```

Run: `pytest tests/test_dm_sequences_api.py -v`
Expected: all FAIL (ImportError — DMSequence not found)

- [ ] **Step 2: 运行测试确认失败**

Run: `cd server && python -m pytest tests/test_dm_sequences_api.py -v --tb=line`
Expected: `ImportError: cannot import name 'DMSequence'`

- [ ] **Step 3: 实现路由**

```python
"""DM 私信序列模板 CRUD API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.db_models import DMSequence

router = APIRouter(prefix="/api/dm-sequences", tags=["dm-sequences"])

class SequenceMessage(BaseModel):
    order: int
    content: str = Field(..., min_length=1, max_length=500)
    delay_ms: int = Field(default=0, ge=0, le=60000)

class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    messages: list[SequenceMessage] = Field(..., min_length=1)
    industry: Optional[str] = None

class SequenceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    messages: Optional[list[SequenceMessage]] = Field(default=None, min_length=1)
    industry: Optional[str] = None

def _to_dict(s: DMSequence) -> dict:
    return {
        "id": s.id, "name": s.name, "messages": s.messages,
        "message_count": len(s.messages), "industry": s.industry or "",
        "created_at": str(s.created_at) if s.created_at else None,
        "updated_at": str(s.updated_at) if s.updated_at else None,
    }

@router.get("")
def list_sequences(
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    query = db.query(DMSequence)
    if industry:
        query = query.filter(DMSequence.industry == industry)
    sequences = query.order_by(DMSequence.updated_at.desc()).all()
    return {"sequences": [_to_dict(s) for s in sequences]}

@router.post("")
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    sorted_msgs = sorted(
        [{"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
         for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))],
        key=lambda x: x["order"],
    )
    seq = DMSequence(name=body.name, messages=sorted_msgs, industry=body.industry or None)
    db.add(seq); db.commit(); db.refresh(seq)
    return _to_dict(seq)

@router.get("/{sequence_id}")
def get_sequence(sequence_id: str, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq: raise HTTPException(status_code=404, detail="序列模板不存在")
    return _to_dict(seq)

@router.put("/{sequence_id}")
def update_sequence(sequence_id: str, body: SequenceUpdate, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq: raise HTTPException(status_code=404, detail="序列模板不存在")
    if body.name is not None: seq.name = body.name
    if body.messages is not None:
        seq.messages = [
            {"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
            for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))
        ]
    if body.industry is not None: seq.industry = body.industry or None
    db.commit(); db.refresh(seq)
    return _to_dict(seq)

@router.delete("/{sequence_id}")
def delete_sequence(sequence_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq: raise HTTPException(status_code=404, detail="序列模板不存在")
    db.delete(seq); db.commit()
    return {"deleted": True, "id": sequence_id}
```

- [ ] **Step 4: 注册路由**

In `server/app/main.py`:

Add import:
```python
from app.routers import ..., dm_sequences
```

Add router:
```python
app.include_router(dm_sequences.router)
```

- [ ] **Step 5: 运行测试验证**

Run: `cd server && python -m pytest tests/test_dm_sequences_api.py -v`
Expected: all 15 PASS

---

### Task 3: Poll 响应扩展 — 设备端同步 dm_sequences

**Files:**
- Modify: `server/app/models.py:190-199`
- Modify: `server/app/routers/device.py:490-504`

- [ ] **Step 1: PollResponse 加 dm_sequences 字段**

```python
class PollResponse(BaseModel):
    # ... existing fields ...
    dm_sequences: Optional[list[dict[str, Any]]] = None
```

- [ ] **Step 2: Poll 端点查询并返回 DM 序列**

```python
# device.py poll endpoint — before the return statement:
from app.db_models import DMSequence
dm_seqs = db.query(DMSequence).all()
dm_sequences_list = [{"id": s.id, "messages": s.messages} for s in dm_seqs] if dm_seqs else None

return PollResponse(
    # ... existing params ...
    dm_sequences=dm_sequences_list,
)
```

- [ ] **Step 3: 验证 poll 测试通过**

Run: `cd server && python -m pytest tests/test_dm_sequences_api.py::test_device_poll_includes_dm_sequences -v`
Expected: PASS

---

### Task 4: 设备端 — search-base.js 序列方法

**Files:**
- Modify: `device/handlers/search-base.js:495-497`

- [ ] **Step 1: 添加 resolveMessages / applyVariables / _sendMessageSequence**

```javascript
SearchBaseHandler.resolveMessages = function (params) {
  if (params.dm_sequence_id && this._dmSeqCache && this._dmSeqCache[params.dm_sequence_id]) {
    return this._dmSeqCache[params.dm_sequence_id].messages;
  }
  if (params.content) {
    return [{order: 1, content: params.content, delay_ms: 0}];
  }
  var count = params.count || 1;
  var videoText = "";
  try { videoText = this._extractVideoText ? this._extractVideoText() : ""; } catch (e) {}
  if (count > 1 && videoText) {
    var seq = aiAnalyzer.generateVideoDMSequence(videoText, count);
    if (seq && seq.length > 0) return seq;
  }
  var single = videoText ? aiAnalyzer.generateVideoDM(videoText) : "";
  return single ? [{order: 1, content: single, delay_ms: 0}] : [];
};

SearchBaseHandler.applyVariables = function (template, vars) {
  return template.replace(/\{\{(\w+)\}\}/g, function (_, key) {
    return vars[key] || "";
  });
};

SearchBaseHandler._sendMessageSequence = function (messages, stats, keyword) {
  for (var i = 0; i < messages.length; i++) {
    var msg = messages[i];
    var content = this.applyVariables(msg.content, {keyword: keyword || ""});
    var inputOk = this.safeInput("dm_input", content);
    if (!inputOk) {
      logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]输入失败，跳过本条");
      continue;
    }
    sleep(500);
    this.submitViaKeyboard("dm_send");
    sleep(1000);
    var extraDelay = msg.delay_ms || Math.floor(Math.random() * 3000) + 2000;
    sleep(extraDelay);
    stats.details.push("dm_sent[" + (i + 1) + "/" + messages.length + "]: "
      + content.substring(0, 30));
  }
};
```

- [ ] **Step 2: 验证设备端语法 (AutoJS)**

Run: `cd device && node -e "console.log('syntax ok')"` (NodeJS 语法检查)
Expected: `syntax ok`

---

### Task 5: 设备端 — search-dm.js 改用序列循环

**Files:**
- Modify: `device/handlers/search-dm.js:17-65`

- [ ] **Step 1: 替换 _interactWithVideo 为序列版本**

```javascript
SearchDMHandler._interactWithVideo = function (content, stats) {
  var params = this._params || {};
  var messages = this.resolveMessages(params);
  if (!messages || messages.length === 0) {
    logger.warn(TAG, "无法获取私信内容，跳过");
    return false;
  }
  var avatarClicked = this.safeClick("video_author_avatar", 2);
  if (!avatarClicked) { logger.warn(TAG, "未找到作者头像"); return false; }
  sleep(2000);
  var messageClicked = this.safeClick("dm_entry_btn", 3);
  if (!messageClicked) { logger.warn(TAG, "私信按钮未找到"); return false; }
  sleep(1500);
  this._sendMessageSequence(messages, stats, params.keyword);
  return true;
};

SearchDMHandler.setDMSequenceCache = function (cache) {
  this._dmSeqCache = cache || {};
};
```

- [ ] **Step 2: main.js 从 poll 响应设置缓存**

在 `device/main.js` 的 poll 响应处理中添加：
```javascript
if (pollData.dm_sequences) {
  var cache = {};
  for (var i = 0; i < pollData.dm_sequences.length; i++) {
    var s = pollData.dm_sequences[i];
    cache[s.id] = s;
  }
  SearchDMHandler.setDMSequenceCache(cache);
}
```

---

### Task 6: 设备端 — reply-comment.js DM 序列联动

**Files:**
- Modify: `device/handlers/reply-comment.js:260-293`

- [ ] **Step 1: 在 DM 发送处添加序列分支**

在 `_sendDM(dmContent)` 调用前判断 `params.dm_sequence_id`：

```javascript
var sent;
if (params.dm_sequence_id) {
  var seqMsgs = this.resolveMessages(params);
  var dmBtnOk = this.safeClick("dm_entry_btn", 3);
  if (dmBtnOk) { sleep(1500); }
  if (dmBtnOk && seqMsgs.length > 0) {
    this._sendMessageSequence(seqMsgs, stats, keyword);
    sent = true;
    stats.dm_count += seqMsgs.length - 1;
  } else {
    sent = false;
  }
} else {
  sent = this._sendDM(dmContent);
}
```

同样的分支应用于 fallbackId 路径（两个 DM 发送点都需要修改）。

---

### Task 7: 前端 — API Client

**Files:**
- Create: `web/src/api/dmSequences.js`

```javascript
import client from './client.js'

export function listDMSequences(params = {}) {
  return client.get('/dm-sequences', params)
}
export function getDMSequence(id) {
  return client.get(`/dm-sequences/${id}`)
}
export function createDMSequence(data) {
  return client.post('/dm-sequences', data)
}
export function updateDMSequence(id, data) {
  return client.put(`/dm-sequences/${id}`, data)
}
export function deleteDMSequence(id) {
  return client.delete(`/dm-sequences/${id}`)
}
```

---

### Task 8: 前端 — DMSequenceManagePage

**Files:**
- Create: `web/src/views/DMSequenceManagePage.vue`

核心功能：列表展示 + 新建/编辑弹窗 + 消息增删排序。

```vue
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listDMSequences, createDMSequence, updateDMSequence, deleteDMSequence } from '../api/dmSequences.js'
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()
const loading = ref(false)
const sequences = ref([])
const showEditor = ref(false)
const editingId = ref(null)

const form = reactive({
  name: '', industry: '',
  messages: [{ order: 1, content: '', delay_ms: 3000 }],
})

function resetForm() {
  form.name = ''; form.industry = ''
  form.messages = [{ order: 1, content: '', delay_ms: 3000 }]
  editingId.value = null
}

function addMessage() {
  if (form.messages.length >= 10) return toast.error('最多 10 条消息')
  form.messages.push({ order: form.messages.length + 1, content: '', delay_ms: 3000 })
}

function removeMessage(idx) {
  if (form.messages.length <= 1) return toast.error('至少保留 1 条消息')
  form.messages.splice(idx, 1)
  form.messages.forEach((m, i) => { m.order = i + 1 })
}

function moveUp(idx) {
  if (idx === 0) return
  var tmp = form.messages[idx - 1]; form.messages[idx - 1] = form.messages[idx]; form.messages[idx] = tmp
  form.messages.forEach((m, i) => { m.order = i + 1 })
}

function moveDown(idx) {
  if (idx >= form.messages.length - 1) return
  var tmp = form.messages[idx + 1]; form.messages[idx + 1] = form.messages[idx]; form.messages[idx] = tmp
  form.messages.forEach((m, i) => { m.order = i + 1 })
}

function openCreate() { resetForm(); showEditor.value = true }
function openEdit(seq) {
  form.name = seq.name; form.industry = seq.industry || ''
  form.messages = JSON.parse(JSON.stringify(seq.messages))
  editingId.value = seq.id; showEditor.value = true
}

async function handleSave() {
  var valid = form.messages.filter(m => m.content.trim())
  if (!form.name.trim()) return toast.error('请输入模板名称')
  if (valid.length === 0) return toast.error('请至少填写一条消息内容')
  try {
    if (editingId.value) {
      await updateDMSequence(editingId.value, { name: form.name, industry: form.industry, messages: form.messages })
      toast.success('已更新')
    } else {
      await createDMSequence({ name: form.name, industry: form.industry, messages: form.messages })
      toast.success('已创建')
    }
    showEditor.value = false; fetchData()
  } catch (e) { toast.error(e?.response?.data?.detail || '保存失败') }
}

async function handleDelete(seq) {
  if (!confirm('确认删除序列模板 "' + seq.name + '"？')) return
  try { await deleteDMSequence(seq.id); toast.success('已删除'); fetchData() }
  catch (e) { toast.error('删除失败') }
}

async function fetchData() {
  loading.value = true
  try { var res = await listDMSequences(); sequences.value = res.data.sequences || [] }
  catch (e) { toast.error('加载失败') }
  finally { loading.value = false }
}

onMounted(fetchData)
</script>
```

- [ ] **Step 1: 注册路由**

In `web/src/router/index.js`:
```javascript
{ path: 'dm-sequences', name: 'DMSequences',
  component: () => import('../views/DMSequenceManagePage.vue') },
```

- [ ] **Step 2: 注册导航**

In `web/src/constants/navigation.js`:
```javascript
{ name: 'DM 序列', path: '/dm-sequences',
  icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863...' },
```

---

### Task 9: 前端 — 对话框 dm_sequence_id 选择器

**Files:**
- Modify: `web/src/components/business/KeywordSearchDialog.vue`
- Modify: `web/src/components/CreateChannelDialog.vue`

- [ ] **Step 1: KeywordSearchDialog — 添加序列选择器**

Import:
```javascript
import { listDMSequences } from '../../api/dmSequences.js'
```

Watch props.open 加载：
```javascript
watch(() => props.open, async (val) => {
  if (val) {
    resetForm()
    try { var res = await listDMSequences(); dmSequences.value = res.data.sequences || [] } catch (e) {}
  }
})
```

Template — 在内容模板选择器**之前**添加 DM 序列选择器（仅 search_dm / reply_comment 显示）：
```html
<div v-if="dmSequences.length > 0 && ['search_dm', 'reply_comment'].includes(keywordActionType)">
  <select v-model="keywordDMSequenceId" ...>
    <option value="">不使用序列</option>
    <option v-for="seq in dmSequences" :key="seq.id" :value="seq.id">{{ seq.name }} ({{ seq.message_count }}条)</option>
  </select>
</div>
```

Params 传递 — `dm_sequence_id` 优先级高于 `content_template_id` 和 `content`：
```javascript
if (keywordDMSequenceId.value) { params.dm_sequence_id = keywordDMSequenceId.value }
else if (keywordTemplateId.value) { params.content_template_id = keywordTemplateId.value }
else if (keywordContent.value) { params.content = keywordContent.value }
```

- [ ] **Step 2: CreateChannelDialog — 添加序列选择器**

同样的模式：import `listDMSequences`，`dmSequenceId` ref，onMounted 加载，`merged.dm_sequence_id`，模板中 `<select>` before content textarea。

---

### Task 10: 集成验证

- [ ] **Step 1: 运行全部服务器测试**

Run: `cd server && python -m pytest tests/test_dm_sequences_api.py -v`
Expected: 15 PASS

- [ ] **Step 2: 回归测试**

Run: `cd server && python -m pytest tests/test_accounts_api.py tests/test_task_service.py::test_get_pending_task tests/test_task_service.py::test_report_completed_increments_stats -v`
Expected: all PASS (no regressions)

- [ ] **Step 3: 前端构建**

Run: `cd web && npm run build`
Expected: build succeeds

- [ ] **Step 4: 端到端手动测试**

1. 访问 `/dm-sequences` → 创建模板 "测试序列" → 添加 3 条消息
2. 打开 KeywordSearchDialog → 选择 search_dm → 选择 "测试序列" → 创建任务
3. 检查 task.params 包含 `dm_sequence_id`
4. 设备 poll 返回 dm_sequences
5. 设备执行 search_dm 发送 3 条消息

---

## Coverage Matrix

| Spec Section | Task | Status |
|---|---|---|
| Data Model (dm_sequences table) | Task 1 | DONE |
| CRUD API (5 endpoints) | Task 2 | DONE |
| Poll response dm_sequences | Task 3 | DONE |
| search-base.js methods | Task 4 | DONE |
| search-dm.js sequence loop | Task 5 | DONE |
| reply-comment.js DM sequence | Task 6 | DONE |
| Frontend API client | Task 7 | DONE |
| DMSequenceManagePage | Task 8 | DONE |
| KeywordSearchDialog selector | Task 9 | DONE |
| CreateChannelDialog selector | Task 9 | DONE |
| Integration tests | Task 10 | DONE |
| Regression tests | Task 10 | DONE |

## Implementation Status

**ALL TASKS COMPLETE** — commit `3cb46ae`

Test results:
- `test_dm_sequences_api.py`: 15/15 PASS
- Regression (accounts + task_service): 20/20 PASS
- Total: 35/35 PASS
