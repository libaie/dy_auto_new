// device/handlers/search-dm.js
var SearchBaseHandler = require("./search-base");
var logger = require("../utils/logger");

var TAG = "SEARCH_DM";

/**
 * 搜索私信 Handler
 * params:
 *   - keyword: string (搜索关键词 — 用于搜索用户)
 *   - count: number (私信数量)
 *   - content: string (私信内容)
 */
var SearchDMHandler = Object.create(SearchBaseHandler);

/**
 * 打开搜索结果后，进入用户主页并发送私信
 */
SearchDMHandler._interactWithVideo = function (content, stats) {
  if (!content) {
    logger.warn(TAG, "No DM content provided");
    return false;
  }

  // 1. 点击视频作者头像进入主页
  var avatarClicked = this.safeClick("video_author_avatar", 2);
  if (!avatarClicked) {
    logger.warn(TAG, "Failed to click author avatar");
    return false;
  }
  sleep(2000);

  // 2. 点击私信按钮
  var messageClicked = this.safeClick("message_button", 3);
  if (!messageClicked) {
    logger.warn(TAG, "Failed to click message button");
    return false;
  }

  sleep(1500);

  // 3. 输入私信内容
  var inputResult = this.safeInput("dm_input", content);
  if (!inputResult) {
    logger.warn(TAG, "Failed to input DM text");
    return false;
  }

  sleep(500);

  // 4. 点击发送
  var sendClicked = this.safeClick("dm_send", 3);
  if (!sendClicked) {
    logger.warn(TAG, "Failed to send DM");
    return false;
  }

  sleep(1000);

  logger.info(TAG, "DM sent: '" + content.substring(0, 20) + "...'");
  stats.details.push("dm_sent: " + content.substring(0, 30));
  return true;
};

module.exports = SearchDMHandler;
