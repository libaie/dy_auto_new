// device/handlers/search-base.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");
var aiAnalyzer = require("../core/ai-analyzer");

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

  
  aiAnalyzer.useTemplate(params.prompt_template_id);

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "搜索: '" + keyword + "', 数量=" + count + ", 排序=" + sortBy);

  var taskId = params.task_id || "";
  var apiClient = require("../core/api-client");
  function _reportProgress(step, detail, prog) {
    if (taskId) { try { apiClient.reportProgress(taskId, step, detail, prog); } catch (e) {} }
  }
  _reportProgress("搜索: " + keyword, "开始搜索", 0);

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

  // 等待联想词列表加载
  sleep(2000);

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

  // 6. 逐个视频处理（第一个点击，后续滑动切换）
  var stats = { success_count: 0, fail_count: 0, details: [] };

  for (var i = 0; i < count; i++) {
    logger.info(TAG, "处理第 " + (i + 1) + "/" + count + " 个结果");

    if (i === 0) {
      // 第一个视频：从搜索结果点击
      if (!this._clickSearchResult(0)) {
        logger.warn(TAG, "点击第一个视频失败，停止处理");
        break;
      }
      sleep(2000);
    } else {
      // 后续视频：滑动切换
      back(); sleep(500);
      uiOperator.swipeUp();
      sleep(2500);
    }

    var interactResult = this._interactWithVideo(content, stats);
    if (interactResult) {
      stats.success_count++;
    } else {
      stats.fail_count++;
    }

    antiDetect.maybePause();
  }

  logger.info(TAG, "搜索完成. " + JSON.stringify(stats));
  // 关闭抖音，等待下一个任务
  uiOperator.closeApp();
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
  var editBox = className("EditText").findOne(2000);
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
 * 通过 search_suggestion_list 选择器策略查找联想词列表，点击第一个
 */
SearchBaseHandler._clickSuggestion = function (keyword) {
  var uiOperator = require("../core/ui-operator");

  // 路径1: 选择器策略查找
  var items = uiOperator.findElements("search_suggestion_list", 3000);
  if (items.length > 0) {
    for (var i = 0; i < items.length; i++) {
      var t = items[i].findOne(text(keyword));
      if (t) {
        logger.info(TAG, "点击联想词(策略): '" + t.text() + "'");
        var gp = t.parent().parent();
        var b = gp.bounds();
        if (b) { press(b.centerX(), b.centerY(), 150); sleep(500); return true; }
      }
    }
  }

  // 路径2: 硬编码兜底 — RecyclerView + 遍历匹配 + 爷爷节点
  logger.info(TAG, "策略未找到联想词，尝试硬编码兜底");
  var rv = id("recycler_view").findOne(2000);
  if (!rv) {
    var allRVs = className("androidx.recyclerview.widget.RecyclerView").find();
    if (allRVs.length === 0) allRVs = className("android.support.v7.widget.RecyclerView").find();
    for (var ri = 0; ri < allRVs.length; ri++) {
      var rvb = allRVs[ri].bounds();
      // 联想词列表通常在搜索框下方，取较小的那个
      if (rvb && rvb.height() < device.height * 0.5 && rvb.top < device.height * 0.4) {
        rv = allRVs[ri]; break;
      }
    }
  }
  if (rv) {
    var children = rv.children();
    for (var c = 0; c < children.length; c++) {
      var ct = children[c].findOne(text(keyword));
      if (ct) {
        logger.info(TAG, "点击联想词(兜底): '" + ct.text() + "'");
        var gpp = ct.parent().parent();
        var bb = gpp.bounds();
        if (bb) { press(bb.centerX(), bb.centerY(), 150); sleep(500); return true; }
      }
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
    sleep(300);
    // 轻点排序按钮关闭弹窗（retries=1，避免二次点击重新打开）
    this.safeClick("sort_button", 1);
    sleep(300);
    return true;
  }

  logger.warn(TAG, "点击排序选项失败: " + sortBy);
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
 * 通过选择器系统查找视频列表容器，再点击子项
 */
SearchBaseHandler._clickSearchResult = function (index) {
  var screenW = device.width;
  var screenH = device.height;

  function isVisible(el) {
    try {
      var b = el.bounds();
      if (!b) return false;
      var cx = b.centerX();
      var cy = b.centerY();
      return cx >= 0 && cy >= 0 && cx < screenW && cy < screenH;
    } catch (e) { return false; }
  }

  function tryClick(el) {
    if (el.clickable()) return el.click();
    var b = el.bounds();
    if (b) return click(b.centerX(), b.centerY());
    return false;
  }

  function findRecyclerView() {
    var rv = id("recycler_view").findOne(500);
    if (rv) return rv;
    var all = className("androidx.recyclerview.widget.RecyclerView").find();
    if (all.length === 0) all = className("android.support.v7.widget.RecyclerView").find();
    for (var i = 0; i < all.length; i++) {
      var b = all[i].bounds();
      if (b && b.height() > 200 && b.width() > 200) return all[i];
    }
    return null;
  }

  var maxScroll = 10;
  for (var scroll = 0; scroll < maxScroll; scroll++) {
    // 路径1: 选择器
    var items = uiOperator.findElements("search_video_list", 3000);
    var seenCount = 0;
    for (var i = 0; i < items.length; i++) {
      if (isVisible(items[i])) {
        if (seenCount === index) {
          if (tryClick(items[i])) {
            logger.info(TAG, "点击视频: 第" + (index+1) + "个(策略)"); sleep(2000);
            this.safeClick("off_video", 2);
            return true;
          }
          return false;
        }
        seenCount++;
      }
    }

    // 路径2: RecyclerView 兜底
    var rv = findRecyclerView();
    if (rv) {
      var children = rv.children();
      var cnt = 0;
      for (var c = 0; c < children.length; c++) {
        if (isVisible(children[c])) {
          if (cnt === index) {
            if (tryClick(children[c])) {
              logger.info(TAG, "点击视频: 第" + (index+1) + "个(兜底)"); sleep(2000);
              this.safeClick("off_video", 2);
              return true;
            }
            return false;
          }
          cnt++;
        }
      }
    }

    if (scroll < maxScroll - 1) { uiOperator.swipeUp(); sleep(2000); }
  }

  logger.warn(TAG, "目标视频 " + (index + 1) + " 未找到");
  return false;
};

/**
 * 返回上一页
 */
SearchBaseHandler._goBack = function () {
  back();
  sleep(1000);
};

/**
 * 容错返回：连续按返回键直到回到搜索视频列表页
 * 不管当前在评论列表页/个人主页/私信页/视频详情页，最终都能回到搜索结果列表
 *
 * 页面检测选择器（需在管理后台配置）：
 *   search_video_list  — 搜索视频列表存在 → 已在搜索页
 *   search_video_tab   — 视频 tab 存在 → 已在搜索页
 *   is_comment_view    — 在评论面板？
 *   is_user_view       — 在个人主页？
 *
 * @returns {boolean} 是否成功回到搜索列表页
 */
SearchBaseHandler._backToSearchResults = function () {
  var maxBacks = 5;
  for (var i = 0; i < maxBacks; i++) {
    // 已在搜索视频列表页？
    var items = uiOperator.findElements("search_video_list", 2000);
    if (items.length > 0) {
      logger.info(TAG, "已在搜索视频列表页 (back " + i + " 次)");
      return true;
    }
    var videoTab = uiOperator.findElement("search_video_tab", 1000);
    if (videoTab) {
      logger.info(TAG, "检测到视频 tab，已在搜索页 (back " + i + " 次)");
      return true;
    }

    // 诊断当前页面
    var where = "未知";
    if (uiOperator.findElement("is_comment_view", 300)) where = "评论面板";
    else if (uiOperator.findElement("is_user_view", 300)) where = "个人主页";
    else if (uiOperator.findElement("is_video_view", 300)) where = "视频详情页";
    logger.info(TAG, "第 " + (i + 1) + " 次 back，当前位置: " + where);
    back();
    sleep(1000);
  }

  logger.warn(TAG, "back " + maxBacks + " 次后仍未回到搜索列表页");
  return false;
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
