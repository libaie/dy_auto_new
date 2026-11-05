// device/handlers/search-comment.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var uiOperator = require("../core/ui-operator");
var commentUtils = require("./comment-utils");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");
var taskCancellation = require("../core/task-cancellation");

var TAG = "搜索评论";

/**
 * 搜索评论 Handler
 * params:
 *   - keyword: string (搜索关键词)
 *   - count: number (评论数量)
 *   - content: string (评论内容，可选，留空则 AI 根据视频内容生成)
 */
var SearchCommentHandler = Object.create(SearchBaseHandler);

/**
 * 对当前视频发表评论
 * 优先使用 params.content，留空则 AI 根据视频内容自动生成
 */
SearchCommentHandler._interactWithVideo = function (content, stats) {
  this._lastSendOutcome = "not_attempted";
  if (taskCancellation.isCancelled()) return false;
  // 如果没有提供评论内容，提取视频文本并 AI 生成
  if (!content) {
    var videoText = this._extractVideoText();
    content = aiAnalyzer.generateVideoComment(videoText);
    if (!content) {
      logger.warn(TAG, "AI 生成评论失败，跳过");
      return false;
    }
    logger.info(TAG, "AI 生成评论: '" + content.substring(0, 30) + "'");
  }

  if (taskCancellation.isCancelled()) return false;

  // 0. 确认进入视频详情页
  if (!uiOperator.isOnPage("is_video_view")) {
    if (taskCancellation.isCancelled()) return false;
    logger.info(TAG, "未检测到视频详情页，尝试点击屏幕中心进入");
    press(Math.round(device.width * 0.5), Math.round(device.height * 0.5), 80);
    sleep(2000);
  }
  if (!uiOperator.isOnPage("is_video_view")) {
    logger.warn(TAG, "未进入视频详情页");
    return false;
  }
  var commentBtn = uiOperator.findElement("video_comment_btn", 3000);
  if (!commentBtn) {
    logger.warn(TAG, "评论入口按钮未找到");
    return false;
  }

  // 预检评论数：零评论视频点评论按钮会直接唤起键盘，跳过
  var cc = commentUtils.preCheckCommentCount(commentBtn);
  logger.info(TAG, "评论按钮 desc: '" + cc.rawDesc + "'");
  logger.info(TAG, "评论数: " + (cc.count >= 0 ? cc.count : "未知"));
  if (cc.count === 0) {
    logger.info(TAG, "该视频无评论，跳过");
    return false;
  }

  // 1. 点击评论入口按钮，打开评论面板
  var commentClicked = uiOperator.clickElement(commentBtn);
  if (!commentClicked) {
    logger.warn(TAG, "评论入口按钮点击失败");
    return false;
  }
  sleep(1500);

  // 2. 点击评论输入框，弹出键盘
  var inputClicked = this.safeClick("video_comment_input", 3);
  if (!inputClicked) {
    logger.warn(TAG, "评论输入框未找到");
    back();
    return false;
  }
  sleep(1000);

  // 3. 输入评论内容
  var inputResult = this.safeInput("video_comment_input", content);
  if (!inputResult) {
    logger.warn(TAG, "输入评论内容失败");
    back();
    return false;
  }
  sleep(500);

  // 4. Submit once and require visible delivery evidence before counting it.
  sleep(500);
  if (taskCancellation.isCancelled()) return false;
  this._lastSendOutcome = commentUtils.submitAndObserve("comment_submit", "video_comment_input", content, "comment_send_failed");
  if (this._lastSendOutcome !== "confirmed") {
    logger.warn(TAG, "评论发送未确认: " + this._lastSendOutcome);
    this.safeClick("back_btn", 2);
    return false;
  }
  sleep(1000);

  // 5. 关闭评论面板
  this.safeClick("back_btn", 2);
  sleep(800);

  logger.info(TAG, "评论成功: '" + content.substring(0, 20) + "'");
  stats.details.push("commented: " + content.substring(0, 30));
  try { apiClient.incrementStats((this._params || {}).account_id, "search_comment", "", 1); } catch (e) {}
  return true;
};

module.exports = SearchCommentHandler;
