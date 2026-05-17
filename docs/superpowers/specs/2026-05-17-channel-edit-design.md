# Channel Edit Feature — Design Spec

**Date:** 2026-05-17
**Status:** approved

## Problem

Task channels are immutable after creation. Users cannot change account groups, accounts, devices, or params mid-execution. Pending/assigned ChannelItems are also locked — the only option is to cancel the entire channel and recreate.

## Design

### API Layer

**1. PUT /api/channels/{id}** — Edit channel metadata

```json
// Request (all fields optional)
{
  "group_id": "string?",
  "account_mode": "single_account|round_robin?",
  "account_id": "string?",
  "params_template": {},
  "cooldown_seconds": 600
}
// Response: updated channel object
// Constraint: only active/paused channels
```

**2. PUT /api/channel-items/{item_id}** — Edit single item

```json
// Request (all fields optional)
{
  "account_id": "string?",
  "assigned_device_id": "string?",
  "keyword": "string?"
}
// Response: updated item
// Constraint: only pending/assigned items
```

**3. PUT /api/channel-items/batch** — Batch edit items

```json
// Request
{
  "item_ids": ["id1", "id2"],
  "account_id": "string?",
  "assigned_device_id": "string?"
}
// Response: { updated: N, skipped: [...], errors: [...] }
// Constraint: same as single item, failures don't block successes
```

**Validation rules:**
- `group_id`: must exist in account_groups
- `account_id`: must exist in accounts. For channel edit, must belong to selected group
- `assigned_device_id`: must exist in devices

### Frontend: ChannelDetail.vue

```
ChannelDetail
├── Channel Info Card [+ Edit button → inline form]
│   └── group / account_mode / account / params / cooldown
├── Keyword Manager (existing)
└── Task List (enhanced)
    ├── Checkbox column (pending/assigned only, completed/failed disabled)
    ├── Row "Edit" action button
    ├── Bottom toolbar: "Batch Edit" / "N selected"
    └── Edit Dialog: account / device / keyword fields (all optional)
```

**Interaction rules:**
- Channel edit form: toggled by "Edit" button, save/cancel
- Channel edit only affects future items; existing items unchanged
- Item checkboxes: enabled for pending/assigned, disabled for completed/failed
- Item edit dialog: pre-filled with current values, blank fields = keep current
- Batch toolbar: appears when ≥1 item selected
- Channel edit available for active/paused status only

### Implementation Scope

| Layer | Files |
|-------|-------|
| Server | `routers/channels.py` — 3 new endpoints |
| Server | `services/channel_service.py` — edit_channel, edit_item, batch_edit_items |
| Server | `models.py` — ChannelEditRequest, ChannelItemEditRequest, BatchEditRequest |
| Web | `api/channels.js` — updateChannel, updateChannelItem, batchUpdateItems |
| Web | `components/ChannelDetail.vue` — edit form, checkbox, dialog, toolbar |
