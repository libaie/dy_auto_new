# 任务通道（Task Channel）设计文档

> 关键词搜索任务的并发分发系统，支持多设备协作执行同一通道内的关键词队列。

## 背景与问题

当前系统中，批量关键词搜索任务的分发存在以下问题：

1. **一次性全量创建**：10 个关键词 = 10 个独立 Task，全部同时插入 DB
2. **无协调机制**：设备通过 poll 竞争领取，先到先得，无法控制分发节奏
3. **单设备瓶颈**：只有一台设备在线时，10 个任务全部堆积给它串行执行
4. **新设备无法介入**：设备上线后无法参与已创建任务的协作执行
5. **缺乏进度可见性**：无法直观看到一组关键词任务的整体进度

## 设计目标

- 引入通道（Channel）概念，关键词任务有序排队、按设备容量分发
- 多设备在线 → 并发执行，每台设备同一时间只处理一个关键词
- 单设备在线 → 串行执行，完成一个再领下一个
- 新设备上线 → 自动从通道领取待处理关键词
- 通道可暂停/恢复/取消/追加关键词
- 失败 → 跳过继续，不阻塞后续关键词
- 设备端无需改动，通道逻辑完全在服务端实现
- 搜索类任务（通道核心场景）受平台风控重点监控，需频率控制和账号健康感知

## 审查修复项（autoplan 4 阶段审查 + 风控审查）

| # | 来源 | 修复 |
|---|------|------|
| C1 | Eng | SQLite 配置 WAL 模式 + busy_timeout=5000 |
| C2 | Eng | 完成检测使用原子 UPDATE + EXISTS 子查询，避免 TOCTOU 竞态 |
| C3 | Eng | 懒创建 Task 使用 flush-only 变体，不 commit，由 poll 端点统一 commit |
| C4 | CEO | assigned 超过 10 分钟自动回退 pending（stale 回收） |
| H1 | Eng | 通道 claim 路径复用现有 bound_account_id 路由逻辑 |
| H2 | Eng | report_result() 重试时同步回滚 ChannelItem→pending |
| H3 | Eng | ChannelItem 添加 `(channel_id, status)` 复合索引 |
| H4 | CEO | 单通道最大 500 个关键词 |
| H5 | CEO | 软删除（status=deleted）替代物理删除 |
| R1 | 风控 | 通道 claim 必须过滤 Account.status == 'active' |
| R2 | 风控 | per-account 并发锁：同一账号同时只能有 1 个 running 通道任务 |
| R3 | 风控 | 通道支持配置任务间 cooldown（默认 5 分钟） |
| R5 | 风控 | 风控事件触发时，自动将该账号的 pending item 标记 skipped |
| R7 | 风控 | params_template 增加 delay_range 配置（任务间随机延迟范围） |

## 数据模型

### Channel 表（`channels`）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| group_id | FK → account_groups | 绑定的账号分组 |
| task_type | str | `search_comment` / `search_like` / `search_dm` / `reply_comment` |
| status | str | `active` / `paused` / `completed` / `cancelled` |
| account_mode | str | `single_account` / `round_robin` |
| account_id | FK → accounts（nullable） | single_account 模式下指定的账号 |
| params_template | JSON | 共享参数模板（content, count, sort_by 等） |
| cooldown_seconds | int | 同一账号连续任务间最小间隔（默认 300 秒） |
| delay_range | JSON | 任务间随机延迟范围 `[min_ms, max_ms]`，默认 `[3000, 8000]` |
| max_keywords | int | 最大关键词数限制（默认 500） |
| current_account_index | int | round_robin 模式的轮转索引 |
| created_at | datetime | 创建时间 |
| completed_at | datetime | 完成时间（null = 未完成） |
| deleted_at | datetime | 软删除时间（null = 未删除） |

### ChannelItem 表（`channel_items`）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| channel_id | FK → channels | 所属通道 |
| keyword | str | 搜索关键词 |
| account_id | FK → accounts | 分配的账号 |
| status | str | `pending` / `assigned` / `completed` / `failed` / `skipped` |
| assigned_device_id | FK → devices | 领取的设备 |
| assigned_at | datetime | 设备领取时间（用于 stale recovery 判断） |
| task_id | FK → tasks | 关联的 Task（领取时创建） |
| queue_position | int | 队列排序位置 |
| created_at | datetime | 创建时间 |
| completed_at | datetime | 完成/失败时间 |

**索引**：`(channel_id, status)` 复合索引，`(assigned_device_id)` 索引。

### 关键设计决策

**懒创建 Task**：ChannelItem 在 `pending` 状态时不创建 Task。设备领取时（`assigned`）才创建实际的 Task 记录。避免 DB 中预创建大量空闲 Task。

**单账号模式**：所有 ChannelItem 的 `account_id` 相同，使用 Channel 表的 `account_id` 字段。

**分摊模式**：ChannelItem 的 `account_id` 按 round-robin 分配给组内活跃账号（`Account.status == 'active'`）。分配时跳过非 active 账号，优先选择今日用量最少的账号。

### 状态流转

```
ChannelItem:
  pending → assigned → completed
                     → failed   (跳过)
                     → skipped  (手动跳过)

Channel:
  active → paused ↔ active
  active → completed  (所有 item 完成)
  active/paused → cancelled  (手动取消)
```

## 分发逻辑

### 设备 poll 时的通道感知

修改 `task_service.get_pending_task()`，在现有领取逻辑之前增加通道任务优先领取：

```
设备 poll 请求
  │
  ├─ 1. 检查是否有活跃通道（Channel.status = 'active', deleted_at IS NULL）
  │     且有 pending 的 ChannelItem
  │
  ├─ 2. 如果有 → 领取一个 pending 的 ChannelItem
  │     ├─ 过滤条件（必须全部满足）：
  │     │   - ChannelItem.status = 'pending'
  │     │   - ChannelItem.account_id 对应的 Account.status = 'active'
  │     │   - 该账号当前无其他 running 状态的通道任务（per-account 并发锁）
  │     │   - 该账号距离上次通道任务完成时间 >= channel.cooldown_seconds
  │     ├─ 乐观锁: UPDATE SET status='assigned', assigned_device_id=?
  │     │          WHERE id=? AND status='pending'
  │     ├─ flush-only 创建 Task（不 commit）
  │     │   type=通道task_type, account_id=item.account_id
  │     │   params = merge(params_template, {keyword: item.keyword})
  │     └─ 更新 ChannelItem.task_id
  │
  └─ 3. 如果没有通道任务 → 走现有 Task 领取逻辑
```

**路由兼容**：通道 claim 路径复用现有 `bound_account_id` 路由逻辑。bound 设备只能领取其绑定账号的通道 item；unbound 设备可领取任意 active 账号的 item。

**stale 回收**：每次 poll 时，将 `assigned_at` 超过 10 分钟仍为 `assigned` 状态的 ChannelItem 自动回退为 `pending`（设备可能已离线）。

### 设备领取范围

由于设备不绑定账号（动态分配模式），任何在线设备都可以领取任何活跃通道的 pending 项。无需匹配组。

### 单设备串行保证

设备端现有的 `_taskBusy` 互斥锁保证串行执行。通道的 `assigned` 状态防止同一关键词被重复领取。

### 新设备上线

新设备连接 WS 后触发 `catchUpPoll()`，走同样的通道领取逻辑。无需特殊处理。

### 完成与推进

```
设备报告任务完成
  │
  ├─ 更新 Task 状态为 completed/failed
  ├─ 更新 ChannelItem 状态为 completed/failed
  ├─ 如果 Task 重试（retry_count < MAX_RETRIES）：
  │     同步回滚 ChannelItem → pending，清除 assigned_device_id
  └─ 原子检查通道是否全部完成：
        UPDATE channels SET status='completed', completed_at=now
        WHERE id=? AND status='active'
        AND NOT EXISTS (
          SELECT 1 FROM channel_items
          WHERE channel_id=? AND status NOT IN ('completed','failed','skipped')
        )
        ├─ rowcount=1 → 推送 channel_completed 事件
        └─ rowcount=0 → 推送 channel_progress 事件
```

### 风控联动

```
设备上报风控事件（/risk-report）
  │
  ├─ 标记 Account.status = 'risk_controlled'
  └─ 自动处理该账号的通道 item：
        UPDATE channel_items SET status='skipped'
        WHERE account_id=? AND status='pending'
        推送 channel_progress 事件
```

已 assigned 的 item 不受影响（设备端 crash-recovery 会自行停止执行）。

### 暂停/恢复

- **暂停**：Channel.status → `paused`，poll 时跳过 paused 通道。已 assigned 的 item 继续执行。
- **恢复**：Channel.status → `active`，poll 时重新可见。
- **取消**：Channel.status → `cancelled`，所有 pending item 标记 skipped，已 assigned 的等待完成。

## API 设计

### 通道管理端点（Admin，需要 admin token）

#### 创建通道

```
POST /api/channels
```

请求体：
```json
{
  "group_id": "grp-xxx",
  "task_type": "search_comment",
  "account_mode": "round_robin",
  "account_id": null,
  "keywords": ["美食", "旅游", "健身", "穿搭", "数码"],
  "params_template": {
    "content": "好棒！",
    "count": 5,
    "sort_by": "latest"
  },
  "cooldown_seconds": 300,
  "delay_range": [3000, 8000]
}
```

`account_id` 仅在 `account_mode = "single_account"` 时必填。`keywords` 数组长度上限 500。

处理逻辑：
1. 验证 group_id 存在
2. 验证 keywords 数量 <= 500
3. 查询组内 `Account.status == 'active'` 的账号列表
4. single_account 模式：验证 account_id 对应的账号 status == 'active'
5. round_robin 模式：关键词按顺序轮转分配给组内 active 账号（优先今日用量最少的）
6. 创建 N 个 ChannelItem（status=pending）
7. 返回 Channel 对象（含 item 统计）

#### 列出通道

```
GET /api/channels
```

返回所有通道列表，每个通道包含统计信息（total/pending/assigned/completed/failed item 计数）。

#### 通道详情

```
GET /api/channels/{id}
```

返回通道详情 + 所有 ChannelItem 列表。

#### 更新通道（暂停/恢复/取消）

```
PATCH /api/channels/{id}
```

请求体：
```json
{
  "status": "paused"
}
```

允许的状态转换：`active→paused`、`paused→active`、`active→cancelled`、`paused→cancelled`。

#### 删除通道（软删除）

```
DELETE /api/channels/{id}
```

软删除：设置 `Channel.deleted_at = now`，所有 pending item 标记 skipped。已 assigned 且正在执行的 Task 不受影响（设备完成后 Task 标记 completed，但通道已删除所以不触发通道推进）。列表查询默认过滤 `deleted_at IS NULL`。

#### 追加关键词

```
POST /api/channels/{id}/items
```

请求体：
```json
{
  "keywords": ["新关键词1", "新关键词2"]
}
```

向活跃通道追加新的 ChannelItem。

#### 单个 item 操作

```
PATCH /api/channels/{id}/items/{item_id}
```

请求体：
```json
{
  "status": "skipped"
}
```

支持：`pending→skipped`（跳过）、`failed→pending`（重新入队）。

### 设备端 poll 修改

`GET /api/device/poll` 响应格式不变——设备仍收到一个 Task 对象。通道逻辑完全在服务端实现，设备端无感知。

### WS 通知（Admin）

通道事件推送给前端 admin WS 连接：
- `channel_progress`：item 状态变化时推送 `{ channel_id, total, completed, failed, assigned, pending }`
- `channel_completed`：所有 item 完成时推送 `{ channel_id }`

## 前端 UI

### 新增页面：通道管理

在侧边栏导航中增加「任务通道」入口。

**页面布局**：
- 顶部：标题 + 「创建通道」按钮
- 主体：通道卡片列表，每个卡片显示：
  - 通道名称（组名 · 任务类型 · 账号模式）
  - 进度条（completed / total）
  - 状态标签 + 在线设备数
  - 操作按钮（暂停/恢复、取消、查看详情）

**创建通道弹窗**：
- AccountGroup 下拉选择
- 任务类型选择（search_comment / search_like / search_dm / reply_comment）
- 账号模式选择（单账号 / 分摊）。单账号时显示账号下拉选择
- 关键词输入（textarea，每行一个，支持 AI 扩展按钮）
- 共享参数表单（根据任务类型动态显示）

**通道详情页**：
- 顶部：状态、进度条、统计数字
- 操作栏：暂停/恢复、追加关键词、取消
- 关键词列表：每行显示 keyword、account、status、device、操作

### 实时更新

通过 admin WebSocket 接收事件，实时更新进度条和统计数字。

## 基础设施前置要求

### SQLite WAL 模式

当前 SQLite 使用默认的 DELETE 日志模式，并发写入会互相阻塞。通道的 poll-claim 是写操作，必须启用 WAL 模式：

```python
# database.py - engine 创建后添加
from sqlalchemy import event

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
```

此修复独立于通道功能，应优先合入。

## 与现有系统的关系

- **Task 表**：不修改。通道领取时才懒创建 Task。
- **AccountGroup**：复用，作为通道的分组依据。
- **Account.status**：通道 claim 必须过滤 `active` 状态，与 chain_service 一致。
- **设备 poll**：扩展 `get_pending_task()` 增加通道感知，现有逻辑不变。
- **设备端**：零改动。设备仍按 poll → execute → report 流程工作。
- **批量创建 / 任务链**：不受影响，两套系统并行。
- **风控系统**：`/risk-report` 联动通道，自动 skipped 该账号的 pending item。

## 文件变更清单

| 层 | 文件 | 变更 |
|---|---|---|
| Server | `server/app/database.py` | 添加 SQLite WAL 模式 + busy_timeout |
| Server | `server/app/db_models.py` | 新增 Channel、ChannelItem ORM 模型（含索引） |
| Server | `server/app/models.py` | 新增 ChannelCreate、ChannelResponse 等 Pydantic 模型 |
| Server | `server/app/routers/channels.py` | 新增通道管理路由（CRUD + 暂停/恢复/取消） |
| Server | `server/app/services/channel_service.py` | 新增通道服务（创建、分发、完成推进、stale 回收、风控联动） |
| Server | `server/app/services/task_service.py` | 修改 `get_pending_task()` 增加通道领取 |
| Server | `server/app/routers/device.py` | poll 端点适配通道逻辑；risk-report 联动通道 |
| Server | `server/app/ws_manager.py` | 新增通道事件推送方法 |
| Server | `server/tests/test_channel_service.py` | 新增通道服务测试（含并发测试） |
| Web | `web/src/api/channels.js` | 新增通道 API 封装 |
| Web | `web/src/views/ChannelsPage.vue` | 新增通道管理页面 |
| Web | `web/src/components/ChannelCard.vue` | 通道卡片组件 |
| Web | `web/src/components/CreateChannelDialog.vue` | 创建通道弹窗 |
| Web | `web/src/components/ChannelDetail.vue` | 通道详情组件 |
| Web | `web/src/router/index.js` | 新增路由 |
| Web | `web/src/App.vue` | 侧边栏增加导航入口 |

## 验证场景

1. 创建通道（5 个关键词，round_robin，2 个 active 账号）→ 确认 5 个 ChannelItem 按轮转分配账号
2. 1 台设备在线 → poll 领取 1 个关键词 → 完成 → 等待 cooldown → 领取下一个 → 串行执行
3. 2 台设备在线 → 各领取 1 个关键词 → 同时执行 → 完成后各自领取下一个
4. 执行中 1 台新设备上线 → 从通道领取 pending 的关键词
5. 暂停通道 → 设备不再领取新 item → 已 assigned 的继续完成
6. 恢复通道 → 设备重新领取
7. 关键词失败 → 标记 failed → 不影响后续关键词
8. 手动跳过 → item 标记 skipped
9. 追加关键词 → 新 item 加入队列
10. 所有 item 完成 → 通道自动标记 completed → 前端收到通知
11. 账号被风控 → pending item 自动 skipped → 设备领取其他账号的 item
12. 设备离线 → assigned 超 10 分钟 → 自动回退 pending → 其他设备可领取
13. 两个设备同时完成最后 item → 通道恰好 completed 一次（原子检查）
14. risk_controlled 账号的 item 不会被任何设备领取
15. 同一账号有 running 通道任务时，不会分配第二个通道任务（并发锁）
