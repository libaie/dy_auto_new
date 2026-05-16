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
- **复用现有选择器系统**：不新建表、不新建 API，选择器加 `purpose` 字段区分"动作"和"页面检测"
- **flow-context 纯运行时**：不依赖服务端，设备端内存状态机

---

## 第一层：多控件页面检测

### 服务端：选择器 `purpose` 扩展

`SelectorConfig` 模型加一个字段：

```python
class SelectorConfig(BaseModel):
    action_name: str
    platform_version: str = "default"
    strategies: list[SelectorStrategy]
    version: int = 1
    purpose: str = "action"    # 新增: "action"(默认) | "page_detect"
```

`purpose: "page_detect"` 的选择器，设备端 AND 逻辑——所有策略必须同时命中才算页面匹配。现有 `purpose: "action"` 的选择器保持 OR 逻辑（优先级匹配）不变。

管理后台选择器管理页加一个 `purpose` 下拉选项，同一页面管理动作和页面检测，不需要新建表、不需要新管理页。

### 页面定义

| priority | action_name | purpose | strategies（AND 逻辑） | 说明 |
|----------|-------------|---------|----------------------|------|
| 0 | comment | page_detect | ["is_comment_view"] | 评论面板（最先检测，叠在任何页面之上） |
| 1 | dm | page_detect | ["dm_input"] | 私信页 |
| 2 | profile | page_detect | ["user_nickname"] | 个人主页 |
| 3 | search | page_detect | ["is_search_view"] | 搜索输入页 |
| 4 | search_result_list | page_detect | ["search_video_list", "search_video_tab"] | 搜索结果列表 |
| 5 | video | page_detect | ["is_video_view"] | 视频详情页（控件层面不区分子类型） |
| 6 | dialog | page_detect | ["system_dialog_close"] | 系统弹窗/权限对话框 |
| 7 | feed | page_detect | ["like_button"] | 推荐页（最后兜底） |

priority 规则：叠层页面排在底层页面之前。`comment` > `video`（评论区遮在视频之上），`dialog` > `feed`（弹窗遮住推荐流），`feed` 最后（`like_button` 几乎所有视频播放页都可见）。

`strategies` 中每一项是一个已有的 action_name（如 `is_search_view`），引用现有 selector 配置。页面检测不定义新的图像模板/控件定位，完全复用已有 selector。

### 设备端

`ui-operator.js` 加一个 `isOnPage(actionName)` 方法：

```javascript
isOnPage: function(actionName, timeout) {
    timeout = timeout || 800;
    var config = selectorLoader.get(actionName);
    if (!config || config.purpose !== "page_detect") return false;
    for (var i = 0; i < config.strategies.length; i++) {
        // 每个 strategy 是一个已知的 action_name，复用它来查找
        if (!this.findElement(config.strategies[i].value, timeout)) {
            return false;
        }
    }
    return true;
},

detectPage: function() {
    // 遍历所有 purpose="page_detect" 的选择器，按 priority 升序
    // 返回第一个 isOnPage 命中的 action_name
    // 无匹配返回 null
},
```

### 替换计划

| 文件 | 当前写法 | 替换为 |
|------|---------|--------|
| search-base.js:166 | `findElement("is_search_view")` | `isOnPage("search")` |
| search-comment.js:35 | `findElement("is_video_view")` | `isOnPage("video")` |
| reply-comment.js:16-23 | 本地 `PAGE_DETECTORS` | 删除，改用 `detectPage()` + `isOnPage()` |
| search-collect.js 各处 | `findElement("is_comment_view")` 等 | `isOnPage("comment")` |

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

```javascript
// 搜索流：确认进入视频后才标记
this._clickSearchResult(0);
sleep(2000);
if (uiOperator.isOnPage("video")) {
    flowContext.enter("search_video");
}

// 个人主页流：确认进入主页后才标记
this._enterCommenterProfile(avatarEl, nickname);
if (uiOperator.isOnPage("profile")) {
    flowContext.enter("profile");
}

// 视频详情页的关键操作前：校验上下文
if (uiOperator.isOnPage("video")) {
    if (flowContext.is("search_video")) {
        // 正常：打开评论区、切下一个视频
    } else if (flowContext.is("profile")) {
        // 误触：立即 back
        back(); sleep(500);
        return;
    }
}
```

### 注入点

| 文件 | 注入点 | 上下文 |
|------|--------|--------|
| search-base.js | `_clickSearchResult(0)` 后确认 | `search_video` |
| search-base.js | `_openSearch()` 后确认 | `search` |
| search-collect.js | `_clickSearchResult(0)` 后确认 | `search_video` |
| search-collect.js | `_openComments()` 后确认 | `comment` |
| reply-comment.js | 评论区打开后确认 | `comment` |
| reply-comment.js | `_enterCommenterProfile()` 后确认 | `profile` |
| reply-comment.js | `_sendDM()` 进入私信页后确认 | `dm` |
| reply-comment.js | `_returnToComments()` 回到评论面板后确认 | `comment` |
| nurture.js | `_ensureOnFeed()` 确认后 | `feed` |

---

## 加固措施

| 风险 | 对策 |
|------|------|
| 页面加载延迟导致 enter 失败 | `enter()` 调用方给 3s 重试窗口，超时标记 `unknown` 触发恢复 |
| 意外弹窗打断 detect | `detectPage()` 返回 `"dialog"` 时，先 `safeClick("dialog_close")` → `detectPage()` 重检测 |
| 上下文与页面不匹配 | 关键操作前轻量校验：`detectPage()` 结果是否符合 `flowContext._current` |
| 恢复失败 | back 5 次不在任何已知页 → 回首页冷启动兜底，标记 `idle` |

---

## 实现清单

| 层 | 改动 | 文件 |
|---|------|------|
| 服务端 | `SelectorConfig` 加 `purpose` 字段 | `server/app/models.py` |
| 服务端 | `selector` 表加 `purpose` 列 | `server/app/db_models.py` |
| 设备端 | `ui-operator.js` 加 `isOnPage()` + `detectPage()` | `device/core/ui-operator.js` |
| 设备端 | 新增 `flow-context.js` | `device/core/flow-context.js` |
| 设备端 | 替换硬编码页面判定 | search-base.js, search-comment.js, reply-comment.js, search-collect.js, nurture.js |

## 验证

1. 搜索采集流程：`search → search_result_list → search_video → comment` 链条完整
2. 评论回复流程：`search → search_video → comment → profile → dm → comment` 链条完整
3. 个人主页误触检测：`profile → profile_video` 页面检测 + 上下文校验，触发 back
4. 弹窗中断恢复：弹出系统权限弹窗 → `detectPage()` 返回 `"dialog"` → 关闭弹窗 → 重新检测
