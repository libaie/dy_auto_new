# DM 序列模板系统 — 设计文档

**Date:** 2026-05-18
**Status:** proposed
**Branch:** feature/video-review-fixes

## Context

当前 `search_dm` 任务每次只发送**一条私信**。`params.content` 字段承载单条内容：有预设值时直接发送，无预设值时 AI 生成一条。用户需要升级为：预设**多条有序消息模板**，一次进入用户主页连续发送（复用现有拟人输入），无模板时 AI 生成 N 条序列。

`keywordContent` 字段（`KeywordSearchDialog.vue`）和 `formParams.content`（`CreateChannelDialog.vue`）目前都是单行/单文本域，承载不了"多条有序消息"的语义。

## Decision

新增独立的 `DMSequence` 表 + CRUD API + 设备端序列发送循环。不与 `ContentTemplate` 混用——后者管理单条文本模板变量，前者管理**有序消息序列**。

`params.content` 向下兼容（单条字符串），新增 `params.dm_sequence_id` 引用模板。设备端无需新 UI 操作——`safeInput` + `submitViaKeyboard` 已实现拟人，序列发送只是循环调用。

## Architecture

```
┌─ 前端 ──────────────────────────────────────────────────┐
│ DMSequenceManagePage (新)    KeywordSearchDialog (改)     │
│ CRUD 模板管理                dm_sequence_id 下拉选择       │
│ 拖拽排序消息                 keywordContent 保留兼容       │
└────────────────────────────┬────────────────────────────┘
                             │ API: /api/dm-sequences
┌─ 服务端 ───────────────────┼────────────────────────────┐
│ routers/dm_sequences.py (新)                             │
│ db_models.py: DMSequence (新表)                          │
│ task: params.dm_sequence_id → 加载序列 → 下发到设备        │
└────────────────────────────┬────────────────────────────┘
                             │ params.dm_sequence_id
┌─ 设备端 ────────────────────────────────────────────────┐
│ search-dm.js:                                            │
│   有 dm_sequence_id → 获取 messages[] → 遍历发送          │
│   无 dm_sequence_id → 当前行为 (单条 content)              │
│   无模板+count>1 → AI 生成 N 条序列                       │
└─────────────────────────────────────────────────────────┘
```

## Data Model

### New table: `dm_sequences`

```python
class DMSequence(Base):
    __tablename__ = "dm_sequences"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)          # 模板名称
    messages = Column(JSON, nullable=False)             # [{order, content, delay_ms}]
    industry = Column(String(50), nullable=True)        # 行业标签
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=bj_now)
    updated_at = Column(DateTime, nullable=False, default=bj_now, onupdate=bj_now)
```

`messages` JSON:

```json
[
  {"order": 1, "content": "你好，我是做{{industry}}的", "delay_ms": 3000},
  {"order": 2, "content": "看到你对{{keyword}}感兴趣", "delay_ms": 5000},
  {"order": 3, "content": "方便聊聊吗？", "delay_ms": 0}
]
```

字段说明:
- **order**: 发送顺序（从 1 开始），前端拖拽排序后重新编号
- **content**: 消息文本，支持 `{{keyword}}`、`{{industry}}` 等变量替换
- **delay_ms**: 本条发送**完成后**额外等待时间。0 = 仅用系统拟人延迟（random 2000-5000ms）

### Task params extension

| 字段 | 类型 | 说明 |
|------|------|------|
| `params.content` | `string \| null` | **保留兼容**。单条消息文本 |
| `params.dm_sequence_id` | `string \| null` | **新增**。DMSequence.id |

优先级规则:

```
params.dm_sequence_id 存在且有效
  → 使用 DMSequence.messages，忽略 params.content
params.dm_sequence_id 不存在
  → params.content 有值 → 发单条
  → params.content 为空 + count>1 → AI 生成 count 条
  → params.content 为空 + count≤1 → AI 生成 1 条
```

## API Design

### `GET /api/dm-sequences`

列表，支持 `?industry=` 过滤。

```json
{"sequences": [{"id":"...", "name":"健康行业标准话术", "message_count":3, "industry":"健康", "created_at":"..."}]}
```

### `POST /api/dm-sequences`

创建模板。Admin only。

```json
{
  "name": "健康行业标准话术",
  "messages": [
    {"order": 1, "content": "你好，我是做健康管理的", "delay_ms": 3000},
    {"order": 2, "content": "看到你对养生感兴趣", "delay_ms": 5000}
  ],
  "industry": "健康"
}
```

校验：`messages` 非空，每条 `content` 非空且 ≤ 500 字符，`order` 自动重排。

### `GET /api/dm-sequences/{id}`

获取模板详情（含完整 messages）。

### `PUT /api/dm-sequences/{id}`

更新模板。Admin only。

### `DELETE /api/dm-sequences/{id}`

删除模板。已有 task 引用不阻止删除——`search-dm.js` 处理时如果 `dm_sequence_id` 找不到模板，回退到 `params.content` 或 AI 生成。

### `GET /api/device/dm-sequences`

设备端拉取所有序列模板。**已替代为 poll 响应中下发**——`GET /api/device/poll` 新增 `dm_sequences` 字段，与 task/selectors 一起返回。减少一次 HTTP 请求。

### Poll 响应扩展

```json
{
  "task": {...},
  "dm_sequences": [{"id":"...", "messages":[{...}]}],
  "selectors_version": 1,
  ...
}
```

## Device-Side Changes

### search-base.js — 新增序列发送方法

```javascript
/**
 * 解析消息序列，返回 [{order, content, delay_ms}]
 * 优先级: dm_sequence_id > params.content > AI 生成
 */
resolveMessages: function (params, seqCache) {
  if (params.dm_sequence_id && seqCache && seqCache[params.dm_sequence_id]) {
    return seqCache[params.dm_sequence_id].messages;
  }
  if (params.content) {
    return [{order: 1, content: params.content, delay_ms: 0}];
  }
  var count = params.count || 1;
  if (count > 1) {
    return aiAnalyzer.generateVideoDMSequence(this._extractVideoText(), count);
  }
  var single = aiAnalyzer.generateVideoDM(this._extractVideoText());
  return single ? [{order: 1, content: single, delay_ms: 0}] : [];
},

/**
 * 变量替换 — 不存在的 key → 空字符串（静默）
 */
applyVariables: function (template, vars) {
  return template.replace(/\{\{(\w+)\}\}/g, function (_, key) {
    return vars[key] || "";
  });
},

/**
 * 发送消息序列的通用循环
 */
_sendMessageSequence: function (messages, stats, keyword) {
  for (var i = 0; i < messages.length; i++) {
    var msg = messages[i];
    var content = this.applyVariables(msg.content, {keyword: keyword});
    this.safeInput("dm_input", content);
    this.submitViaKeyboard("dm_send");
    var extraDelay = msg.delay_ms || Math.floor(Math.random() * 3000) + 2000;
    sleep(extraDelay);
    stats.details.push("dm_sent[" + (i + 1) + "/" + messages.length + "]: "
      + content.substring(0, 30));
  }
}
```

### search-dm.js — 改为调用父类方法

```javascript
SearchDMHandler._interactWithVideo = function (content, stats) {
  var messages = this.resolveMessages(this._params,
    this._dmSeqCache || {});
  if (!messages || messages.length === 0) {
    logger.warn(TAG, "无法获取私信内容，跳过");
    return false;
  }
  var avatarClicked = this.safeClick("video_author_avatar", 2);
  if (!avatarClicked) return false;
  sleep(2000);
  var messageClicked = this.safeClick("dm_entry_btn", 3);
  if (!messageClicked) return false;
  sleep(1500);
  this._sendMessageSequence(messages, stats, this._params.keyword);
  return true;
};
```

### reply-comment.js — DM 序列联动

在回复评论后、判断是否需要 DM 时，若 task.params.dm_sequence_id 存在，走序列发送而不是当前的单条 DM 逻辑。具体改动位置：`_processComments()` 中 canDM 分支，替换 `safeInput("dm_input", dmContent)` → `this._sendMessageSequence(messages, stats, keyword)`。

### 现有能力复用

- `safeInput("dm_input", content)`: 拟人输入，逐字符键入 + 随机抖动 → **直接复用**
- `submitViaKeyboard("dm_send")`: 键盘回车发送 → **直接复用**
- `aiAnalyzer.generateVideoDM(videoText)`: AI 生成单条 DM → **向后兼容**
- `aiAnalyzer.generateVideoDMSequence(videoText, count)`: AI 生成 N 条序列 → **新增**

## Frontend Changes

### 1. DMSequenceManagePage（新建）

路由: `/dm-sequences`，侧边栏 "DM 序列"。

功能:
- 列表页：卡片或表格，显示名称、行业、消息数、更新时间
- 新建/编辑弹窗：名称、行业、消息列表（每行: content textarea + delay_ms 数字输入 + 拖拽手柄 + 删除按钮）
- 拖拽排序：`vuedraggable` 或原生 HTML5 drag
- 删除确认弹窗

UI 布局:

```
┌─ DM 序列模板 ──────────────────────────────────────┐
│ [+ 新建模板]                    行业筛选: [全部 ▾]   │
│                                                    │
│ ┌──────────────────────────────────────────┐       │
│ │ 健康行业标准话术    3 条消息    健康       │       │
│ │ 2026-05-18 15:00              [编辑][删除]│       │
│ └──────────────────────────────────────────┘       │
│ ┌──────────────────────────────────────────┐       │
│ │ 旅游行业标准话术    2 条消息    旅游       │       │
│ │ 2026-05-18 14:30              [编辑][删除]│       │
│ └──────────────────────────────────────────┘       │
└────────────────────────────────────────────────────┘
```

### 2. KeywordSearchDialog.vue（修改）

`keywordContent` textarea 上方新增:

```
┌─────────────────────────────────────────────┐
│ 私信序列模板: [选择模板 ▾] 或 手动输入内容:   │
│ ┌─────────────────────────────────────────┐ │
│ │ (保留现有 keywordContent textarea)       │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

逻辑: 选择模板后 `keywordContent` 置灰禁用（或自动填充提示文字）。

### 3. CreateChannelDialog.vue（修改）

`formParams.content` textarea 上方新增 `dm_sequence_id` 下拉框:

```
私信序列模板（可选）: [无（使用下方内容） ▾]
私信内容: [现有 textarea，选择模板后禁用]
```

## Channel Integration

Channel 创建时 `params_template.dm_sequence_id` → 分发的每个 task 继承该参数。Channel 分发逻辑无需改动——`params_template` 合并到 task.params 的流程已存在。

支持 Channel 编辑（`PUT /api/channels/{id}`）修改 `params_template.dm_sequence_id`。

## Error Handling

| 场景 | 处理 |
|------|------|
| `dm_sequence_id` 指向已删除模板 | 回退到 `params.content` 或 AI 生成 |
| `messages` 为空数组 | 同回退 |
| 单条消息发送失败 | 跳过本条，继续下一条（不阻塞整个序列） |
| 发送前检测对话已存在（Conversation 去重） | 当前机制已处理——`dm-claim-recipient` 返回 claimed=false 则跳过 |
| 变量替换中 key 不存在 | 空字符串替换，不发 `undefined` |

## Testing

| 层 | 测试内容 |
|----|---------|
| **单元** | `applyVariables()` 变量替换 |
| **单元** | `resolveMessages()` 优先级逻辑 |
| **API** | DMSequence CRUD 校验 + 权限 |
| **API** | Task 创建含 `dm_sequence_id` → 参数正确传递 |
| **集成** | 设备端拉取序列模板列表 |
| **设备** | 序列发送循环：有模板/无模板/AI 生成/AI 生成多条 |
| **回归** | `params.content` 单条模式不改行为 |

## Migration

- `params.content` 字段**不删除、不改语义**——所有现有 task 和 channel 继续正常工作
- 新字段 `params.dm_sequence_id` 为 optional，默认 null
- 前端 `keywordContent` textarea 保留，新增模板选择器
- Channel `params_template` 兼容旧数据（无 `dm_sequence_id` → null）

## NOT in Scope

- DM 序列跨任务追踪（今天发第 1 条，明天发第 2 条）——用户确认本次只做一次性连发
- AI 根据对方回复动态调整下一条内容（对话式 AI）——后续迭代
- 序列模板变量支持更多字段（用户名、性别等）——当前仅 `{{keyword}}`，后续按需扩展

## Risks

- **序列过长导致主页停留过久**: 前端限制最多 10 条，单条发送 + 延迟合计约 30 秒/条，10 条约 5 分钟——可通过 `content.length` 校验控制
- **变量替换依赖设备端**: `{{keyword}}` 等变量在设备端解析，服务端不感知。若未来需要更多变量，需同步更新 device script
- **AI 生成多条**: `generateVideoDMSequence(videoText, count)` 的 prompt 需明确指示 AI 返回 JSON 数组 `[{order, content}]`，而非单条文本。若 AI 返回格式不正确，回退到只发一条

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/autoplan` | Strategy & scope | 1 | CLEAN | Premises accepted. Scope well-bounded. One deferral: reply_comment DM sequence → TODOS |
| Eng Review | `/autoplan` | Architecture & tests (required) | 1 | CLEAN | Arch clean, backward-compatible. 9 test gaps identified. No perf concerns. |
| Design Review | `/autoplan` | UI/UX gaps | — | SKIPPED | CRUD-only UI, no consumer-facing design. Existing design system covers components. |
| DX Review | `/autoplan` | Developer experience | — | SKIPPED | No external API consumers. Internal system feature. |

### CEO Findings
- **Premises**: All 3 accepted (sequence template > single content, independent table > mix into ContentTemplate, device-side loop reuses existing primitives)
- **Scope**: Approved as-is. `reply_comment.js` DM sequence support deferred to TODOS.md
- **Alternatives considered**: (A) Extend ContentTemplate with a "sequence" type — rejected, different data shape. (B) Store messages as newline-separated text — rejected, loses delay_ms per message. Chosen: independent JSON column (most flexible, clean separation)

### Eng Findings
- **Architecture**: Clean 3-layer separation. New `routers/dm_sequences.py` follows existing CRUD pattern. Backward-compatible params extension.
- **Test gaps**: 9 paths identified (5 API endpoints + 4 device functions). API tests mandatory. Device tests deferred to manual QA.
- **Code quality**: No DRY violations. `applyVariables()` regex potential future duplication — accepted as pragmatic (YAGNI).
- **Performance**: No concerns (PK lookups, no N+1, loop is sleep-bound).
- **Security**: All endpoints verified — admin-only CRUD via `verify_admin_token`, device endpoint via `verify_device_secret`.

### Auto-Decisions
| # | Decision | Principle | Rationale |
|---|----------|-----------|-----------|
| 1 | Scope: approve as-is | P3 (pragmatic) | Well-bounded, backward-compatible |
| 2 | reply_comment DM seq → TODOS | P3 (pragmatic) | Outside current scope |
| 3 | API CRUD tests mandatory | P1 (completeness) | Follows existing test patterns |
| 4 | Device tests → manual QA | P3 (pragmatic) | No device test infra exists |
| 5 | applyVariables regex duplication OK | P5 (YAGNI) | No current need for shared validation |

### VERDICT
CEO + ENG CLEARED — ready to implement. No blocking issues.

Run `/ship` when ready, or proceed with `/writing-plans` for implementation planning.
