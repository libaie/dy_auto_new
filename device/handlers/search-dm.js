// device/handlers/search-dm.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var logger = require("../utils/logger");

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
 * 打开搜索结果后，进入用户主页并发送私信
 * 优先使用 params.content，留空则 AI 根据视频内容自动生成
 */
SearchDMHandler._interactWithVideo = function (content, stats) {
  // 如果没有提供私信内容，在进入主页前提取视频文本并 AI 生成
  if (!content) {
    var videoText = this._extractVideoText();
    content = aiAnalyzer.generateVideoDM(videoText);
    if (!content) {
      logger.warn(TAG, "AI 生成私信失败，跳过");
      return false;
    }
    logger.info(TAG, "AI 生成私信: '" + content.substring(0, 30) + "'");
  }

  // 1. 点击视频作者头像进入主页
  var avatarClicked = this.safeClick("video_author_avatar", 2);
  if (!avatarClicked) {
    logger.warn(TAG, "未找到作者头像");
    return false;
  }
  sleep(2000);

  // 2. 点击私信按钮
  var messageClicked = this.safeClick("message_button", 3);
  if (!messageClicked) {
    logger.warn(TAG, "私信按钮未找到");
    return false;
  }
  sleep(1500);

  // 3. 输入私信内容
  var inputResult = this.safeInput("dm_input", content);
  if (!inputResult) {
    logger.warn(TAG, "输入私信内容失败");
    return false;
  }
  sleep(500);

  // 4. 点击发送
  var sendClicked = this.safeClick("dm_send", 3);
  if (!sendClicked) {
    logger.warn(TAG, "发送私信失败");
    return false;
  }
  sleep(1000);

  logger.info(TAG, "私信已发送: '" + content.substring(0, 20) + "'");
  stats.details.push("dm_sent: " + content.substring(0, 30));
  return true;
};

module.exports = SearchDMHandler;
