// device/handlers/nurture.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "NURTURE";

/**
 * 养号 Handler
 * params:
 *   - duration: number (养号时长，分钟)
 *   - actions: Array<{ type: string, weight: number }> (可选，自定义行为权重)
 */
var NurtureHandler = Object.create(BaseHandler);

NurtureHandler.execute = function (params) {
  var duration = params.duration || 30; // 默认 30 分钟
  var actions = params.actions || [
    { type: "browse_feed", weight: 70 },
    { type: "like", weight: 20 },
    { type: "follow", weight: 10 },
  ];

  logger.info(TAG, "Starting nurture for " + duration + " minutes");

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  var startTime = Date.now();
  var endTime = startTime + duration * 60 * 1000;
  var stats = { videos_watched: 0, likes: 0, follows: 0, errors: 0 };

  while (Date.now() < endTime) {
    // 随机选择行为
    var action = this._weightedRandom(actions);

    try {
      switch (action.type) {
        case "browse_feed":
          this._browseFeed(stats);
          break;
        case "like":
          this._likeCurrentVideo(stats);
          break;
        case "follow":
          this._followCurrentUser(stats);
          break;
        default:
          this._browseFeed(stats);
      }
    } catch (e) {
      logger.error(TAG, "Error during nurture action '" + action.type + "': " + e.message);
      stats.errors++;
    }

    // 随机上滑浏览下一条
    antiDetect.humanSwipeUp();
    stats.videos_watched++;

    logger.info(TAG, "Progress: watched=" + stats.videos_watched +
      " likes=" + stats.likes + " follows=" + stats.follows +
      " errors=" + stats.errors);
  }

  logger.info(TAG, "Nurture completed. Stats: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 浏览推荐页（不做额外操作，只是等待观看）
 */
NurtureHandler._browseFeed = function (stats) {
  // 模拟观看视频 5-15 秒
  var watchTime = Math.floor(Math.random() * 10000 + 5000);
  logger.debug(TAG, "Watching video for " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

/**
 * 对当前视频点赞
 */
NurtureHandler._likeCurrentVideo = function (stats) {
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    stats.likes++;
    logger.info(TAG, "Liked video (total: " + stats.likes + ")");
  }
};

/**
 * 关注当前视频的作者
 */
NurtureHandler._followCurrentUser = function (stats) {
  var clicked = this.safeClick("follow_button", 2);
  if (clicked) {
    stats.follows++;
    logger.info(TAG, "Followed user (total: " + stats.follows + ")");
  }
};

/**
 * 按权重随机选择行为
 */
NurtureHandler._weightedRandom = function (actions) {
  var totalWeight = actions.reduce(function (sum, a) { return sum + a.weight; }, 0);
  var random = Math.random() * totalWeight;
  var cumulative = 0;
  for (var i = 0; i < actions.length; i++) {
    cumulative += actions[i].weight;
    if (random < cumulative) return actions[i];
  }
  return actions[0];
};

module.exports = NurtureHandler;
