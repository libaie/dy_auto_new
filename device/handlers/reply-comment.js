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
