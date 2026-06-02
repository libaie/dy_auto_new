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
- `task_id`: 关联任务，允许为空以兼容历史补齐
- `account_id`: 发送账号
- `device_id`: 执行设备
- `dm_sequence_id`: 使用的 DM 序列模板，允许为空
- `message_order`: 序列中的第几条
- `content`: 实际发送内容
- `status`: `sent` 或 `failed`
- `sent_at`: 发送时间
- `error_message`: 失败原因，允许为空
- `created_at`: 记录创建时间

幂等约束使用 `(conversation_id, task_id, message_order)`。当 `task_id` 为空时，历史补齐只为每个会话生成一条摘要消息。

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

- `message_order`
- `dm_sequence_id`
- `status`
- `error_message`

写入行为：

- 每次上报插入或更新一条 `conversation_messages`。
- 同步更新 `conversations.last_dm_content`、`last_dm_at`、`total_dm_count`、`current_stage`、`intent`。
- 重复上报同一 `(conversation_id, task_id, message_order)` 时更新已有记录，不重复增加展示条目。

## 设备端流程

设备端如果当前只在序列结束后上报一次，需要调整为每条私信发送完成后上报一次。

每条上报应包含：

- 会话 ID
- 任务 ID
- 账号 ID
- 设备 ID
- DM 序列 ID
- 当前消息序号
- 实际发送内容
- 成功或失败状态
- 失败原因

如果某条发送失败，设备端仍可上报失败记录，后端将其展示在流水中，避免用户误以为三条都发送成功。

## 前端体验

数据中心的“私信会话”保留卡片列表。

卡片展示：

- 收件人昵称和抖音号
- 阶段标签
- 状态标签
- 最近一条私信摘要
- 总消息数
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
- 同一 `(conversation_id, task_id, message_order)` 重复上报不会重复插入。
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

## 风险与约束

- 设备端可能需要从“序列结束上报一次”改为“每条消息上报一次”，这是本设计能否展示完整三条私信的关键。
- 历史数据无法完整恢复，必须在 UI 上明确标注。
- 幂等约束需要覆盖设备重试，否则会出现重复消息。
- 第一版不引入统一事件日志，避免扩大到评论、关注、采集等其他动作。

## 验收标准

- 新的三条私信序列发送后，数据中心会话详情能看到三条内容、顺序和发送时间。
- 会话卡片仍能正常按阶段、状态、账号筛选。
- 历史会话不会被误展示成完整流水。
- 重复上报不会造成重复消息。
- 详情接口和导出不会破坏现有会话列表 API。
