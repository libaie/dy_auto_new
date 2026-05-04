// device/handlers/search-base.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "搜索";

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
 *   - sort_by: string (可选，排序方式: "latest"|"most_liked")
 * @returns {Object} { success, result, error }
 */
SearchBaseHandler.execute = function (params) {
  var keyword = params.keyword;
  var count = params.count || 5;
  var content = params.content || "";
  var sortBy = params.sort_by || "";

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "搜索: '" + keyword + "', 数量=" + count + ", 排序=" + sortBy);

  if (!this.ensureAppActive()) {
    return { success: false, error: "打开抖音失败" };
  }

  // 1. 进入搜索页
  if (!this._openSearch()) {
    return { success: false, error: "打开搜索页失败" };
  }

  // 2. 输入关键词
  if (!this._inputKeyword(keyword)) {
    return { success: false, error: "输入关键词失败" };
  }

  // 3. 点击联想词
  if (!this._clickSuggestion(keyword)) {
    // 联想词没找到，尝试直接搜索
    if (!this._submitSearch()) {
      return { success: false, error: "提交搜索失败" };
    }
  }

  sleep(3000);

  // 4. 点击"视频" tab
  this._clickVideoTab();
  sleep(2000);

  // 5. 排序（如果指定）
  if (sortBy) {
    this._sortResults(sortBy);
    sleep(2000);
  }

  // 6. 逐个打开结果并互动
  var stats = { success_count: 0, fail_count: 0, details: [] };

  for (var i = 0; i < count; i++) {
    logger.info(TAG, "处理第 " + (i + 1) + "/" + count + " 个结果");

    if (!this._clickSearchResult(i)) {
      logger.warn(TAG, "点击第 " + (i + 1) + " 个结果失败，跳过");
      stats.fail_count++;
      continue;
    }

    sleep(2000);

    var interactResult = this._interactWithVideo(content, stats);
    if (interactResult) {
      stats.success_count++;
    } else {
      stats.fail_count++;
    }

    this._goBack();
    sleep(1500);

    antiDetect.maybePause();
  }

  logger.info(TAG, "搜索完成. " + JSON.stringify(stats));
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
 * 使用 setText 直接设置（测试验证可用）
 */
SearchBaseHandler._inputKeyword = function (keyword) {
  var editBox = className("EditText").findOnce();
  if (!editBox) {
    logger.warn(TAG, "搜索输入框未找到");
    return false;
  }
  editBox.click();
  sleep(300);
  editBox.setText(keyword);
  sleep(500);
  logger.info(TAG, "输入关键词: '" + keyword + "'");
  return true;
};

/**
 * 点击联想词
 * 在 recycler_view 中查找包含关键词的联想词并点击
 * 优先使用选择器系统，回退到硬编码 ID
 */
SearchBaseHandler._clickSuggestion = function (keyword) {
  // 尝试使用选择器系统
  var rv = null;
  var selector = require("../core/selector-loader").get("search_suggestion_list");
  if (selector) {
    var strategies = selector.strategies.slice().sort(function (a, b) { return a.priority - b.priority; });
    for (var s = 0; s < strategies.length; s++) {
      try {
        switch (strategies[s].type) {
          case "id": rv = id(strategies[s].value).findOne(3000); break;
          case "className": rv = className(strategies[s].value).findOne(3000); break;
        }
      } catch (e) {}
      if (rv) break;
    }
  }
  // 回退：硬编码 ID
  if (!rv) {
    rv = id("recycler_view").findOne(3000);
  }
  if (!rv) {
    logger.warn(TAG, "联想词列表未找到");
    return false;
  }
  var children = rv.children();
  for (var i = 0; i < children.length; i++) {
    var t = children[i].findOne(text(keyword));
    if (t) {
      logger.info(TAG, "点击联想词: '" + t.text() + "'");
      t.parent().parent().click();
      sleep(1000);
      return true;
    }
  }
  logger.warn(TAG, "未找到匹配联想词: '" + keyword + "'");
  return false;
};

/**
 * 点击"视频" tab
 * 优先使用选择器系统，回退到硬编码
 */
SearchBaseHandler._clickVideoTab = function () {
  // 尝试使用选择器系统
  var clicked = this.safeClick("search_video_tab", 2);
  if (clicked) {
    logger.info(TAG, "点击视频标签");
    return true;
  }
  // 回退：硬编码
  try {
    var vt = id("text1").className("android.widget.Button").text("视频").findOne(5000);
    if (vt) {
      vt.parent().parent().click();
      logger.info(TAG, "点击视频标签(硬编码)");
      return true;
    }
  } catch (e) {
    logger.warn(TAG, "视频标签点击失败: " + e.message);
  }
  return false;
};

/**
 * 点击排序选项
 * 使用选择器系统（支持 text 和 image 策略）
 * @param {string} sortBy - "latest" 或 "most_liked"
 */
SearchBaseHandler._sortResults = function (sortBy) {
  // 点击排序按钮打开弹出框
  var sortBtnClicked = this.safeClick("sort_button", 3);
  if (!sortBtnClicked) {
    logger.warn(TAG, "排序按钮未找到");
    return false;
  }
  sleep(800);

  // 使用选择器系统点击排序选项（自动尝试 text → image 策略）
  var actionMap = {
    "latest": "sort_latest",
    "most_liked": "sort_most_liked",
    "default": "sort_default",
  };
  var actionName = actionMap[sortBy] || actionMap["default"];

  var clicked = this.safeClick(actionName, 3);
  if (clicked) {
    logger.info(TAG, "排序方式: " + sortBy);
    sleep(500);
    // 关闭排序弹出框
    this._closeSortPopup();
    return true;
  }

  logger.warn(TAG, "点击排序选项失败: " + sortBy);
  return false;
};

/**
 * 关闭排序弹出框（再次点击排序按钮）
 */
SearchBaseHandler._closeSortPopup = function () {
  var clicked = this.safeClick("sort_button", 2);
  if (clicked) {
    sleep(500);
    logger.info(TAG, "排序弹窗已关闭");
    return true;
  }
  return false;
};

/**
 * 搜索 → 排序 → 关闭弹出框 → 打开第一个视频
 * @param {string} keyword
 * @param {string} sortBy - "latest" 或 "most_liked"
 * @returns {boolean}
 */
SearchBaseHandler.searchSortAndOpenFirstResult = function (keyword, sortBy) {
  if (!this._openSearch()) return false;
  if (!this._inputKeyword(keyword)) return false;
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return false;
  }
  sleep(3000);
  this._clickVideoTab();
  sleep(2000);
  if (sortBy) {
    this._sortResults(sortBy);
    sleep(1500);
  }
  if (!this._clickSearchResult(0)) return false;
  sleep(2000);
  return true;
};

/**
 * 点击搜索按钮（备用）
 */
SearchBaseHandler._submitSearch = function () {
  return this.safeClick("search_button", 3);
};

/**
 * 点击第 index 个搜索结果
 */
SearchBaseHandler._clickSearchResult = function (index) {
  if (index > 0) {
    for (var i = 0; i < index; i++) {
      uiOperator.swipeUp();
      sleep(1000);
    }
  }
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
 */
SearchBaseHandler.searchAndOpenFirstResult = function (keyword) {
  if (!this._openSearch()) return false;
  if (!this._inputKeyword(keyword)) return false;
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return false;
  }
  sleep(3000);
  this._clickVideoTab();
  sleep(2000);
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
