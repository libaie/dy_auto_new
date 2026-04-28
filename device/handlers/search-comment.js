// device/handlers/search-comment.js
var SearchBaseHandler = require("./search-base");
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
