# Data Center Export Feature

> Add Excel (.xlsx) export to the Data Center page, per-tab, respecting active filters.

## Motivation

Data Center currently displays collected comments, user profiles, and conversation data with
pagination (20/page). Users need to export full filtered datasets for offline analysis, reporting,
and CRM import.

## Design

### Interaction

One "导出 Excel" button per tab, placed in the filter bar. On click:

1. Frontend collects the active tab + all filter values
2. Calls `GET /api/data/export/{type}?{filters}`
3. Backend queries ALL matching rows (no pagination), generates .xlsx in memory
4. Returns `StreamingResponse` with `Content-Disposition: attachment`
5. Browser triggers file download as `{type}_{YYYYMMDD}.xlsx`

### Backend: Endpoints

Three new endpoints in `server/app/routers/data.py`:

| Endpoint | Source Table | Key Filters |
|----------|-------------|-------------|
| `GET /api/data/export/comments` | `collected_comments` | keyword, account_id, task_id, search |
| `GET /api/data/export/users` | `collected_users` | keyword, task_id, search |
| `GET /api/data/export/conversations` | `conversations` | account_id, stage, status, task_id, search |

- Reuse existing filter logic from `listComments`/`listUsers`/`listConversations`
- No pagination — query all matching rows
- Use `openpyxl.Workbook` to build .xlsx in a `BytesIO` buffer
- Return via `StreamingResponse` with media type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

### Backend: Column Definitions

**Comments sheet:**

| Column | Field |
|--------|-------|
| 昵称 | nickname |
| 内容 | content |
| AI回复 | ai_reply |
| 关键词 | keyword |
| 点赞数 | like_count |
| 回复数 | reply_count |
| IP属地 | location |
| 是否作者 | is_author |
| 采集时间 | created_at |

**Users sheet:**

| Column | Field |
|--------|-------|
| 昵称 | nickname |
| 抖音号 | douyin_id |
| 获赞 | likes_count |
| 关注 | follow_count |
| 粉丝 | fans_count |
| 作品 | works_count |
| 性别 | gender |
| 年龄 | age |
| IP属地 | ip_location |
| 私密账号 | is_private |
| 采集时间 | created_at |

**Conversations sheet:**

| Column | Field |
|--------|-------|
| 对方昵称 | recipient_nickname |
| 抖音号 | recipient_douyin_id |
| 阶段 | current_stage |
| 最新消息 | last_dm_content |
| 消息总数 | total_dm_count |
| 最后发送时间 | last_dm_at |

### Frontend

- File: `web/src/views/DataCenterPage.vue`
- Add button in filter bar (right side)
- New function `handleExport()`:
  1. Build params from current filter refs
  2. `axios.get(`/api/data/export/${activeTab.value}`, { params, responseType: 'blob' })`
  3. `URL.createObjectURL(blob)` → `<a download>` → click → revoke
  4. Loading state on button during export

### Dependency

- `openpyxl` — add to `server/requirements.txt`

## Edge Cases

- Empty result set: still return a valid .xlsx with headers only
- Large datasets (>10K rows): use `openpyxl` write-only mode (`write_only=True`) to keep memory bounded
- Auth: all export endpoints require `verify_admin_token`
