# 数据中心 — 采集数据展示 & 私信会话管理

> 设备采集的评论、用户资料、AI 发送的私信统一展示；私信全局去重，支持后期扩展为完整对话。

## 架构概览

```
设备端                             服务端                           前端
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
collect-report ──────→ collected_comments ──→ GET /api/data/comments
                     → collected_users    ──→ GET /api/data/users
                     
dm-claim-recipient ──→ conversations ──────→ GET /api/data/conversations
dm-send-report ──────→ conversations (update stage/content)
dm-release-recipient ─→ conversations (delete/rollback)

WS 实时推送:
  新数据入库 → broadcast_to_admins({ event: "data_changed", type: "comment|user|conversation" })
```

---

## 1. 数据模型

### 新表：conversations（私信会话）

```sql
CREATE TABLE conversations (
    id              VARCHAR(36) PRIMARY KEY,
    task_id         VARCHAR(36) REFERENCES tasks(id),
    account_id      VARCHAR(36) REFERENCES accounts(id) NOT NULL,
    device_id       VARCHAR(36) REFERENCES devices(id),
    keyword         VARCHAR(200),
    
    -- 收信人
    recipient_nickname   VARCHAR(100) NOT NULL,
    recipient_douyin_id  VARCHAR(100) NOT NULL,
    
    -- 私信内容与阶段
    current_stage   VARCHAR(20) NOT NULL DEFAULT 'qualifying',
                    -- qualifying / nurturing / converting / follow_up
    intent          VARCHAR(30),
                    -- AI 意图分类
    last_dm_content TEXT,
    last_dm_at      DATETIME,
    
    -- claim 超时恢复
    claimed_at      DATETIME,       -- claim 时间，超 30min 未 send 则自动释放
    
    -- 状态
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
                    -- active / replied / closed
    
    -- 统计
    total_dm_count  INTEGER NOT NULL DEFAULT 0,
    
    -- 后期对话扩展（一期字段预留但暂不用）
    reply_received_at  DATETIME,
    
    created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(account_id, recipient_douyin_id)
);

CREATE INDEX ix_conversations_task_id ON conversations(task_id);
CREATE INDEX ix_conversations_account_id ON conversations(account_id);
CREATE INDEX ix_conversations_stage ON conversations(current_stage);
CREATE INDEX ix_conversations_status ON conversations(status);
```

**去重逻辑**：`UNIQUE(account_id, recipient_douyin_id)` — 一个账号对一个抖音用户只能有一个活跃会话。设备发 DM 前调用 claim 接口，服务端原子插入，返回 claimed=false 表示该用户已被其他设备 DM 过。

### 复用已有表

- `collected_comments` — 不改结构
- `collected_users` — 不改结构

---

## 2. API

### 2.1 设备端（3 个端点）

#### POST /api/device/dm-claim-recipient

```json
// Request
{ "account_id": "...", "recipient_douyin_id": "123456", "recipient_nickname": "用户A" }

// Response 200
{ "claimed": true, "conversation_id": "uuid" }
// 或
{ "claimed": false, "conversation_id": null }
```

原子操作：先 SELECT 查是否已有活跃会话，无则 INSERT。SQLite WAL 模式下两个并发请求可能同时通过 SELECT → 第二个 INSERT 触发 UNIQUE 约束的 IntegrityError → 必须捕获并返回 `claimed=false`（与 collect-report [device.py:901] 模式一致）。

#### POST /api/device/dm-send-report

```json
// Request
{
  "conversation_id": "uuid",
  "stage": "nurturing",
  "intent": "health_consult",
  "keyword": "养生",
  "content": "你好，..."
}

// Response 200
{ "ok": true }
```

更新 `current_stage`、`intent`、`last_dm_content`、`last_dm_at`、`total_dm_count + 1`。

#### POST /api/device/dm-release-recipient

```json
// Request
{ "conversation_id": "uuid" }

// Response 200
{ "released": true }
```

DM 发送失败时调用，删除会话记录（原子回滚）。**必须校验 `device_id`**：仅当 `conversation.device_id == authed_device_id` 时才删除，防止设备 A 的失败释放误删设备 B 的成功会话（与 comment-claim-release [device.py:750] 模式一致）。

### 2.3 claim 超时恢复

`conversations` 表增加 `claimed_at` 字段（DateTime, nullable）。设备 claim 时写入当前时间。

`claim_channel_item` 的 stale recovery（[channel_service.py:134-146]）已处理 ChannelItem 超时。`conversations` 同理：定时任务或 `dm-claim-recipient` 被调用时，清理 `claimed_at < now - 30min` 且 `status = 'active'` 且 `last_dm_at IS NULL` 的孤儿会话（设备 claim 后崩溃未发送）。

### 2.2 管理端（3 个端点）

全部需要 `verify_admin_token`。路由文件：`server/app/routers/data.py`（新建）。

#### GET /api/data/comments

Query: `?keyword=&account_id=&search=&task_id=&skip=0&limit=50`

返回结构：`{ items: [...], total: N }`

#### GET /api/data/users

Query: `?keyword=&search=&task_id=&skip=0&limit=50`

返回结构：`{ items: [...], total: N }`

#### GET /api/data/conversations

Query: `?account_id=&stage=&status=&search=&task_id=&skip=0&limit=50`

返回结构：`{ items: [...], total: N }`

### 2.3 WS 事件

数据入库后推送（广播位置：`collect-report` 端点、`dm-send-report` 端点、`dm-claim-recipient` 端点）：

```json
// 新评论
{ "event": "data_changed", "type": "comment", "id": "..." }

// 新用户
{ "event": "data_changed", "type": "user", "id": "..." }

// 私信会话变更
{ "event": "data_changed", "type": "conversation", "id": "..." }
```

---

## 3. 设备端改造

### reply-comment.js

在 `_sendDM()` 前后增加：

```javascript
// 1. 发前 claim
var claimResult = apiClient.claimDMRecipient({
  account_id: task.params.account_id,
  recipient_douyin_id: userData.douyin_id,
  recipient_nickname: userData.nickname,
});
if (!claimResult.claimed) {
  logger.info(TAG, "该用户已被其他设备 DM，跳过: " + userData.nickname);
  return false;
}

// 2. 发送 DM
var sent = this._doSendDM(content);

// 3. 上报或释放
if (sent) {
  apiClient.reportDMSend({
    conversation_id: claimResult.conversation_id,
    stage: stage,
    intent: intent,
    keyword: task.params.keyword,
    content: content,
  });
} else {
  apiClient.releaseDMRecipient({ conversation_id: claimResult.conversation_id });
}
```

### api-client.js

新增 3 个方法：

```javascript
claimDMRecipient: function (data) {
  return this.post("/api/device/dm-claim-recipient", data);
},
reportDMSend: function (data) {
  return this.post("/api/device/dm-send-report", data);
},
releaseDMRecipient: function (data) {
  return this.post("/api/device/dm-release-recipient", data);
},
```

---

## 4. 前端

### 4.1 路由 & 菜单

- 路径：`/data`
- 菜单：左侧「数据中心」（图标：database/chart）
- 组件：`web/src/views/DataCenterPage.vue`

### 4.2 页面布局

```
┌─────────────────────────────────────────────────┐
│  [评论采集] [用户资料] [私信会话]                  │  ← Tabs
│                                                  │
│  筛选：关键词[____] 账号[____] [搜索]              │  ← 筛选栏
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │ 表格 / 卡片列表                            │   │
│  │ ...                                       │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  第 1/10 页  [←] [→]                            │  ← 分页
└─────────────────────────────────────────────────┘
```

Tab 切换通过 URL query：`/data?tab=conversations&task_id=xxx`

### 4.3 三个 Tab

**评论采集（comments）**
- DataTable：昵称、内容（截断50字）、关键词、点赞数、回复数、IP属地、是否作者、采集时间
- 筛选：关键词、账号
- 搜索：内容模糊匹配
- 行内展开：完整内容

**用户资料（users）**
- 卡片网格：首字头像、昵称、抖音ID、获赞/关注/粉丝/作品数、性别、IP属地
- 筛选：关键词
- 搜索：昵称/抖音ID
- 点击卡片：展开完整信息弹窗

**私信会话（conversations）**
- 卡片列表：收信人首字头像、昵称、抖音ID、阶段 badge、意图、最后消息预览、发送时间
- 筛选：阶段、账号
- 搜索：昵称/内容模糊
- 点击卡片：会话时间线（所有 DM 记录 + 回复状态）
- 阶段 badge 颜色：qualifying=蓝、nurturing=绿、converting=橙、follow_up=紫

### 4.4 任务详情联动

任务列表点击行 → 详情弹窗底部「产出数据」区块：

| 任务类型 | 展示内容 | 跳转 |
|---------|---------|------|
| search_comment / collect | 采集到的评论数 + 前 5 条预览 | 点击→数据中心评论 Tab，筛选该 task_id |
| reply_comment | 回复数 / 关注数 / 私信数 | 分别跳转对应 Tab |
| search_dm | 创建的会话数 | 点击→数据中心私信 Tab |

跳转：`router.push('/data?tab=comments&task_id=xxx')`

### 4.5 WS 实时更新

```javascript
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'data_changed') {
      // 更新对应 Tab 的未读计数 badge
      newDataCount.value[msg.type]++
    }
  }
})
```

Tab 切换时重置计数并刷新列表。

---

## 5. 服务端文件清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `server/app/db_models.py` | 修改 | 新增 `Conversation` 模型 |
| `server/app/models.py` | 修改 | 新增 Pydantic 请求/响应模型 |
| `server/app/routers/data.py` | 新建 | 管理端 3 个查询接口 |
| `server/app/routers/device.py` | 修改 | 新增设备端 3 个 DM 接口 + WS 广播 |

## 6. 前端文件清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `web/src/views/DataCenterPage.vue` | 新建 | 主页面（3 Tab） |
| `web/src/components/business/CommentTab.vue` | 新建 | 评论采集 Tab |
| `web/src/components/business/UserTab.vue` | 新建 | 用户资料 Tab |
| `web/src/components/business/ConversationTab.vue` | 新建 | 私信会话 Tab |
| `web/src/components/business/ConversationDetail.vue` | 新建 | 会话详情弹窗 |
| `web/src/api/data.js` | 新建 | 数据中心 API |
| `web/src/router/index.js` | 修改 | 新增 /data 路由 |
| `web/src/constants/navigation.js` | 修改 | 新增菜单项 |
| `web/src/views/TasksPage.vue` | 修改 | 任务详情弹窗增加「产出数据」 |
