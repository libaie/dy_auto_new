// device/handlers/search-dm.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var apiClient = require("../core/api-client");
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
 * 打开搜索结果后，进入用户主页并发送私信序列
 * 支持 DM 序列模板、单条内容、AI 生成
 */
SearchDMHandler._interactWithVideo = function (content, stats) {
  var params = this._params || {};
  var messages = this.resolveMessages(params);
  if (!messages || messages.length === 0) {
    logger.warn(TAG, "无法获取私信内容，跳过");
    return false;
  }

  // 1. 点击视频作者头像进入主页
  var avatarClicked = this.safeClick("video_author_avatar", 2);
  if (!avatarClicked) {
    logger.warn(TAG, "未找到作者头像");
    return false;
  }
  sleep(2000);

  // 2. 点击私信按钮
  var messageClicked = this.safeClick("dm_entry_btn", 3);
  if (!messageClicked) {
    logger.warn(TAG, "私信按钮未找到");
    return false;
  }
  sleep(1500);

  // 3. 发送消息序列
  var sentCount = this._sendMessageSequence(messages, stats, params.keyword);
  if (sentCount <= 0) {
    logger.warn(TAG, "私信序列没有成功发送任何消息");
    return false;
  }
  try { apiClient.incrementStats(params.account_id, "search_dm", 1); } catch (e) {}
  return true;
};

module.exports = SearchDMHandler;
