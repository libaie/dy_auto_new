<!-- /autoplan restore point: /c/Users/HNXE/.gstack/projects/dy_auto/feature-video-review-fixes-autoplan-restore-20260517-225138.md -->

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

---

## /autoplan Review Report

**Review date:** 2026-05-17
**Reviewer:** autoplan (Claude, Codex unavailable)
**Phases run:** CEO (premises), Eng (architecture + code)
**Phases skipped:** Design (single Vue component, follows existing patterns), DX (internal admin API)

### Premise Gate

| # | Premise | Verdict |
|---|---------|---------|
| P1 | Channels immutable after creation | **Confirmed** — `update_channel_status` only |
| P2 | ChannelItems locked (account/device/keyword) | **Confirmed** — `update_item_status` only |
| P3 | Edit only active/paused channels | **Confirmed** — reasonable constraint |
| P4 | Edit only pending/assigned items | **Confirmed** — avoids data inconsistency |
| P5 | Edit affects only future items | **REVISED** — user chose optional sync to pending/assigned items |

### Engineering Findings

#### P0 — Missing `sync_to_items` on channel edit (from premise gate)

Channel edit form needs a checkbox: "同步应用到所有待处理和执行中的子项". When checked:
- If `account_id` changes → update all pending/assigned items to new account
- If `group_id` changes + round_robin → redistribute accounts for pending/assigned items

**Fix:** Add `sync_to_items: bool = False` to `ChannelEditRequest`, implement sync in `edit_channel()`.

#### P1 — `edit_item()` missing group membership check

[channel_service.py:546](server/app/services/channel_service.py#L546) — When changing an item's `account_id`, validates account exists and is active, but does NOT verify the account belongs to the parent channel's group. Could assign items to accounts outside the channel's group.

**Fix:** In `edit_item()`, look up the parent channel's `group_id` and validate `AccountGroupMember` membership.

#### P2 — `editableAccounts` computed uses non-existent `group_ids` field

[ChannelDetail.vue](web/src/components/ChannelDetail.vue) — The computed `editableAccounts` filters by `a.group_ids` but the accounts API (`_account_to_dict`) doesn't return this field. Filter is silently a no-op.

**Fix:** Either fetch group members via `listMembers(groupId)` API, or add `group_ids` to the accounts endpoint response.

#### P3 — Channel edit: no-op PUT when all fields empty

Sending `PUT /api/channels/{id}` with `{}` body executes a DB commit that changes nothing. Harmless but wastes a write.

**Fix (low priority):** Return 400 if no fields provided, or skip commit.

### Architecture Assessment

```
PUT /api/channels/items/batch ──► batch_edit_items()
PUT /api/channels/items/{id}  ──► edit_item()
PUT /api/channels/{id}        ──► edit_channel()
                                      │
                                      ├── validates group exists
                                      ├── validates account ∈ group
                                      ├── validates device exists
                                      └── commit
```

- Route ordering correct (`/items/*` before `/{channel_id}`)
- FK validation follows existing patterns
- Auth scoping (`user_id`) consistent with rest of channels.py
- No optimistic locking (acceptable for internal admin tool)
- No new dependencies or DB migrations required

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale |
|---|-------|----------|---------------|-----------|-----------|
| 1 | CEO | Accept P1-P4 premises | Mechanical | P6 | Verified against code — premises are factual |
| 2 | CEO | Revise P5 (sync to items) | Taste | P1 | User chose optional sync over "future only" |
| 3 | Eng | Route ordering /items/* before /{id} | Mechanical | P5 | FastAPI matches first-registered; must be explicit |
| 4 | Eng | No optimistic locking | Mechanical | P3 | Internal admin tool; conflict probability negligible |
| 5 | Eng | Flag P1 group membership gap | Mechanical | P1 | Data integrity — items must stay within channel's group |
| 6 | Eng | Flag P2 editableAccounts bug | Mechanical | P1 | UI shows incorrect account list; completeness |

### Test Plan (minimal)

| Codepath | Test type | Status |
|----------|-----------|--------|
| PUT /channels/{id} with valid fields | Integration | **Missing** |
| PUT /channels/{id} on completed channel → 400 | Integration | **Missing** |
| PUT /channels/{id} with invalid group → 400 | Integration | **Missing** |
| PUT /channels/items/{id} with new account | Integration | **Missing** |
| PUT /channels/items/batch with mixed statuses | Integration | **Missing** |
| ChannelDetail.vue edit form toggle | E2E | **Missing** |
| ChannelDetail.vue batch select + edit | E2E | **Missing** |

### Scores

- **CEO**: SELECTIVE EXPANSION. Problem well-scoped. One premise revised (sync to items). No scope creep.
- **Design**: Skipped (single Vue component, follows existing DataTable patterns).
- **Eng**: 2 P0s (sync_to_items + group membership), 2 P1s (UI filter bug + no-op PUT). Architecture clean.
- **DX**: Skipped (internal admin API, no developer-facing surface).
