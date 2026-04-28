// device/handlers/search-like.js
var SearchBaseHandler = require("./search-base");
var logger = require("../utils/logger");

var TAG = "SEARCH_LIKE";

/**
 * 搜索点赞 Handler
 * params:
 *   - keyword: string (搜索关键词)
 *   - count: number (点赞数量)
 */
var SearchLikeHandler = Object.create(SearchBaseHandler);

/**
 * 对当前视频点赞
 */
SearchLikeHandler._interactWithVideo = function (content, stats) {
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "Liked video");
    stats.details.push("liked");
    return true;
  }
  logger.warn(TAG, "Failed to like video");
  return false;
};

module.exports = SearchLikeHandler;
