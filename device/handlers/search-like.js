// device/handlers/search-like.js
var SearchBaseHandler = require("./search-base");
var apiClient = require("../core/api-client");
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
// 入参：content、stats 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 SearchLikeHandler._interactWithVideo 对应业务流程的处理结果。
SearchLikeHandler._interactWithVideo = function (content, stats) {
  var params = this._params || {};
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "Liked video");
    stats.details.push("liked");
    try { apiClient.incrementStats(params.account_id, "search_like", "", 1); } catch (e) {}
    return true;
  }
  logger.warn(TAG, "Failed to like video");
  return false;
};

module.exports = SearchLikeHandler;
