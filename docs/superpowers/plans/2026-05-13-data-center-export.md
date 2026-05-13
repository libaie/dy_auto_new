# Data Center Export Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-tab Excel (.xlsx) export to Data Center page, respecting active filters, downloading full filtered datasets.

**Architecture:** Three new `GET /api/data/export/{type}` endpoints in the existing data.py router, reusing the same filter logic as `listComments`/`listUsers`/`listConversations` but without pagination. Frontend adds a single button per tab that triggers an axios blob download. `openpyxl` generates the workbook in memory.

**Tech Stack:** Python 3.12+ / FastAPI / openpyxl / Vue 3 / axios

---

### Task 1: Add openpyxl dependency

**Files:**
- Modify: `server/requirements.txt`

- [ ] **Step 1: Add openpyxl to requirements.txt**

```diff
+ openpyxl>=3.1
```

- [ ] **Step 2: Install dependency**

Run: `cd server && pip install openpyxl`
Expected: Successfully installed openpyxl

---

### Task 2: Build export endpoints in data.py

**Files:**
- Modify: `server/app/routers/data.py`

- [ ] **Step 1: Add openpyxl import and helper function**

At the top of data.py, add:

```python
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from fastapi.responses import StreamingResponse

HEADER_FONT = Font(bold=True, size=11)
HEADER_FILL = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")


def _build_xlsx(headers: list[str], rows: list[list]) -> io.BytesIO:
    """Build an .xlsx in memory and return the BytesIO buffer."""
    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.close()
    buf = io.BytesIO()
    # write_only mode: we must write to a temp buffer and re-read
    wb.save(buf)
    buf.seek(0)
    return buf


def _stream_xlsx(filename: str, buf: io.BytesIO) -> StreamingResponse:
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 2: Add export/comments endpoint**

After the existing `list_comments` function, add:

```python
@router.get("/export/comments")
def export_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    query = db.query(CollectedComment)
    if keyword:
        query = query.filter(CollectedComment.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedComment.device_id.in_(device_ids))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            CollectedComment.nickname.like(pattern),
            CollectedComment.content.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedComment.task_id == task_id)
    rows = query.order_by(CollectedComment.created_at.desc()).all()

    headers = ["昵称", "内容", "AI回复", "关键词", "点赞数", "回复数", "IP属地", "是否作者", "采集时间"]
    data = [[
        r.nickname, r.content, r.ai_reply or "", r.keyword or "",
        r.like_count or "", r.reply_count or "", r.location or "",
        "是" if r.is_author else "否", str(r.created_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"comments_{bj_now().strftime('%Y%m%d')}.xlsx", buf)
```

- [ ] **Step 3: Add export/users endpoint**

```python
@router.get("/export/users")
def export_users(
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    query = db.query(CollectedUser)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedUser.device_id.in_(device_ids))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            CollectedUser.nickname.like(pattern),
            CollectedUser.douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedUser.task_id == task_id)
    rows = query.order_by(CollectedUser.created_at.desc()).all()

    headers = ["昵称", "抖音号", "获赞", "关注", "粉丝", "作品", "性别", "年龄", "IP属地", "私密账号", "采集时间"]
    data = [[
        r.nickname, r.douyin_id or "",
        r.likes_count or "", r.follow_count or "", r.fans_count or "", r.works_count or "",
        r.gender or "", r.age or "", r.ip_location or "", r.is_private or "",
        str(r.created_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"users_{bj_now().strftime('%Y%m%d')}.xlsx", buf)
```

- [ ] **Step 4: Add export/conversations endpoint**

```python
@router.get("/export/conversations")
def export_conversations(
    account_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    query = db.query(Conversation)
    if account_id:
        query = query.filter(Conversation.account_id == account_id)
    if stage:
        query = query.filter(Conversation.current_stage == stage)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Conversation.recipient_nickname.like(pattern),
            Conversation.last_dm_content.like(pattern),
            Conversation.recipient_douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(Conversation.task_id == task_id)
    rows = query.order_by(Conversation.last_dm_at.desc().nullslast()).all()

    stage_map = {"qualifying": "触达", "nurturing": "培育", "converting": "转化", "follow_up": "跟进"}

    headers = ["对方昵称", "抖音号", "阶段", "最新消息", "消息总数", "最后发送时间"]
    data = [[
        r.recipient_nickname, r.recipient_douyin_id or "",
        stage_map.get(r.current_stage, r.current_stage or ""),
        r.last_dm_content or "", str(r.total_dm_count or 0),
        str(r.last_dm_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"conversations_{bj_now().strftime('%Y%m%d')}.xlsx", buf)
```

- [ ] **Step 5: Verify endpoints work**

Run: start server → `curl -s -o /tmp/test.xlsx -w "HTTP %{http_code}" "http://localhost:8000/api/data/export/comments" -H "Authorization: Bearer <token>"`
Expected: HTTP 200, file is valid .xlsx

---

### Task 3: Add export button to frontend

**Files:**
- Modify: `web/src/views/DataCenterPage.vue`

- [ ] **Step 1: Add handleExport function to script**

In `<script setup>`, add after `handleSearch`:

```javascript
const exporting = ref(false)

async function handleExport() {
  exporting.value = true
  try {
    const params = {}
    if (filterTaskId.value) params.task_id = filterTaskId.value
    if (searchQuery.value) params.search = searchQuery.value

    if (activeTab.value === 'comments') {
      if (filterKeyword.value) params.keyword = filterKeyword.value
      if (filterAccountId.value) params.account_id = filterAccountId.value
    } else if (activeTab.value === 'users') {
      if (filterAccountId.value) params.account_id = filterAccountId.value
    } else if (activeTab.value === 'conversations') {
      if (filterAccountId.value) params.account_id = filterAccountId.value
      if (filterStage.value) params.stage = filterStage.value
    }

    const token = localStorage.getItem('token') || ''
    const resp = await fetch(`/api/data/export/${activeTab.value}?${new URLSearchParams(params)}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!resp.ok) throw new Error('Export failed')
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${activeTab.value}_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('导出完成')
  } catch (e) {
    toast.error('导出失败: ' + (e.message || '未知错误'))
  } finally { exporting.value = false }
}
```

- [ ] **Step 2: Add export button to template filter bar**

In `<template>`, add after the `filterTaskId` span (line 167):

```html
<button @click="handleExport" :disabled="exporting"
  class="ml-auto px-4 py-1.5 text-sm rounded-lg border transition cursor-pointer"
  :class="exporting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-sky-500/10 hover:border-sky-500/30'"
  style="border-color: var(--border-default); color: var(--accent-400);">
  {{ exporting ? '导出中...' : '导出 Excel' }}
</button>
```

---

### Task 4: Restart and verify

- [ ] **Step 1: Start backend and verify health**

```bash
taskkill //F //IM python.exe 2>/dev/null
cd D:/devWorkspace/jsProjects/dy_auto/server && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 5 && curl -s http://localhost:8000/health
```
Expected: `{"status":"ok","version":"0.3.0"}`

- [ ] **Step 2: Start frontend and verify**

```bash
taskkill //F //IM node.exe 2>/dev/null
cd D:/devWorkspace/jsProjects/dy_auto/web && npx vite --host 0.0.0.0 --port 5173 &
sleep 8 && curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:5173
```
Expected: HTTP 200, no compilation errors

- [ ] **Step 3: Manual verification**

Open `http://localhost:5173/data-center` → click "导出 Excel" → verify .xlsx downloads and opens correctly with filtered data.
