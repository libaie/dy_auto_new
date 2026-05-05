// device/handlers/search-comment.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var logger = require("../utils/logger");

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

  // 0. 确认进入视频详情页 — 检测评论按钮，不存在则尝试点击屏幕中心进入
  var uiOperator = require("../core/ui-operator");
  var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
  if (!commentBtn) {
    logger.info(TAG, "未检测到视频详情页，尝试点击进入");
    var x = Math.round(device.width * 0.5);
    var y = Math.round(device.height * 0.5);
    click(x, y);
    sleep(2000);
    commentBtn = uiOperator.findElement("video_comment_btn", 3000);
  }
  if (!commentBtn) {
    logger.warn(TAG, "评论入口按钮未找到，可能未进入视频详情页");
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

  // 4. 通过键盘回车发送
  sleep(500);
  this.submitViaKeyboard("comment_submit");
  sleep(1000);

  // 5. 关闭评论面板
  this.safeClick("back_btn", 2);
  sleep(800);

  logger.info(TAG, "评论成功: '" + content.substring(0, 20) + "'");
  stats.details.push("commented: " + content.substring(0, 30));
  return true;
};

module.exports = SearchCommentHandler;
