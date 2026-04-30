# 阶段三：核心任务处理器 实施计划

> **给智能体工人：** 必须使用子技能：superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实施此计划。步骤使用 checkbox（`- [ ]`）语法跟踪进度。

**目标：** 实现 4 个核心任务处理器（search_comment、search_like、search_dm、reply_comment），使设备端能执行搜索+互动的完整工作流。

**架构：** 所有搜索类 handler 共享 `SearchBaseHandler`（搜索导航逻辑），各自只实现互动部分。`ReplyCommentHandler` 不需要搜索，直接在评论页面操作。每个 handler 返回 `{ success, result, error }`，由 `task-executor.js` 统一调度。

**技术栈：** AutoJS6 JavaScript（设备端），选择器配置通过 `selectors.yaml` 管理

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `device/handlers/search-base.js` | 新建 | 搜索导航基类：打开搜索、输入关键词、打开结果视频 |
| `device/handlers/search-comment.js` | 新建 | 搜索后评论 handler |
| `device/handlers/search-like.js` | 新建 | 搜索后点赞 handler |
| `device/handlers/search-dm.js` | 新建 | 搜索后私信 handler |
| `device/handlers/reply-comment.js` | 新建 | 评论回复 handler |
| `device/core/task-executor.js` | 修改 | 注册 4 个新 handler |
| `server/config/selectors.yaml` | 修改 | 添加 comment_item、comment_reply 相关选择器 |

---

## Task 1：补充选择器配置

**文件：**
- 修改: `server/config/selectors.yaml`

在 `selectors.yaml` 末尾（`dm_send` 之后）添加评论回复和视频作者头像选择器：

- [ ] **步骤 1：添加选择器**

```yaml
  - action_name: "comment_reply_button"
    strategies:
      - { type: "text", value: "回复", priority: 1 }
      - { type: "desc", value: "回复", priority: 2 }

  - action_name: "video_author_avatar"
    strategies:
      - { type: "desc", value: "头像", priority: 1 }
      - { type: "id", value: "com.ss.android.ugc.aweme:id/author_avatar", priority: 2 }
      - { type: "coordinate", x_percent: 0.9, y_percent: 0.6, priority: 3 }
```

- [ ] **步骤 2：重启服务端加载新选择器**

```bash
cd server && python -m app.seed
```

预期：输出 `Seed complete: ... X selectors added, Y selectors updated`

- [ ] **步骤 3：提交**

```bash
git add server/config/selectors.yaml
git commit -m "feat(config): add comment/reply selectors for Phase 3 handlers"
```

---

## Task 2：搜索基类 SearchBaseHandler

**文件：**
- 新建: `device/handlers/search-base.js`

- [ ] **步骤 1：创建搜索基类**

```javascript
// device/handlers/search-base.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "SEARCH_BASE";

/**
 * 搜索基类 — 所有搜索类 handler 继承此对象
 * 提供通用的搜索导航逻辑，子类只需实现 _interactWithVideo()
 */
var SearchBaseHandler = Object.create(BaseHandler);

/**
 * 执行搜索+互动流程
 * @param {Object} params
 *   - keyword: string (搜索关键词)
 *   - count: number (操作数量)
 *   - content: string (可选，评论/私信内容)
 * @returns {Object} { success, result, error }
 */
SearchBaseHandler.execute = function (params) {
  var keyword = params.keyword;
  var count = params.count || 5;
  var content = params.content || "";

  if (!keyword) {
    return { success: false, error: "Missing keyword" };
  }

  logger.info(TAG, "Searching: '" + keyword + "', count=" + count);

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  // 1. 进入搜索页
  if (!this._openSearch()) {
    return { success: false, error: "Failed to open search" };
  }

  // 2. 输入关键词
  if (!this._inputKeyword(keyword)) {
    return { success: false, error: "Failed to input keyword" };
  }

  // 3. 点击搜索按钮
  if (!this._submitSearch()) {
    return { success: false, error: "Failed to submit search" };
  }

  // 等待搜索结果加载
  sleep(3000);

  // 4. 逐个打开结果并互动
  var stats = { success_count: 0, fail_count: 0, details: [] };

  for (var i = 0; i < count; i++) {
    logger.info(TAG, "Processing result " + (i + 1) + "/" + count);

    // 点击第 i 个搜索结果
    if (!this._clickSearchResult(i)) {
      logger.warn(TAG, "Failed to click result " + (i + 1) + ", skipping");
      stats.fail_count++;
      continue;
    }

    sleep(2000); // 等待视频加载

    // 子类实现的互动逻辑
    var interactResult = this._interactWithVideo(content, stats);
    if (interactResult) {
      stats.success_count++;
    } else {
      stats.fail_count++;
      // 互动失败时清理页面状态，确保回到搜索结果
      this._goBack();
      sleep(1000);
    }

    // 返回搜索结果列表
    this._goBack();
    sleep(1500);

    // 反检测随机停顿
    antiDetect.maybePause();
  }

  logger.info(TAG, "Search complete. " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 打开搜索页
 * 先尝试直接点击搜索入口，失败则 back() 后重试
 */
SearchBaseHandler._openSearch = function () {
  // 先直接尝试点击搜索入口（当前可能已在首页）
  var clicked = this.safeClick("search_tab", 1);
  if (clicked) {
    sleep(1500);
    return true;
  }

  // 搜索入口找不到，可能在子页面，back() 回退后重试
  back();
  sleep(1500);

  clicked = this.safeClick("search_tab", 3);
  if (clicked) {
    sleep(1500);
    return true;
  }
  return false;
};

/**
 * 在搜索框输入关键词
 */
SearchBaseHandler._inputKeyword = function (keyword) {
  var inputResult = this.safeInput("search_input", keyword);
  if (inputResult) {
    sleep(500);
    return true;
  }
  return false;
};

/**
 * 点击搜索按钮
 */
SearchBaseHandler._submitSearch = function () {
  return this.safeClick("search_button", 3);
};

/**
 * 点击第 index 个搜索结果
 * 搜索结果列表中，每个结果通常是一个可点击的卡片
 */
SearchBaseHandler._clickSearchResult = function (index) {
  // 搜索结果列表中，点击第 index 个结果
  // 抖音搜索结果是垂直列表，每个结果占据大部分屏幕
  // 使用滑动定位 + 点击的方式
  if (index > 0) {
    // 先滑动到目标位置
    for (var i = 0; i < index; i++) {
      uiOperator.swipeUp();
      sleep(1000);
    }
  }

  // 点击屏幕中间区域打开视频
  var x = Math.round(device.width * 0.5);
  var y = Math.round(device.height * 0.4);
  return click(x, y);
};

/**
 * 返回上一页
 */
SearchBaseHandler._goBack = function () {
  back();
  sleep(1000);
};

/**
 * 搜索关键词并打开第一个结果视频
 * 供 ReplyCommentHandler 等不需要遍历多个结果的场景使用
 * @param {string} keyword - 搜索关键词
 * @returns {boolean} 是否成功打开视频
 */
SearchBaseHandler.searchAndOpenFirstResult = function (keyword) {
  if (!this._openSearch()) return false;

  if (!this._inputKeyword(keyword)) return false;

  if (!this._submitSearch()) return false;

  sleep(3000);

  // 点击第一个结果
  if (!this._clickSearchResult(0)) return false;

  sleep(2000);
  return true;
};

/**
 * 互动逻辑（子类必须实现）
 * @param {string} content - 评论/私信内容
 * @param {Object} stats - 统计对象
 * @returns {boolean} 是否成功
 */
SearchBaseHandler._interactWithVideo = function (content, stats) {
  throw new Error("_interactWithVideo() not implemented");
};

module.exports = SearchBaseHandler;
```

- [ ] **步骤 2：提交**

```bash
git add device/handlers/search-base.js
git commit -m "feat(device): add SearchBaseHandler with search navigation logic"
```

---

## Task 3：搜索评论 Handler

**文件：**
- 新建: `device/handlers/search-comment.js`

- [ ] **步骤 1：创建搜索评论 handler**

```javascript
// device/handlers/search-comment.js
var SearchBaseHandler = require("./search-base");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "SEARCH_COMMENT";

/**
 * 搜索评论 Handler
 * params:
 *   - keyword: string (搜索关键词)
 *   - count: number (评论数量)
 *   - content: string (评论内容)
 */
var SearchCommentHandler = Object.create(SearchBaseHandler);

/**
 * 对当前视频发表评论
 */
SearchCommentHandler._interactWithVideo = function (content, stats) {
  if (!content) {
    logger.warn(TAG, "No comment content provided");
    return false;
  }

  // 1. 点击评论区域打开评论面板
  var commentClicked = this.safeClick("comment_input", 3);
  if (!commentClicked) {
    logger.warn(TAG, "Failed to open comment panel");
    return false;
  }

  sleep(1500);

  // 2. 输入评论内容
  var inputResult = this.safeInput("comment_input", content);
  if (!inputResult) {
    logger.warn(TAG, "Failed to input comment text");
    return false;
  }

  sleep(500);

  // 3. 点击发送
  var submitClicked = this.safeClick("comment_submit", 3);
  if (!submitClicked) {
    logger.warn(TAG, "Failed to submit comment");
    return false;
  }

  sleep(1000);

  logger.info(TAG, "Comment posted: '" + content.substring(0, 20) + "...'");
  stats.details.push("commented: " + content.substring(0, 30));
  return true;
};

module.exports = SearchCommentHandler;
```

- [ ] **步骤 2：提交**

```bash
git add device/handlers/search-comment.js
git commit -m "feat(device): add SearchCommentHandler"
```

---

## Task 4：搜索点赞 Handler

**文件：**
- 新建: `device/handlers/search-like.js`

- [ ] **步骤 1：创建搜索点赞 handler**

```javascript
// device/handlers/search-like.js
var SearchBaseHandler = require("./search-base");
var logger = require("../utils/logger");

var TAG = "SEARCH_LIKE";

/**
 * 搜索点赞 Handler
 * params:
 *   - keyword: string (搜索关键词)
 *   - count: number (点赞数量)
 */
var SearchLikeHandler = Object.create(SearchBaseHandler);

/**
 * 对当前视频点赞
 */
SearchLikeHandler._interactWithVideo = function (content, stats) {
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "Liked video");
    stats.details.push("liked");
    return true;
  }
  logger.warn(TAG, "Failed to like video");
  return false;
};

module.exports = SearchLikeHandler;
```

- [ ] **步骤 2：提交**

```bash
git add device/handlers/search-like.js
git commit -m "feat(device): add SearchLikeHandler"
```

---

## Task 5：搜索私信 Handler

**文件：**
- 新建: `device/handlers/search-dm.js`

- [ ] **步骤 1：创建搜索私信 handler**

```javascript
// device/handlers/search-dm.js
var SearchBaseHandler = require("./search-base");
var uiOperator = require("../core/ui-operator");
var logger = require("../utils/logger");

var TAG = "SEARCH_DM";

/**
 * 搜索私信 Handler
 * params:
 *   - keyword: string (搜索关键词 — 用于搜索用户)
 *   - count: number (私信数量)
 *   - content: string (私信内容)
 */
var SearchDMHandler = Object.create(SearchBaseHandler);

/**
 * 打开搜索结果后，进入用户主页并发送私信
 */
SearchDMHandler._interactWithVideo = function (content, stats) {
  if (!content) {
    logger.warn(TAG, "No DM content provided");
    return false;
  }

  // 1. 点击视频作者头像进入主页
  var avatarClicked = this.safeClick("video_author_avatar", 2);
  if (!avatarClicked) {
    logger.warn(TAG, "Failed to click author avatar");
    return false;
  }
  sleep(2000);

  // 2. 点击私信按钮
  var messageClicked = this.safeClick("message_button", 3);
  if (!messageClicked) {
    logger.warn(TAG, "Failed to click message button");
    return false;
  }

  sleep(1500);

  // 3. 输入私信内容
  var inputResult = this.safeInput("dm_input", content);
  if (!inputResult) {
    logger.warn(TAG, "Failed to input DM text");
    return false;
  }

  sleep(500);

  // 4. 点击发送
  var sendClicked = this.safeClick("dm_send", 3);
  if (!sendClicked) {
    logger.warn(TAG, "Failed to send DM");
    return false;
  }

  sleep(1000);

  logger.info(TAG, "DM sent: '" + content.substring(0, 20) + "...'");
  stats.details.push("dm_sent: " + content.substring(0, 30));
  return true;
};

module.exports = SearchDMHandler;
```

- [ ] **步骤 2：提交**

```bash
git add device/handlers/search-dm.js
git commit -m "feat(device): add SearchDMHandler"
```

---

## Task 6：评论回复 Handler

**文件：**
- 新建: `device/handlers/reply-comment.js`

- [ ] **步骤 1：创建评论回复 handler**

```javascript
// device/handlers/reply-comment.js
var SearchBaseHandler = require("./search-base");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "REPLY_COMMENT";

/**
 * 评论回复 Handler
 * 继承 SearchBaseHandler，复用搜索导航逻辑
 * params:
 *   - keyword: string (搜索关键词，用于找到视频)
 *   - content: string (回复内容)
 *   - count: number (回复数量)
 */
var ReplyCommentHandler = Object.create(SearchBaseHandler);

ReplyCommentHandler.execute = function (params) {
  var keyword = params.keyword;
  var content = params.content;
  var count = params.count || 3;

  if (!content) {
    return { success: false, error: "Missing content" };
  }

  if (!keyword) {
    return { success: false, error: "Missing keyword" };
  }

  logger.info(TAG, "Reply to comments, keyword='" + keyword + "', count=" + count);

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  // 1. 搜索并打开视频（复用基类方法）
  if (!this.searchAndOpenFirstResult(keyword)) {
    return { success: false, error: "Failed to find video" };
  }

  // 2. 打开评论区
  var commentClicked = this.safeClick("comment_input", 3);
  if (!commentClicked) {
    return { success: false, error: "Failed to open comments" };
  }
  sleep(2000);

  // 3. 回复评论
  var stats = { success_count: 0, fail_count: 0, details: [] };

  for (var i = 0; i < count; i++) {
    logger.info(TAG, "Replying to comment " + (i + 1) + "/" + count);

    // 点击评论的回复按钮
    var replyClicked = this.safeClick("comment_reply_button", 2);
    if (!replyClicked) {
      logger.warn(TAG, "Failed to click reply on comment " + (i + 1));
      stats.fail_count++;
      continue;
    }

    sleep(1000);

    // 输入回复内容
    var inputResult = this.safeInput("comment_input", content);
    if (!inputResult) {
      logger.warn(TAG, "Failed to input reply text");
      stats.fail_count++;
      continue;
    }

    sleep(500);

    // 发送
    var submitClicked = this.safeClick("comment_submit", 3);
    if (!submitClicked) {
      logger.warn(TAG, "Failed to submit reply");
      stats.fail_count++;
      continue;
    }

    sleep(1500);
    stats.success_count++;
    stats.details.push("replied: " + content.substring(0, 30));
    logger.info(TAG, "Reply posted (total: " + stats.success_count + ")");

    // 反检测
    antiDetect.maybePause();
  }

  // 返回
  back();
  sleep(1000);

  logger.info(TAG, "Reply complete. " + JSON.stringify(stats));
  return { success: true, result: stats };
};

module.exports = ReplyCommentHandler;
```

- [ ] **步骤 2：提交**

```bash
git add device/handlers/reply-comment.js
git commit -m "feat(device): add ReplyCommentHandler"
```

---

## Task 7：注册 Handler 到 TaskExecutor

**文件：**
- 修改: `device/core/task-executor.js`

- [ ] **步骤 1：注册新 handler**

将 `device/core/task-executor.js` 的 handlers 部分从：

```javascript
var handlers = {
  nurture: require("../handlers/nurture"),
};
```

改为：

```javascript
var handlers = {
  nurture: require("../handlers/nurture"),
  search_comment: require("../handlers/search-comment"),
  search_like: require("../handlers/search-like"),
  search_dm: require("../handlers/search-dm"),
  reply_comment: require("../handlers/reply-comment"),
};
```

- [ ] **步骤 2：提交**

```bash
git add device/core/task-executor.js
git commit -m "feat(device): register all core task handlers in executor"
```

---

## 最终验证

- [ ] **运行服务端测试确认无回归**

```bash
cd server && python -m pytest tests/ -v --tb=short
```

预期：82 个测试全部通过

- [ ] **验证选择器加载**

```bash
cd server && python -c "
from app.database import SessionLocal
from app.services.selector_service import selector_service
db = SessionLocal()
v, sels = selector_service.get_all_selectors(db)
print(f'Version: {v}, Selectors: {len(sels)}')
for s in sels:
    print(f'  - {s[\"action_name\"]}')
db.close()
"
```

预期：输出包含 comment_reply_button、video_author_avatar

- [ ] **设备端冒烟测试**

在 AutoJS6 设备上创建一个测试任务：
```bash
curl -X POST http://server:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-Device-Secret: change-me-to-a-random-string" \
  -d '{"type": "search_comment", "account_id": "acc-001", "params": {"keyword": "美食", "count": 2, "content": "不错哦"}}'
```

预期：设备端执行搜索→找到视频→发送评论→上报结果

---

## 任务汇总

| 任务 | 内容 | 新增/修改 |
|------|------|-----------|
| 1 | 补充选择器配置 | 修改 selectors.yaml (+2 selectors) |
| 2 | 搜索基类 | 新建 search-base.js（含 searchAndOpenFirstResult） |
| 3 | 搜索评论 Handler | 新建 search-comment.js |
| 4 | 搜索点赞 Handler | 新建 search-like.js |
| 5 | 搜索私信 Handler | 新建 search-dm.js（用选择器替代硬编码坐标） |
| 6 | 评论回复 Handler | 新建 reply-comment.js（继承 SearchBaseHandler） |
| 7 | 注册 Handler | 修改 task-executor.js |

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 6 issues fixed |

- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED — ready to implement

### 审查修复清单

| # | 问题 | 修复 |
|---|------|------|
| 1 | ReplyCommentHandler 重复搜索逻辑 (DRY) | 提取 `searchAndOpenFirstResult()` 到基类，ReplyCommentHandler 继承 SearchBaseHandler |
| 2 | `_openSearch()` 无条件 `back()` | 先尝试 safeClick，失败再 back + 重试 |
| 3 | 3 个未使用的选择器 | 只保留 `comment_reply_button`，新增 `video_author_avatar` |
| 4 | `comment_input` 复用 | 保持现状（ID 策略兼容两个场景） |
| 5 | profile 硬编码坐标 | 新增 `video_author_avatar` 选择器，用 safeClick 替代 |
| 6 | 错误清理不一致 | SearchBaseHandler 互动失败后统一 `_goBack()` 清理 |
