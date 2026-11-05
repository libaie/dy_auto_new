// device/handlers/search-dm.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");
var uiOperator = require("../core/ui-operator");
var flowContext = require("../core/flow-context");
var crashRecovery = require("../core/crash-recovery");
var taskCancellation = require("../core/task-cancellation");

var TAG = "搜索私信";

/**
 * 搜索私信 Handler
 * params:
 *   - keyword: string (搜索关键词 — 用于搜索用户)
 *   - count: number (私信数量)
 *   - content: string (私信内容，可选，留空则 AI 根据视频内容生成)
 */
var SearchDMHandler = Object.create(SearchBaseHandler);

/**
 * 打开搜索结果后，进入用户主页并发送私信序列
 * 支持 DM 序列模板、单条内容、AI 生成
 *
 * 页面导航: 视频详情页 → 个人主页 → 私信聊天室 → 发消息 → 回退到视频详情页
 * 确保退出时页面状态与进入前完全一致，避免外层循环在错误的页面继续执行
 */
SearchDMHandler._interactWithVideo = function (content, stats) {
  if (taskCancellation.isCancelled()) return false;
  var params = this._params || {};

  // ==== 消息解析：传入 content 参数优先于 params 静态模板 ====
  // content 为数组 → 完整序列变体（后端AI批量生成无缝透传）
  // content 为字符串 → 单条定制消息
  // content 为空 → 降级读取 params 内的 dm_sequence_id/dm_messages 静态模板
  var messages;
  if (content instanceof Array && content.length > 0) {
    messages = [];
    for (var i = 0; i < content.length; i++) {
      var item = content[i];
      if (typeof item === "string") {
        messages.push({order: messages.length + 1, content: item, delay_ms: 0});
      } else if (item && item.content != null) {
        messages.push(item);
      }
    }
    if (messages.length === 0) {
      messages = this.resolveMessages(params);
    } else {
      logger.info(TAG, "DM使用传入变体序列: " + messages.length + "条 msg1=" + (messages[0].content || "").substring(0, 30));
    }
  } else if (typeof content === "string" && content.trim()) {
    messages = [{order: 1, content: content, delay_ms: 0}];
    logger.info(TAG, "DM使用传入单条内容: " + content.substring(0, 30));
  } else {
    messages = this.resolveMessages(params);
  }

  if (taskCancellation.isCancelled()) return false;
  if (!messages || messages.length === 0) {
    logger.warn(TAG, "无法获取私信内容，跳过");
    return false;
  }

  var navigationDepth = 0;  // 0=视频详情页, 1=个人主页, 2=私信聊天室

  try {
    // 1. 点击视频作者头像进入主页
    var avatarClicked = this.safeClick("video_author_avatar", 2);
    if (!avatarClicked) {
      logger.warn(TAG, "未找到作者头像");
      return false;
    }
    // safeClick 内部 findElement 已做显式等待，无需 sleep 赌页面加载
    navigationDepth = 1;
    flowContext.enter("profile");

    // 2. 点击私信按钮进入聊天室 — 增加重试次数应对弱网
    var messageClicked = this.safeClick("dm_entry_btn", 5);
    if (!messageClicked) {
      logger.warn(TAG, "私信按钮未找到");
      return false;
    }
    // safeClick 已确认元素出现并点击，safeInput 内部 wait 5s 足够聊天室加载
    navigationDepth = 2;
    flowContext.enter("dm");

    // 3. 发送消息序列
    var sentCount = this._sendMessageSequence(messages, stats, params.keyword);
    if (sentCount <= 0) {
      logger.warn(TAG, "私信序列没有成功发送任何消息");
      return false;
    }
    try { apiClient.incrementStats(params.account_id, "search_dm", "", 1); } catch (e) {}
    return true;
  } finally {
    // ==== 页面状态恢复：确保退出时回到视频详情页 ====
    if (navigationDepth >= 2) {
      back(); sleep(800);
      logger.debug(TAG, "back: 私信聊天室 → 个人主页");
    }
    if (navigationDepth >= 1) {
      back(); sleep(800);
      logger.debug(TAG, "back: 个人主页 → 视频详情页");
    }

    if (navigationDepth > 0) {
      var onVideo = uiOperator.isOnPage("is_video_view");
      var onSearch = uiOperator.isOnPage("is_search_view") || uiOperator.isOnPage("search_result_list");
      if (onVideo) {
        flowContext.enter("video");
      } else if (onSearch) {
        flowContext.enter("search");
      } else {
        logger.warn(TAG, "页面恢复异常，当前不在视频/搜索页，触发 crash-recovery");
        crashRecovery.ensureAppRunning();
      }
    }
  }
};

module.exports = SearchDMHandler;
