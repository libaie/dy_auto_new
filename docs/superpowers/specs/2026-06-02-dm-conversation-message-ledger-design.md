<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260602-154049.md -->

# 私信会话消息流水重设计

## 背景

当前数据中心的“私信会话”只展示 `conversations.last_dm_content`，后端会话模型也只保存最后一条私信摘要、最近发送时间和总条数。对于使用 DM 序列一次发送多条私信的任务，前端无法展示第 1/2/3 条完整内容，用户只能看到最后一条或看不到完整发送过程。

本设计将私信会话从“最后一条摘要”升级为“会话摘要 + 消息流水”。第一版目标是确保以后新发送的多条私信逐条落库、逐条展示；旧数据尽量补摘要，但不伪造无法恢复的历史消息。

## 目标

- 新发送的每条私信都有独立消息记录，支持展示内容、顺序、发送时间、状态和来源。
- 数据中心保留现有会话卡片列表，点击卡片打开详情抽屉查看完整消息流水。
- `conversations` 继续承担列表摘要、筛选和排序职责。
- 历史会话能补则补，无法恢复完整流水时明确标记为历史摘要。
- 第一版不做人工备注、跟进编辑、复杂 CRM 工作台和跨事件统一日志。

## 数据模型

`conversations` 保持为会话摘要表，继续保留：

- 收件人昵称和抖音号
- 账号、设备、任务、阶段、状态
- `last_dm_content`
- `last_dm_at`
- `total_dm_count`
- `created_at`
- `updated_at`

新增 `conversation_messages` 表：

- `id`: 主键
- `conversation_id`: 关联 `conversations.id`
- `task_id`: 关联任务；新发送消息必须填写，历史补齐允许为空
- `account_id`: 发送账号
- `device_id`: 执行设备
- `dm_sequence_id`: 使用的 DM 序列模板，允许为空
- `message_order`: 序列中的第几条
- `message_key`: 幂等键，新消息格式为 `task_id:dm_sequence_id_or_single:message_order`，历史摘要格式为 `history:conversation_id`
- `content`: 实际发送内容
- `status`: `sent` 或 `failed`
- `sent_at`: 发送时间
- `error_message`: 失败原因，允许为空
- `created_at`: 记录创建时间

幂等约束使用 `(conversation_id, message_key)`。不要用 `(conversation_id, task_id, message_order)` 作为唯一键，因为 `task_id` 在历史补齐中允许为空，而 SQL 唯一约束通常不会把 `NULL` 当作相等值处理。

`conversations.total_dm_count` 只统计成功发送的消息。失败消息保留在 `conversation_messages.status=failed` 中，用于详情展示和排查，但不增加成功发送总数。

## 后端接口

新增 `GET /api/data/conversations/{id}`。

响应结构：

```json
{
  "conversation": {},
  "messages": [],
  "history_incomplete": false
}
```

行为：

- `conversation` 返回会话摘要。
- `messages` 按 `message_order`、`sent_at` 排序。
- 如果该会话没有消息流水但有 `last_dm_content`，返回一条历史摘要消息，并设置 `history_incomplete=true`。
- 非管理员继续遵守现有用户权限过滤，不允许读取无权任务产生的会话。

扩展 `POST /api/device/dm-send-report`。

请求体增加：

- `task_id`
- `message_order`
- `dm_sequence_id`
- `message_key`
- `status`
- `error_message`

写入行为：

- 每次上报插入或更新一条 `conversation_messages`。
- 同步更新 `conversations.last_dm_content`、`last_dm_at`、`total_dm_count`、`current_stage`、`intent`。
- 如果 `message_key` 未传，后端按 `task_id:dm_sequence_id_or_single:message_order` 生成。
- 重复上报同一 `(conversation_id, message_key)` 时更新已有记录，不重复增加展示条目。
- `status=sent` 时更新 `last_dm_content` 和 `last_dm_at`；`status=failed` 时只记录失败流水，不覆盖最近成功消息。

## 设备端流程

设备端当前存在两类路径，第一版必须同时覆盖：

- `reply_comment` 路径已经会调用 `claimDMRecipient`，但 DM 序列成功后只调用一次 `dm-send-report`，并把多条内容拼成一条字符串。这里要改成逐条上报。
- `search_dm` 路径当前只发送私信并增加统计，没有创建会话，也没有调用 `dm-send-report`。这里要补齐收件人身份提取、会话 claim 和逐条 report，否则搜索私信任务仍然不会进入“私信会话”。

`_sendMessageSequence` 不能只返回 `sentCount`。它需要返回每条消息的发送结果，例如：

```json
[
  {"order": 1, "content": "实际内容", "status": "sent", "sent_at": "..."},
  {"order": 2, "content": "实际内容", "status": "failed", "error_message": "发送按钮未找到"}
]
```

调用方负责把这些结果逐条上报。

每条上报应包含：

- 会话 ID
- 任务 ID
- 账号 ID
- 设备 ID
- DM 序列 ID
- 幂等键
- 当前消息序号
- 实际发送内容
- 成功或失败状态
- 失败原因

如果某条发送失败，设备端仍可上报失败记录，后端将其展示在流水中，避免用户误以为三条都发送成功。

`search_dm` 的收件人是视频作者。实现阶段需要从作者主页或已采集的用户信息中提取稳定的 `recipient_douyin_id`；如果拿不到，才允许用昵称和主页信息生成 fallback ID，并在详情中标记为 fallback，便于后续排查重复会话。

## 前端体验

数据中心的“私信会话”保留卡片列表。

卡片展示：

- 收件人昵称和抖音号
- 阶段标签
- 状态标签
- 最近一条私信摘要
- 总消息数
- 失败消息数
- 最近发送时间
- 历史摘要提示

点击卡片打开右侧详情抽屉。

详情抽屉展示：

- 顶部：收件人、账号、阶段、状态、最近发送时间。
- 中部：消息流水，按第 1/2/3 条排列。
- 每条消息展示：序号、内容、发送时间、状态、DM 序列来源。
- 任务 ID、设备 ID、账号 ID 使用折叠信息展示，避免卡片过重。
- 详情接口失败时显示错误，不清空当前列表。

导出会话时，第一版在会话导出中增加“消息明细”列，用多行文本展示消息流水。后续如果需要对账，再单独增加消息明细导出接口。

## 历史数据策略

历史数据按“尽量补齐但不伪造”处理。

- 对没有任何 `conversation_messages` 但有 `last_dm_content` 的会话，生成一条历史摘要消息。
- 该消息使用 `message_order=1`，内容来自 `last_dm_content`。
- 详情接口返回 `history_incomplete=true`。
- 前端显示“历史会话，仅保留最后一条摘要”。

旧会话中无法恢复的第 1/2/3 条不会凭空生成。

## 测试计划

后端测试：

- `dm-send-report` 每次上报插入一条 `conversation_messages`。
- 同一 `(conversation_id, message_key)` 重复上报不会重复插入。
- `status=failed` 不覆盖 `conversations.last_dm_content`，也不增加成功发送总数。
- 会话详情接口返回 `conversation`、`messages` 和 `history_incomplete`。
- 历史会话只有 `last_dm_content` 时返回一条摘要消息，并标记 `history_incomplete=true`。
- 无权用户不能读取其他用户任务产生的会话详情。

前端测试：

- 会话卡片点击后打开详情抽屉。
- 三条私信完整展示，顺序正确。
- 历史不完整会话显示历史摘要提示。
- 详情接口失败时显示错误并保留列表内容。

设备端测试：

- DM 序列发送三条消息时产生三次上报。
- 单条发送失败时上报 `failed` 和错误原因。
- 重试同一条消息不会导致前端重复展示。
- `search_dm` 路径会创建或复用会话，并逐条上报消息流水。
- `reply_comment` 路径不再把多条 DM 序列拼成一条 `content` 上报。

## 风险与约束

- 设备端可能需要从“序列结束上报一次”改为“每条消息上报一次”，这是本设计能否展示完整三条私信的关键。
- `search_dm` 当前没有会话上报路径，如果只改后端和前端，搜索私信仍不会出现在会话详情里。
- 历史数据无法完整恢复，必须在 UI 上明确标注。
- 幂等约束需要覆盖设备重试，否则会出现重复消息。使用 nullable `task_id` 参与唯一约束不可靠，应使用稳定的 `message_key`。
- 第一版不引入统一事件日志，避免扩大到评论、关注、采集等其他动作。

## 验收标准

- 新的三条私信序列发送后，数据中心会话详情能看到三条内容、顺序和发送时间。
- `search_dm` 和 `reply_comment` 两条设备路径都能产生消息流水。
- 会话卡片仍能正常按阶段、状态、账号筛选。
- 历史会话不会被误展示成完整流水。
- 重复上报不会造成重复消息。
- 详情接口和导出不会破坏现有会话列表 API。

## GSTACK REVIEW REPORT

### Intake

- Plan file: `docs/superpowers/specs/2026-06-02-dm-conversation-message-ledger-design.md`
- Restore point: `C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260602-154049.md`
- Branch: `feature/video-review-fixes`
- Base branch: `main` fallback; no `origin` or local `main` ref available for full base diff.
- UI scope: yes. The plan changes Data Center conversation cards and a right-side detail drawer.
- DX scope: yes. The plan changes REST APIs, device reporting payloads, and export behavior.
- External Codex voice: attempted with read-only sandbox; timed out after 10 minutes and produced no usable findings.

### CEO Review

Verdict: keep the scope. The user-facing failure is not just a missing display state; the system currently lacks a durable record for each sent DM. The independent message ledger is the correct product shape because it makes “sent three messages” auditable instead of inferred from a final string.

Scope expansion accepted: include both `reply_comment` and `search_dm` device paths. Code inspection showed `reply_comment` reports sequence messages once as a joined string, while `search_dm` sends DMs without conversation claim/report. If the plan only changes the data model and frontend, the original complaint can still reproduce from `search_dm`.

Scope held: do not add CRM editing, manual notes, unified event logs, or full follow-up workflows in this slice.

### Design Review

Initial design score: 7/10. The card + drawer model is appropriate for Data Center because the list stays scan-friendly and the complete message sequence moves into a focused detail view.

Required design additions:

- Show both successful count and failed count on the card or drawer header.
- Show per-message status badges in the drawer.
- Mark fallback recipient IDs when `search_dm` cannot extract a stable Douyin ID.
- Preserve the current list when detail loading fails.

No design challenge. The drawer approach is a good first version and avoids turning Data Center into a full CRM.

### Engineering Review

Initial engineering score: 6/10 before fixes, 8/10 after the updates above.

Confirmed architecture:

```text
device handler
  -> claimDMRecipient
  -> _sendMessageSequence returns per-message results
  -> dm-send-report per result
  -> Conversation summary update
  -> ConversationMessage ledger insert/update
  -> Data Center list + detail drawer
```

Critical fixes added to the spec:

- `search_dm` must create or reuse conversations and report each message.
- `reply_comment` must stop joining sequence messages into one report payload.
- `task_id` must be present in new message reports.
- Idempotency should use `(conversation_id, message_key)`, not nullable `(conversation_id, task_id, message_order)`.
- Failed sends should be visible in message details without inflating `total_dm_count`.

Remaining implementation risks:

- AutoJS is ES5.1, so device changes must avoid modern JavaScript syntax.
- `search_dm` may not always have a stable recipient Douyin ID at send time; fallback IDs need clear UI labeling.
- Existing non-admin permission logic joins conversations through `task_id`; new reports must backfill `Conversation.task_id` where possible.

### DX Review

DX score: 7/10. The API direction is clear, but the implementation plan must make request/response payloads explicit before coding.

Required implementation-plan details:

- Pydantic request model fields and defaults for `DMSendReportRequest`.
- Detail response serializer instead of returning raw ORM rows.
- Migration shape for `conversation_messages`, indexes, and unique constraints.
- Device payload examples for `reply_comment` sequence, `search_dm` sequence, single-message DM, and failed message.
- Export format example for the multiline “消息明细” column.

### Decision Audit Trail

| Decision | Classification | Auto Decision | Reason |
| --- | --- | --- | --- |
| Use independent `conversation_messages` table | Mechanical | Accepted | It is the only option that preserves every DM as auditable data. |
| Cover `search_dm` device path | Mechanical | Accepted | Code inspection showed it currently has no conversation report path. |
| Replace nullable tuple idempotency with `message_key` | Mechanical | Accepted | SQL unique constraints with nullable columns do not reliably prevent duplicates. |
| Count only successful sends in `total_dm_count` | Mechanical | Accepted | Failed sends should be visible but not counted as delivered DMs. |
| Keep card + drawer UI | Taste | Accepted | It solves the display problem without expanding into a CRM rebuild. |
| Keep multiline export first, not a separate message export endpoint | Taste | Accepted | Good first slice; a dedicated detail export can be added after usage proves the need. |

### Final Gate

No user challenges. Two taste decisions remain for review:

- Card + drawer stays as the first UI version.
- Conversation export gets a multiline “消息明细” column first, not a separate message-detail export endpoint.

Recommended approval: approve the reviewed spec and move to a detailed implementation plan.
