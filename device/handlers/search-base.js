// device/handlers/search-base.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "SEARCH_BASE";

/**
 * 搜索基类 — 所有搜索类 handler 继承此对象
 * 提供通用的搜索导航逻辑，子类只需实现 _interactWithVideo()
 */
var SearchBaseHandler = Object.create(BaseHandler);

/**
 * 执行搜索+互动流程
 * @param {Object} params
 *   - keyword: string (搜索关键词)
 *   - count: number (操作数量)
 *   - content: string (可选，评论/私信内容)
 * @returns {Object} { success, result, error }
 */
SearchBaseHandler.execute = function (params) {
  var keyword = params.keyword;
  var count = params.count || 5;
  var content = params.content || "";

  if (!keyword) {
    return { success: false, error: "Missing keyword" };
  }

  logger.info(TAG, "Searching: '" + keyword + "', count=" + count);

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  // 1. 进入搜索页
  if (!this._openSearch()) {
    return { success: false, error: "Failed to open search" };
  }

  // 2. 输入关键词
  if (!this._inputKeyword(keyword)) {
    return { success: false, error: "Failed to input keyword" };
  }

  // 3. 点击搜索按钮
  if (!this._submitSearch()) {
    return { success: false, error: "Failed to submit search" };
  }

  // 等待搜索结果加载
  sleep(3000);

  // 4. 逐个打开结果并互动
  var stats = { success_count: 0, fail_count: 0, details: [] };

  for (var i = 0; i < count; i++) {
    logger.info(TAG, "Processing result " + (i + 1) + "/" + count);

    // 点击第 i 个搜索结果
    if (!this._clickSearchResult(i)) {
      logger.warn(TAG, "Failed to click result " + (i + 1) + ", skipping");
      stats.fail_count++;
      continue;
    }

    sleep(2000); // 等待视频加载

    // 子类实现的互动逻辑
    var interactResult = this._interactWithVideo(content, stats);
    if (interactResult) {
      stats.success_count++;
    } else {
      stats.fail_count++;
      // 互动失败时清理页面状态，确保回到搜索结果
      this._goBack();
      sleep(1000);
    }

    // 返回搜索结果列表
    this._goBack();
    sleep(1500);

    // 反检测随机停顿
    antiDetect.maybePause();
  }

  logger.info(TAG, "Search complete. " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 打开搜索页
 * 先尝试直接点击搜索入口，失败则 back() 后重试
 */
SearchBaseHandler._openSearch = function () {
  // 先直接尝试点击搜索入口（当前可能已在首页）
  var clicked = this.safeClick("search_tab", 1);
  if (clicked) {
    sleep(1500);
    return true;
  }

  // 搜索入口找不到，可能在子页面，back() 回退后重试
  back();
  sleep(1500);

  clicked = this.safeClick("search_tab", 3);
  if (clicked) {
    sleep(1500);
    return true;
  }
  return false;
};

/**
 * 在搜索框输入关键词
 */
SearchBaseHandler._inputKeyword = function (keyword) {
  var inputResult = this.safeInput("search_input", keyword);
  if (inputResult) {
    sleep(500);
    return true;
  }
  return false;
};

/**
 * 点击搜索按钮
 */
SearchBaseHandler._submitSearch = function () {
  return this.safeClick("search_button", 3);
};

/**
 * 点击第 index 个搜索结果
 * 搜索结果列表中，每个结果通常是一个可点击的卡片
 */
SearchBaseHandler._clickSearchResult = function (index) {
  // 搜索结果列表中，点击第 index 个结果
  // 抖音搜索结果是垂直列表，每个结果占据大部分屏幕
  // 使用滑动定位 + 点击的方式
  if (index > 0) {
    // 先滑动到目标位置
    for (var i = 0; i < index; i++) {
      uiOperator.swipeUp();
      sleep(1000);
    }
  }

  // 点击屏幕中间区域打开视频
  var x = Math.round(device.width * 0.5);
  var y = Math.round(device.height * 0.4);
  return click(x, y);
};

/**
 * 返回上一页
 */
SearchBaseHandler._goBack = function () {
  back();
  sleep(1000);
};

/**
 * 搜索关键词并打开第一个结果视频
 * 供 ReplyCommentHandler 等不需要遍历多个结果的场景使用
 * @param {string} keyword - 搜索关键词
 * @returns {boolean} 是否成功打开视频
 */
SearchBaseHandler.searchAndOpenFirstResult = function (keyword) {
  if (!this._openSearch()) return false;

  if (!this._inputKeyword(keyword)) return false;

  if (!this._submitSearch()) return false;

  sleep(3000);

  // 点击第一个结果
  if (!this._clickSearchResult(0)) return false;

  sleep(2000);
  return true;
};

/**
 * 互动逻辑（子类必须实现）
 * @param {string} content - 评论/私信内容
 * @param {Object} stats - 统计对象
 * @returns {boolean} 是否成功
 */
SearchBaseHandler._interactWithVideo = function (content, stats) {
  throw new Error("_interactWithVideo() not implemented");
};

module.exports = SearchBaseHandler;
