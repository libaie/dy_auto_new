# 多控件页面检测 + 流程上下文 — 设计规格

**日期**: 2026-05-15
**状态**: accepted

## 背景

当前设备端页面判定依赖单控件检测（`findElement("is_video_view")`），存在两个根本问题：

1. **控件不足以区分页面**：视频详情页在搜索流和个人主页流中控件完全一样，单控件判定无法区分
2. **代码中散落 AI 臆造的硬编码定位**：`id("text1")`、`id("et7")` 等无效代码

## 核心设计：双层判定

```
第一层：页面检测（page-detector） → "我现在看到的是什么页面？"
第二层：流程上下文（flow-context） → "我是在什么业务环节来到这个页面的？"
```

两层组合才唯一确定当前系统状态。

### 原则

- **结果驱动，不依赖意图**：不做"我点了所以到了"，必须先检测页面确认到达，再标记上下文
- **page-detector 数据来自服务端**：复用现有 selector action_name 体系，管理后台配置
- **flow-context 纯运行时**：不依赖服务端，设备端内存状态机

---

## 第一层：多控件页面检测

### 页面定义

每个页面由 N 个控件的**同时存在**来判定（AND 逻辑）：

| page_name | required_elements | 说明 |
|-----------|-------------------|------|
| search | ["is_search_view"] | 搜索输入页 |
| search_result_list | ["search_video_list", "search_video_tab"] | 搜索结果列表 |
| video | ["is_video_view"] | 视频详情页（控件层面不区分子类型） |
| comment | ["is_comment_view"] | 评论面板（可叠加） |
| profile | ["user_nickname"] | 个人主页 |
| dm | ["dm_input"] | 私信页 |
| feed | ["like_button"] | 推荐页（兜底） |

### 服务端

新增 `page_detectors` 表：

```sql
CREATE TABLE page_detectors (
    id TEXT PRIMARY KEY,
    page_name TEXT NOT NULL,
    required_elements TEXT NOT NULL,   -- JSON array of action_names
    platform_version TEXT DEFAULT 'default',
    priority INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);
```

管理后台新增页面检测器配置页，CRUD 操作。

API：
- `GET /api/page-detectors` — 设备端拉取全量配置
- `POST /api/page-detectors` — admin 创建
- `PUT /api/page-detectors/{id}` — admin 更新
- `DELETE /api/page-detectors/{id}` — admin 删除

`required_elements` 中引用的 action_name 必须在 selectors 表中已存在。

### 设备端

新增 `device/core/page-detector.js`：

```javascript
var pageDetector = {
  _pages: {},  // page_name → { required_elements, priority }

  init: function(configs) {
    // 从服务端拉取后缓存
  },

  isOnPage: function(pageName, timeout) {
    // 所有 required_elements 同时 findElement 命中 → true
    timeout = timeout || 800;
    var page = this._pages[pageName];
    for (var i = 0; i < page.required_elements.length; i++) {
      if (!uiOperator.findElement(page.required_elements[i], timeout)) {
        return false;
      }
    }
    return true;
  },

  detectPage: function() {
    // 按 priority 升序遍历所有页面，返回第一个匹配的 page_name
    // 无匹配返回 null（弹窗/未知页面）
  },
};
```

### 替换计划

| 文件 | 当前写法 | 替换为 |
|------|---------|--------|
| search-base.js:166 | `findElement("is_search_view")` | `pageDetector.isOnPage("search")` |
| search-comment.js:35 | `findElement("is_video_view")` | `pageDetector.isOnPage("video")` |
| reply-comment.js:16-23 | 本地 `PAGE_DETECTORS` | 删除，改用 `pageDetector.detectPage()` |
| search-collect.js 各处 | `findElement("is_comment_view")` 等 | `pageDetector.isOnPage("comment")` |

---

## 第二层：流程上下文

### 状态机

```
                   ┌─ _openSearch 确认到达 ──→ [search]
                   │      │
                   │      └─ 确认进入视频 ──→ [search_video]
                   │              │
                   │              ├─ back → [search]
                   │              ├─ 误触 → 仍是控件层的 video，但上下文是 search_video
                   │              └─ 任务结束 → [idle]
                   │
[idle] ────────────┤
                   │  _enterCommenterProfile 确认到达
                   │      └────────────────→ [profile]
                   │              │
                   │              ├─ 误触作品视频 → video 控件可见但上下文是 profile
                   │              │        → 检测到 video + profile 上下文 → 立即 back
                   │              ├─ _sendDM 确认到达 → [dm]
                   │              └─ _returnToComments 确认到达 → [comment]
                   │
                   └─ nurture._ensureOnFeed() 确认到达 → [feed]
```

### 实现

新增 `device/core/flow-context.js`：

```javascript
var flowContext = {
  _current: "idle",

  enter: function(state) {
    // 仅在调用方已确认到达目标页后调用
    this._current = state;
  },

  is: function(state) {
    return this._current === state;
  },

  reset: function() {
    this._current = "idle";
  },
};
```

### 使用模式

Handler 中的关键调用点：

```javascript
// 搜索流：确认进入视频后才标记
this._clickSearchResult(0);
sleep(2000);
if (pageDetector.isOnPage("video")) {
    flowContext.enter("search_video");
} else {
    // 重试或报错
}

// 个人主页流：确认进入主页后才标记
this._enterCommenterProfile(avatarEl, nickname);
if (pageDetector.isOnPage("profile")) {
    flowContext.enter("profile");
}

// 视频详情页的关键操作前：校验上下文
if (pageDetector.isOnPage("video")) {
    if (flowContext.is("search_video")) {
        // 正常：打开评论区、切下一个视频
    } else if (flowContext.is("profile")) {
        // 误触：立即 back
        back(); sleep(500);
        return;
    }
}
```

---

## 加固措施

| 风险 | 对策 |
|------|------|
| 页面加载延迟导致 enter 失败 | `enter()` 调用方给 3s 重试窗口，超时标记 `unknown` 触发恢复 |
| 意外弹窗打断 detect | `detectPage()` 返回 null 时，先 `safeClick` 关闭弹窗再重检测 |
| 上下文与页面不匹配 | 关键操作前轻量校验：`detectPage()` 结果是否符合 `flowContext._current` |
| 恢复失败 | back 5 次不在任何已知页 → 回首页冷启动兜底，标记 `idle` |

---

## 验证

1. 搜索采集流程：`search → search_result_list → search_video → comment` 链条完整
2. 评论回复流程：`search → search_video → comment → profile → dm → comment` 链条完整
3. 个人主页误触检测：`profile → profile_video` 页面检测 + 上下文校验，触发 back
4. 弹窗中断恢复：弹出系统权限弹窗 → `detectPage()` 返回 null → 关闭弹窗 → 重新检测
