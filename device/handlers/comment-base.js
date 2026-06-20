// device/handlers/comment-base.js
// 视频+评论统一基类 — reply-comment 和 search-collect 的公共骨架
// 继承 SearchBaseHandler，子类只需实现 _processComments()

var SearchBaseHandler = require("./search-base");
var uiOperator = require("../core/ui-operator");
var aiAnalyzer = require("../core/ai-analyzer");
var antiDetect = require("../core/anti-detect");
var apiClient = require("../core/api-client");
var commentUtils = require("./comment-utils");
var logger = require("../utils/logger");
var flowContext = require("../core/flow-context");
// Lazy-load to break circular: task-executor → reply-comment → comment-base → task-executor

var TAG = "评论基类";

var CommentBaseHandler = Object.create(SearchBaseHandler);

/**
 * 子类可覆盖的配置
 */
CommentBaseHandler._config = {
  videoTimeoutMs: 120000,   // 单视频超时 ms，0=不限
  interVideoDelay: 2000,    // 视频间等待 ms
  maxVideoCount: Infinity,  // video_count=-1 时的上限
  defaultVideoCount: 5,     // 未指定 video_count 时的默认值
};

/**
 * 执行入口 — 搜索 → 视频循环 → 逐视频处理评论
 * 子类必须实现 _processComments(params, stats, videoIndex)
 */
CommentBaseHandler.execute = function (params) {
  var keyword = params.keyword;
  var videoCount = (params.video_count === -1) ? this._config.maxVideoCount : (params.video_count || this._config.defaultVideoCount);
  var sortBy = params.sort_by || "";

  this._prepareAnalyzer(params);

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "关键词='" + keyword + "', 视频=" + videoCount + ", 排序=" + sortBy);

  var taskId = params.task_id || "";
  function _reportProgress(step, detail, prog) {
    if (taskId) { try { apiClient.reportProgress(taskId, step, detail, prog); } catch (e) {} }
  }

  // 子类钩子：搜索前准备（如 resolveDestination）
  this._beforeSearch(params);

  if (!this.ensureAppActive()) {
    return { success: false, error: "打开抖音失败" };
  }

  // 搜索导航
  _reportProgress("搜索: " + keyword, "开始搜索", 0);
  if (!this._openSearch()) return { success: false, error: "打开搜索页失败" };
  if (!this._inputKeyword(keyword)) return { success: false, error: "输入关键词失败" };
  sleep(1000);
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return { success: false, error: "提交搜索失败" };
  }
  if (!this._waitForSearchResults(keyword)) return { success: false, error: "搜索结果页未加载" };
  this._clickVideoTab();
  sleep(1000);

  if (sortBy) {
    this._sortResults(sortBy);
    sleep(800);
  }

  var stats = this._initStats(params);

  // 视频循环
  for (var v = 0; v < videoCount; v++) {
    if (require("../core/task-executor").isCancelled()) {
      logger.info(TAG, "任务已取消，停止处理视频");
      break;
    }

    logger.info(TAG, "=== 视频 " + (v + 1) + "/" + videoCount + " ===");
    _reportProgress("视频 " + (v + 1) + "/" + videoCount, "关键词: " + keyword, v / videoCount);

    // 进入视频
    if (v === 0) {
      // 前置弹窗清洗：排序弹窗残留会拦截视频点击
      var popupOpen = uiOperator.findElement("sort_latest", 800, true) || uiOperator.findElement("sort_most_liked", 800, true);
      if (popupOpen) {
        logger.warn(TAG, "检测到残留排序弹窗，点击 sort_button 切换关闭");
        this.safeClick("sort_button", 2);
        sleep(400);
      }

      if (!this._clickSearchResult(0)) break;
      // _waitForVideoPage 内部已做显式等待，无需 sleep 赌页面加载
    } else {
      uiOperator.swipeUp();
      sleep(this._config.interVideoDelay);
    }

    // 等待视频页加载 — 内置显式等待 + 状态断言
    if (!this._waitForVideoPage(params, v)) {
      // 未进入视频详情页——如果已在视频页则 back 还原，仍在搜索页则无需 back
      if (uiOperator.isOnPage("is_video_view")) { try { back(); sleep(600); } catch (e) {} }
      continue;
    }

    // 预检评论数
    if (!this._shouldProcessVideo(params, v)) {
      this._onVideoSkipped(params, stats, v);
      continue;
    }

    // 打开评论区
    if (!this._ensureCommentsOpen(params, v)) continue;

    // 处理评论 — 子类实现
    // try-finally 确保评论区关闭 + flowContext 重置，防止异常/超时导致状态锁死
    try {
      var processResult = this._processComments(params, stats, v);
      if (processResult === "break") break;
    } finally {
      try { this._closeComments(); } catch (e) { logger.warn(TAG, "关闭评论区异常: " + e.message); }
      flowContext.reset();
    }

    stats.videos_processed = (stats.videos_processed || 0) + 1;
    antiDetect.maybePause();
  }

  logger.info(TAG, "完成. " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 搜索前准备（子类可覆盖）
 */
CommentBaseHandler._beforeSearch = function (params) {
  // default: no-op
};

CommentBaseHandler._prepareAnalyzer = function (params) {
  aiAnalyzer.useTemplate(params.prompt_template_id);
};

/**
 * 初始化统计对象（子类可覆盖）
 */
CommentBaseHandler._initStats = function (params) {
  return { videos_processed: 0, success_count: 0, fail_count: 0, skipped: 0, details: [] };
};

/**
 * 等待进入视频页
 */
CommentBaseHandler._waitForVideoPage = function (params, videoIndex) {
  var timeout = this._config.videoTimeoutMs;
  var startTime = Date.now();

  for (var wait = 0; wait < 5; wait++) {
    if (timeout > 0 && Date.now() - startTime > timeout) {
      logger.warn(TAG, "视频 " + (videoIndex + 1) + " 等待超时，跳过");
      return false;
    }
    var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
    if (commentBtn) return true;
    logger.info(TAG, "等待进入视频页 (" + (wait + 1) + "/5)");
  }
  logger.warn(TAG, "未进入视频详情页，跳过");
  return false;
};

/**
 * 预检评论数，返回 true 继续处理
 */
CommentBaseHandler._shouldProcessVideo = function (params, videoIndex) {
  var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
  if (!commentBtn) return false;

  var cc = commentUtils.preCheckCommentCount(commentBtn);
  this._currentVideoCommentCount = cc.count;
  logger.info(TAG, "视频 " + (videoIndex + 1) + " 评论数: " + (cc.count >= 0 ? cc.count : "未知"));

  if (cc.count === 0) {
    logger.info(TAG, "该视频无评论，跳过");
    return false;
  }
  return true;
};

/**
 * 视频被跳过时的处理（子类可覆盖）
 */
CommentBaseHandler._onVideoSkipped = function (params, stats, videoIndex) {
  // default: no-op
};

/**
 * 打开评论区
 */
CommentBaseHandler._ensureCommentsOpen = function (params, videoIndex) {
  return commentUtils.openComments();
};

/**
 * 关闭评论区
 */
CommentBaseHandler._closeComments = function () {
  this.safeClick("comment_off_btn", 2);
  sleep(400);
  if (uiOperator.isOnPage("is_comment_view")) {
    logger.info(TAG, "评论区未关闭，back 兜底");
    back();
    sleep(500);
  }
};

/**
 * 处理评论 — 子类必须实现
 * @param {Object} params — 任务参数
 * @param {Object} stats — 统计对象
 * @param {number} videoIndex — 当前视频索引
 * @returns {string|undefined} "break" 终止视频循环，否则继续
 */
CommentBaseHandler._processComments = function (params, stats, videoIndex) {
  throw new Error("_processComments() not implemented");
};

module.exports = CommentBaseHandler;
