// device/handlers/nurture.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "养号";

/**
 * 养号 Handler
 * V2 params:
 *   - sub_tasks: Array<{ type: string, count: number, content_template_id?: string }>
 *   - completion_mode: "all" | "any"
 *   - duration: number (最大时长，分钟)
 * Legacy params:
 *   - duration: number (养号时长，分钟)
 *   - actions: Array<{ type: string, weight: number }>
 */
var NurtureHandler = Object.create(BaseHandler);

NurtureHandler.execute = function (params) {
  // V2 format: sub_tasks + completion_mode
  if (params.sub_tasks) {
    return this._executeV2(params);
  }
  // Legacy format: duration + actions
  return this._legacyExecute(params);
};

NurtureHandler._executeV2 = function (params) {
  var subTasks = params.sub_tasks;
  var completionMode = params.completion_mode || "all";
  var maxDuration = (params.duration || 60) * 60 * 1000;
  var startTime = Date.now();

  logger.info(TAG, "开始养号 V2, 子任务数=" + subTasks.length + ", 模式=" + completionMode);

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  // Initialize progress for each sub-task
  var progress = subTasks.map(function (st) {
    return {
      type: st.type,
      target: st.count,
      done: 0,
      contentTemplateId: st.content_template_id || null,
    };
  });

  while (Date.now() - startTime < maxDuration) {
    // Find incomplete sub-tasks
    var pending = progress.filter(function (p) { return p.done < p.target; });
    if (pending.length === 0) {
      logger.info(TAG, "所有子任务已完成");
      break;
    }

    // Randomly pick one incomplete sub-task
    var task = pending[Math.floor(Math.random() * pending.length)];
    try {
      this._executeSubTask(task);
      task.done++;
    } catch (e) {
      logger.error(TAG, "子任务 '" + task.type + "' 出错: " + e.message);
    }

    // Log progress
    var progressSummary = progress.map(function (p) {
      return p.type + ":" + p.done + "/" + p.target;
    }).join(" ");
    logger.info(TAG, "进度: " + progressSummary);

    // Check completion condition
    if (completionMode === "any") {
      var anyDone = progress.some(function (p) { return p.done >= p.target; });
      if (anyDone) {
        logger.info(TAG, "任一子任务完成，结束养号");
        break;
      }
    }

    antiDetect.humanSwipeUp();
  }

  // Build stats
  var stats = {};
  progress.forEach(function (p) {
    stats[p.type] = { target: p.target, done: p.done };
  });

  logger.info(TAG, "养号 V2 完成: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

NurtureHandler._executeSubTask = function (task) {
  switch (task.type) {
    case "browse":
      this._browseFeed();
      break;
    case "watch":
      this._watchVideo();
      break;
    case "like":
      this._likeCurrentVideo();
      break;
    case "comment":
      this._commentOnVideo(task.contentTemplateId);
      break;
    case "follow":
      this._followCurrentUser();
      break;
    default:
      this._browseFeed();
  }
};

NurtureHandler._browseFeed = function () {
  var watchTime = Math.floor(Math.random() * 10000 + 5000);
  logger.debug(TAG, "浏览推荐页 " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

NurtureHandler._watchVideo = function () {
  var watchTime = Math.floor(Math.random() * 20000 + 10000);
  logger.debug(TAG, "观看视频 " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

NurtureHandler._likeCurrentVideo = function () {
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "点赞成功");
  }
};

NurtureHandler._commentOnVideo = function (templateId) {
  var opened = this.safeClick("comment_input", 3);
  if (!opened) return;
  sleep(500);
  var content = "好视频！";
  uiOperator.typeText(content);
  sleep(300);
  this.safeClick("comment_submit", 2);
  logger.info(TAG, "评论成功");
};

NurtureHandler._followCurrentUser = function () {
  var clicked = this.safeClick("follow_button", 2);
  if (clicked) {
    logger.info(TAG, "关注成功");
  }
};

// --- Legacy support ---
NurtureHandler._legacyExecute = function (params) {
  var duration = params.duration || 30;
  var actions = params.actions || [
    { type: "browse_feed", weight: 70 },
    { type: "like", weight: 20 },
    { type: "follow", weight: 10 },
  ];

  logger.info(TAG, "开始养号(旧版) " + duration + " 分钟");

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  var startTime = Date.now();
  var endTime = startTime + duration * 60 * 1000;
  var stats = { videos_watched: 0, likes: 0, follows: 0, errors: 0 };

  while (Date.now() < endTime) {
    var action = this._weightedRandom(actions);
    try {
      switch (action.type) {
        case "browse_feed":
          this._browseFeed();
          break;
        case "like":
          this._likeCurrentVideo();
          break;
        case "follow":
          this._followCurrentUser();
          break;
        default:
          this._browseFeed();
      }
    } catch (e) {
      logger.error(TAG, "养号操作 '" + action.type + "' 出错: " + e.message);
      stats.errors++;
    }
    antiDetect.humanSwipeUp();
    stats.videos_watched++;
  }

  logger.info(TAG, "养号完成. 统计: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

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
