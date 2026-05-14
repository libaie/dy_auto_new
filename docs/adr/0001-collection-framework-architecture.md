# ADR-0001: 采集框架架构 — 当前状态与改进路线

**Date**: 2026-05-14
**Status**: proposed
**Deciders**: xxy2026

## Context

dy_auto 的数据采集系统经历多轮迭代，从最初单一的 `reply-comment.js` 拆分出独立的 `search-collect.js`（数据采集）和 `reply-comment.js`（评论回复+关注+私信），并抽取了共享模块 `comment-utils.js`。系统运行在 Android AutoJS 上，通过无障碍服务操控抖音 UI，经过搜索→视频→评论区→用户主页的链路完成数据采集。

当前系统的核心链路工作正常（254条评论、102个用户已入库），但框架层面存在架构债务，影响可维护性和容错能力。

## 当前架构

```
device/handlers/
├── base-handler.js          ← 底层: 选择器查找链(_findChildBySelector + 6 helpers)
├── search-base.js           ← 搜索导航基类 (extends BaseHandler)
├── comment-utils.js         ← 共享工具 (openComments/parseCommentItem/parseTime/collectProfileData)
│                               ⚠️ 内嵌了 base-handler 的 _findChildBySelector 链 (~170行重复)
├── search-collect.js        ← 数据采集 (extends SearchBaseHandler, 264行)
└── reply-comment.js         ← 评论回复+关注+私信 (extends SearchBaseHandler, 1102行)

server/app/routers/device.py ← /collect-report, /user-profile, /user-avatar
server/app/db_models.py      ← CollectedComment, CollectedUser
```

### 数据流

```
搜索关键词 → 视频列表 → 打开评论区 → for each 评论:
  1. parseCommentItem()     ← comment-utils
  2. 本地预过滤              ← comment-utils.localPreFilter
  3. AI 语义打分             ← aiAnalyzer.analyzeComment → /api/device/ai-proxy → LLM
  4. 采集评论数据            ← search-collect._collectCommentData
  5. 如果新用户:
     a. 点击头像 → 用户主页
     b. collectProfileData  ← comment-utils (字段提取 + 数字清洗 + 头像裁剪)
     c. back() → 重新打开评论区
  6. POST /api/device/collect-report  ← 单条上报 (评论+用户一起)
```

## 发现的问题（按严重度排序）

### P0: comment-utils.js 与 base-handler.js 选择器逻辑重复

`comment-utils.js:330-498` 复制了 BaseHandler 的完整 `_findChildBySelector` 链（7个函数，~170行）。任何选择器策略的 bug 修复或功能增强（如新增 nav 类型、match_mode）都需要改两处。

**影响**：未来选择器系统升级时，comment-utils 的静态副本会行为不一致。历史上已发生过一次——第一版 `_findChildBySelector` 调用了不存在的 `uiOperator._findBySelector()`。

### P1: AI 服务不可用时采集全部静默失败

`search-collect.js:160-168` 的 `_aiQualify` 在 AI 调用失败时返回 false，导致该评论被跳过。如果 AI 代理服务暂时不可用（网络抖动、LLM 限流），**所有评论都被静默跳过**，采集数为 0。

**实际风险**：移动 4G 网络下一次超时就可能导致整个视频的采集结果为空。日志只有 `logger.warn(TAG, "AI分析失败")`。

### P2: 逐条 HTTP POST 上报，无批量机制

`search-collect.js:212-217` 的 `_reportCollection` 每采集一条评论就发一次 HTTP POST。按 50 条/视频、5 个视频计算，单次任务产生 250 次 HTTP 请求。

### P3: _interactWithVideo 单体函数过长

`search-collect.js:14-147` 的 `_interactWithVideo` 是一个 134 行的函数，混合了滚动控制（3个停止条件）、评论解析+去重、AI 过滤、评论数据采集、用户数据采集（点击头像→主页→采集→返回）、评论区重开、计数器更新。

### P4: SearchBaseHandler.execute() 为死代码

`search-base.js:25` 定义了 `execute()` 方法，但 `search-collect.js:219` 和 `reply-comment.js:146` 都定义了自己的 `execute()`，完全不调用父类。

### P5: 无 AI 降级策略

当 AI 连续失败超过阈值时，没有降级到"全量采集"或"仅本地过滤"模式。

## 改进建议

### R1: 选择器逻辑去重 — comment-utils 接受 handler 引用

不在 comment-utils 中复制选择器逻辑，让 `parseCommentItem` 接受可选的 handler 参数：

```javascript
// comment-utils.js
parseCommentItem: function (item, handler) {
    var findChild = (handler && handler._findChildBySelector) 
        ? function(p, a) { return handler._findChildBySelector(p, a); }
        : _findChildBySelector;  // 独立模式兜底
    var extractVal = (handler && handler._extractChildValue)
        ? function(el, a, fb) { return handler._extractChildValue(el, a, fb); }
        : _extractChildValue;
    // ... 其余逻辑不变
}
```

**收益**：消除 170 行重复代码。选择器逻辑单点维护。
**成本**：所有调用点需传入 `this`。约 3 处修改。

### R2: AI 降级模式

在 `_aiQualify` 中追踪连续 AI 失败次数。当 >= 3 次连续失败时，切换到"全量采集"模式。

```javascript
SearchCollectHandler._aiQualify = function (comment) {
    if (!comment || !comment.text) return false;
    if (!commentUtils.localPreFilter(comment.text)) return false;
    if (this._aiConsecutiveFailures >= 3) return true;  // 降级

    try {
        var result = aiAnalyzer.analyzeComment({...});
        if (result && typeof result.score === "number") {
            this._aiConsecutiveFailures = 0;
            return result.score >= 50;
        }
    } catch (e) { /* log */ }
    this._aiConsecutiveFailures = (this._aiConsecutiveFailures || 0) + 1;
    return false;
};
```

**收益**：AI 不可用时采集不中断。在 task result 中标记 `ai_degraded: true` 供后端后续过滤。

### R3: 批量上报

积累 10-20 条评论后批量 POST。用户访问主页时立即 flush。

**收益**：HTTP 请求量减少 90%+。需服务端扩展 `/collect-report` 支持批量。

### R4: 拆分 _interactWithVideo

提取 `_shouldStopScrolling()`、`_processCommentItem()`、`_visitAndCollectUser()` 三个独立方法。

### R5: 统一 execute() 入口

将 SearchBaseHandler.execute() 作为模板方法，子类只实现差异化方法。

## 优先级排序

| 优先级 | 建议 | 原因 |
|--------|------|------|
| **立即** | R1 (去重) | 消除架构债务根源，防止后续 bug |
| **立即** | R2 (降级) | AI 不可用时采集归零是生产级 bug |
| **本迭代** | R4 (拆分) | 降低调试成本，改动最小 |
| **下迭代** | R3 (批量) | 需服务端配合 |
| **下迭代** | R5 (统一入口) | 纯清理，不影响功能 |

## Consequences

### Positive
- **R1**: 选择器逻辑单点维护，bug 修复一劳永逸
- **R2**: 采集鲁棒性大幅提升，网络波动不丢数据
- **R3**: 网络开销降低 90%，设备端省电
- **R4**: 调试效率提升，新人能快速理解数据流

### Negative
- **R1**: 引入 handler 参数增加接口耦合度
- **R3**: 批量上报崩溃时可能丢失未 flush 的批次（可通过定期 flush 缓解）

### Risks
- **R1 风险**: handler 为 null 时独立模式兜底已存在且验证通过 — 低风险
- **R2 风险**: 降级模式采集低质量评论 → 标记 `ai_degraded`，后端可过滤
