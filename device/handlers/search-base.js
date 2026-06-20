// device/handlers/search-base.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");
var aiAnalyzer = require("../core/ai-analyzer");
var flowContext = require("../core/flow-context");
var taskExecutor = require("../core/task-executor");

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
  this._params = params;
  var keyword = params.keyword;
  var videoCount = params.video_count || params.count || 5;
  var content = params.content || "";
  var sortBy = params.sort_by || "";


  aiAnalyzer.useTemplate(params.prompt_template_id);

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "搜索: '" + keyword + "', 视频=" + videoCount + ", 排序=" + sortBy);

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

  if (!this._waitForSearchResults(keyword)) {
    return { success: false, error: "搜索结果页未加载" };
  }

  // 4. 点击"视频" tab
  this._clickVideoTab();
  sleep(2000);

  // 5. 排序（如果指定）
  if (sortBy) {
    this._sortResults(sortBy);
    sleep(1500);
  }

  // 6. 逐个视频处理（第一个点击，后续滑动切换）
  var stats = { success_count: 0, fail_count: 0, details: [] };

  for (var i = 0; i < videoCount; i++) {
    if (taskExecutor.isCancelled()) {
      logger.info(TAG, "任务已取消，停止处理视频");
      stats.details.push("cancelled at video " + (i + 1) + "/" + videoCount);
      break;
    }
    logger.info(TAG, "处理第 " + (i + 1) + "/" + videoCount + " 个结果");

    if (i === 0) {
      // ==== 首视频：前置弹窗清洗 + 状态断言 + 失败重试 ====
      // 排序弹窗残留会拦截视频点击——不能用 back()（抖音搜索结果页 back 直接回首页）
      var popupOpen = uiOperator.findElement("sort_latest", 800, true) || uiOperator.findElement("sort_most_liked", 800, true);
      if (popupOpen) {
        logger.warn(TAG, "检测到残留排序弹窗，点击 sort_button 切换关闭");
        this.safeClick("sort_button", 2);
        sleep(400);
      }

      var firstVideoOpened = false;
      for (var attempt = 0; attempt < 2; attempt++) {
        if (!this._clickSearchResult(0)) break;
        // 状态断言：显式等待视频详情页特征元素，严禁无脑 sleep
        if (uiOperator.waitForElement("video_comment_btn", 5000)) {
          firstVideoOpened = true;
          break;
        }
        logger.warn(TAG, "视频详情页未加载 (尝试 " + (attempt + 1) + "/2)");
        // 只在确实进入了视频页时才 back——若仍在搜索页，back 会直接回首页
        if (uiOperator.isOnPage("is_video_view")) { back(); sleep(800); }
      }
      if (!firstVideoOpened) {
        logger.warn(TAG, "首视频两次尝试均失败，停止处理");
        break;
      }
    } else {
      // 后续视频：暂停 → 滑动切换
      back(); sleep(500);
      if (uiOperator.findElement("is_video_view", 1000)) {
        press(device.width / 2, device.height / 2, 80);
        sleep(300);
      }
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
  return { success: true, result: stats };
};

/**
 * 打开搜索页
 * 先尝试直接点击搜索入口，失败则 back() 后重试
 */
SearchBaseHandler._openSearch = function () {
  // 0. 确保抖音在前台——设备重启或 crash 恢复后抖音可能不在前台
  if (!uiOperator.openApp()) {
    logger.error(TAG, "无法启动抖音");
    return false;
  }
  // 1. 首页可能还在加载，多等几秒，重试 3 次（safeClick 内部 findElement 等 3s × 退避 2s/4s ≈ 最多 17s）
  var clicked = this.safeClick("search_tab", 3);
  if (clicked) {
    sleep(Math.floor(Math.random() * 1000 + 1000));
    if (uiOperator.isOnPage("is_search_view")) {
      flowContext.enter("search");
      return true;
    }
    logger.warn(TAG, "点击 search_tab 后未进入搜索页，重试");
  }

  // 2. 搜索入口找不到，可能在子页面，最多 back 3 次（不摧毁页面状态）
  for (var i = 0; i < 3; i++) {
    back();
    sleep(Math.floor(Math.random() * 400 + 1000));
    clicked = this.safeClick("search_tab", 2);
    if (clicked) {
      sleep(Math.floor(Math.random() * 1000 + 1000));
      if (uiOperator.isOnPage("is_search_view")) {
        flowContext.enter("search");
        return true;
      }
      logger.warn(TAG, "back 后点击 search_tab 未进入搜索页，继续重试");
    }
  }

  // 3. 冷启动兜底
  logger.warn(TAG, "back 链恢复失败，尝试冷启动回首页");
  try { uiOperator.closeApp(); sleep(800); } catch (e) {}
  if (uiOperator.openApp()) {
    sleep(4000);
    clicked = this.safeClick("search_tab", 3);
    if (clicked) {
      sleep(Math.floor(Math.random() * 1000 + 1000));
      if (uiOperator.isOnPage("is_search_view")) {
        flowContext.enter("search");
        return true;
      }
      logger.warn(TAG, "冷启动后点击 search_tab 未进入搜索页");
    }
  }
  return false;
};

/**
 * 在搜索框输入关键词
 * 使用 setText 直接设置（测试验证可用）
 */
SearchBaseHandler._inputKeyword = function (keyword) {
  // 确认在搜索页
  if (!uiOperator.isOnPage("is_search_view")) {
    logger.warn(TAG, "搜索输入框未找到：不在搜索页");
    return false;
  }
  // 在屏幕顶部区域限定查找可聚焦的搜索输入框
  var allEdits = className("EditText").find();
  var editBox = null;
  for (var ei = 0; ei < allEdits.length; ei++) {
    try {
      if (!allEdits[ei].focusable()) continue;
      var b = allEdits[ei].bounds();
      if (b && b.top < device.height * 0.3) { editBox = allEdits[ei]; break; }
    } catch (e) {}
  }
  if (!editBox) {
    logger.warn(TAG, "搜索输入框未找到");
    return false;
  }
  editBox.setText(keyword);
  sleep(500);
  logger.info(TAG, "输入关键词: '" + keyword + "'");
  return true;
};

/**
 * 点击联想词 — RecyclerView 内遍历匹配关键词
 */
SearchBaseHandler._clickSuggestion = function (keyword) {
  // RecyclerView 遍历匹配联想词
  var rv = id("recycler_view").findOne(2000);
  if (!rv) {
    var allRVs = className("androidx.recyclerview.widget.RecyclerView").find();
    if (allRVs.length === 0) allRVs = className("android.support.v7.widget.RecyclerView").find();
    for (var ri = 0; ri < allRVs.length; ri++) {
      var rvb = allRVs[ri].bounds();
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
        logger.info(TAG, "点击联想词: '" + ct.text() + "'");
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
 * 等待搜索动作真正进入结果页。
 * 抖音点击联想词/搜索按钮后有时不会跳转，必须显式校验，避免后续流程误判为“已无结果”而直接跳过。
 */
SearchBaseHandler._waitForSearchResults = function (keyword, timeoutMs) {
  timeoutMs = timeoutMs || 10000;
  var intervalMs = 500;
  var attempts = Math.max(1, Math.ceil(timeoutMs / intervalMs));
  logger.info(TAG, "等待搜索结果页: '" + keyword + "'");

  for (var i = 0; i < attempts; i++) {
    if (uiOperator.isOnPage("search_result_list", 300)) {
      flowContext.enter("search");
      logger.info(TAG, "搜索结果页已加载: search_result_list");
      return true;
    }
    if (uiOperator.findElement("search_video_tab", 300, true)) {
      flowContext.enter("search");
      logger.info(TAG, "搜索结果页已加载: search_video_tab");
      return true;
    }
    if (uiOperator.findElement("search_video_list", 300, true)) {
      flowContext.enter("search");
      logger.info(TAG, "搜索结果页已加载: search_video_list");
      return true;
    }
    sleep(intervalMs);
  }

  var page = "";
  try { page = uiOperator.detectPage ? uiOperator.detectPage() : ""; } catch (e) {}
  logger.warn(TAG, "搜索结果页未加载: '" + keyword + "', 当前页面=" + (page || "未知"));
  return false;
};

/**
 * 点击"视频" tab
 * 优先使用选择器系统，回退到硬编码
 */
SearchBaseHandler._clickVideoTab = function () {
  var clicked = this.safeClick("search_video_tab", 2);
  if (clicked) {
    logger.info(TAG, "点击视频标签");
    return true;
  }
  logger.warn(TAG, "视频标签点击失败");
  return false;
};

/**
 * 点击排序选项
 * 使用选择器系统（支持 text 和 image 策略）
 * @param {string} sortBy - "latest" 或 "most_liked"
 */
SearchBaseHandler._sortResults = function (sortBy) {
  var actionMap = {
    "latest": "sort_latest",
    "most_liked": "sort_most_liked",
    "default": "sort_default",
  };
  var actionName = actionMap[sortBy] || actionMap["default"];

  // 打开排序弹窗
  if (!this.safeClick("sort_button", 3)) {
    logger.warn(TAG, "排序按钮未找到");
    return false;
  }
  // 等待弹窗动画渲染完成（抖音排序弹窗下滑动画约 200-400ms，500ms 足够）
  sleep(500);

  // 以图找图定位排序选项
  var optionEl = uiOperator.findElement(actionName, 3000);
  if (!optionEl) {
    logger.info(TAG, "排序弹窗未检测到 " + sortBy + "，关闭后重新打开弹窗重试");
    this.safeClick("sort_button", 1);
    sleep(800);
    this.safeClick("sort_button", 1);
    sleep(500);
    optionEl = uiOperator.findElement(actionName, 3000);
  }

  if (!optionEl) {
    // ==== OCR 降级：以图找图失败后，PaddleOCR 全屏文本检索排序选项 ====
    var ocrTexts = { "latest": ["最新发布", "最新"], "most_liked": ["最多点赞", "最多"], "default": ["综合排序", "综合"] };
    var ocrKeywords = ocrTexts[sortBy] || ocrTexts["default"];
    logger.info(TAG, "图像匹配失败，启动 OCR 降级检索: " + ocrKeywords.join(", "));

    var ocrScreen = images.captureScreen();
    if (ocrScreen) {
      try {
        var ocrResult = null;
        if (typeof images.paddleOcr === "function") {
          try { ocrResult = images.paddleOcr(ocrScreen); } catch (e) {}
        }
        if (!ocrResult && typeof images.mlKitOcr === "function") {
          try { ocrResult = images.mlKitOcr(ocrScreen); } catch (e) {}
        }
        // ocr.recognizeText() 返回结构化数组，优先于 ocr() 字符串
        if (!ocrResult && typeof ocr === "object" && typeof ocr.recognizeText === "function") {
          try { ocrResult = ocr.recognizeText(ocrScreen); } catch (e) {}
        }
        if (!ocrResult && typeof ocr === "function") {
          try { ocrResult = ocr(ocrScreen); } catch (e) {}
        }

        if (ocrResult) {
          if (Array.isArray(ocrResult)) {
            // paddleOcr / mlKitOcr / ocr.recognizeText: 结构化数组
            for (var oi = 0; oi < ocrResult.length; oi++) {
              var item = ocrResult[oi];
              var itemText = (item.text || "").replace(/\s/g, "");
              for (var kj = 0; kj < ocrKeywords.length; kj++) {
                if (itemText.indexOf(ocrKeywords[kj]) !== -1) {
                  var ocrX, ocrY;
                  if (item.bounds) {
                    ocrX = (item.bounds.left + item.bounds.right) / 2;
                    ocrY = (item.bounds.top + item.bounds.bottom) / 2;
                  } else if (item.x != null && item.y != null) {
                    ocrX = item.x; ocrY = item.y;
                  }
                  if (ocrX && ocrY) {
                    logger.info(TAG, "OCR 命中: '" + itemText + "' 坐标(" + ocrX + "," + ocrY + ")");
                    optionEl = { isCoordinate: true, x: ocrX, y: ocrY };
                    break;
                  }
                }
              }
              if (optionEl) break;
            }
          } else if (typeof ocrResult === "string") {
            // ocr() 返回拼接文本字符串，无坐标信息
            var cleanAll = ocrResult.replace(/\s/g, "");
            for (var kk = 0; kk < ocrKeywords.length; kk++) {
              if (cleanAll.indexOf(ocrKeywords[kk]) !== -1) {
                // OCR 确认弹窗存在，用排序弹窗典型布局近似定位（右上方区域）
                logger.info(TAG, "OCR 字符串命中: '" + ocrKeywords[kk] + "'，使用排序弹窗近似坐标");
                optionEl = { isCoordinate: true, x: Math.round(device.width * 0.72), y: Math.round(device.height * 0.28) };
                break;
              }
            }
          }
        }
        if (!optionEl) {
          logger.warn(TAG, "OCR 也未找到排序选项: " + sortBy);
        }
      } finally {
        ocrScreen.recycle();
      }
    }

    if (!optionEl) {
      this.safeClick("sort_button", 1);
      return false;
    }
  }

  // 点击排序选项
  uiOperator.clickElement(optionEl);
  logger.info(TAG, "排序方式: " + sortBy);
  sleep(500);

  // 关弹窗：抖音选完排序后可能自动关，也可能不关。连点可能反而重新打开。
  // 策略：先等 800ms 等自动关闭动画完成，再图找图判断，开着才关，关完验证
  var stillOpen = uiOperator.findElement(actionName, 2000, true);
  if (stillOpen) {
    logger.info(TAG, "排序弹窗未关闭，点击关闭");
    var closeBtn = uiOperator.findElement("sort_button", 2000);
    if (closeBtn) {
      uiOperator.clickElement(closeBtn);
      sleep(600);
      // 验证：如果还在，说明刚才那下可能反而打开了，再关一次
      if (uiOperator.findElement(actionName, 1000, true)) {
        logger.info(TAG, "排序弹窗仍在，再次关闭");
        closeBtn = uiOperator.findElement("sort_button", 1000);
        if (closeBtn) { uiOperator.clickElement(closeBtn); sleep(500); }
      }
    }
  } else {
    logger.info(TAG, "排序弹窗已关闭");
  }
  sleep(500);
  return true;
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
  if (!this._waitForSearchResults(keyword)) return false;
  this._clickVideoTab();
  sleep(2000);
  if (sortBy) {
    if (!this._sortResults(sortBy)) {
      logger.warn(TAG, "排序失败，将以默认排序处理视频 (sortBy=" + sortBy + ")");
    }
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
    if (!el) return false;
    if (el.isCoordinate || el.isImage || el.isPress) {
      return el.x >= 0 && el.y >= 0 && el.x < screenW && el.y < screenH;
    }
    if (el.isPackage) return true;
    try {
      var b = el.bounds();
      if (!b) return false;
      var cx = b.centerX();
      var cy = b.centerY();
      return cx >= 0 && cy >= 0 && cx < screenW && cy < screenH;
    } catch (e) { return false; }
  }

  function tryClick(el) {
    if (!el) return false;
    if (el.isCoordinate || el.isImage || el.isPress || el.isPackage) return uiOperator.clickElement(el);
    try {
      if (el.clickable && el.clickable()) return el.click();
      var b = el.bounds && el.bounds();
      if (b) return press(b.centerX(), b.centerY(), 80);
    } catch (e) {}
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
    if (uiOperator.isOnPage("search_result_list") || uiOperator.isOnPage("is_search_view")) {
      logger.info(TAG, "已在搜索列表页 (back " + i + " 次)");
      flowContext.enter("search");
      return true;
    }

    var page = uiOperator.detectPage();
    logger.info(TAG, "第 " + (i + 1) + " 次 back，当前位置: " + (page || "未知"));
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
  if (!this._waitForSearchResults(keyword)) return false;
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

// ==== KV 持久化（设备重启恢复状态）====

/**
 * 获取缓存目录 — 兼容 Android 10+ scoped storage
 * 复用 api-client.js 的路径策略: 优先 getExternalFilesDir, 回退 /sdcard/
 */
SearchBaseHandler._getCacheDir = function () {
  var dirs = this._getCacheDirCandidates();
  for (var i = 0; i < dirs.length; i++) {
    if (this._ensureCacheDir(dirs[i])) return dirs[i];
  }
  return dirs[0] || "/sdcard/dy_auto/cache";
};

SearchBaseHandler._getCacheDirCandidates = function () {
  var dirs = [];
  function add(dir) {
    if (dir && dirs.indexOf(dir) === -1) dirs.push(dir);
  }
  try {
    var intDir = context.getFilesDir();
    if (intDir) add(intDir.getAbsolutePath() + "/dy_auto_cache");
  } catch (e) {}
  try {
    var extDir = context.getExternalFilesDir(null);
    if (extDir) add(extDir.getAbsolutePath() + "/dy_auto_cache");
  } catch (e2) {}
  add("/sdcard/dy_auto/cache");
  return dirs;
};

SearchBaseHandler._ensureCacheDir = function (dir) {
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "缓存目录创建失败: " + dir + " err=" + e.message);
    return false;
  }
};

SearchBaseHandler._storageGet = function (key, defaultVal) {
  var dirs = this._getCacheDirCandidates();
  for (var i = 0; i < dirs.length; i++) {
    try {
      if (!this._ensureCacheDir(dirs[i])) continue;
      var path = dirs[i] + "/" + key + ".txt";
      if (files.exists(path)) {
        var parsed = parseInt(files.read(path).trim(), 10);
        return isNaN(parsed) ? defaultVal : parsed;
      }
    } catch (e) {
      logger.warn(TAG, "storageGet 读取失败: " + key + " err=" + e.message);
    }
  }
  return defaultVal;
};

SearchBaseHandler._storageSet = function (key, val) {
  var dirs = this._getCacheDirCandidates();
  var lastErr = "";
  for (var i = 0; i < dirs.length; i++) {
    try {
      if (!this._ensureCacheDir(dirs[i])) continue;
      var path = dirs[i] + "/" + key + ".txt";
      files.write(path, String(val));
      return true;
    } catch (e) {
      lastErr = e.message;
    }
  }
  logger.warn(TAG, "storageSet 写入失败: " + key + "=" + val + " err=" + lastErr);
  return false;
};


// ==== DM 序列发送方法 (search-dm / reply-comment 共用) ====

SearchBaseHandler.applyDMSequences = function (dmSequences) {
  var dmCache = {};
  var ids = [];
  dmSequences = dmSequences || [];
  for (var dsi = 0; dsi < dmSequences.length; dsi++) {
    var ds = dmSequences[dsi];
    if (ds && ds.id) {
      dmCache[ds.id] = ds;
      ids.push(ds.id);
    }
  }
  SearchBaseHandler._dmSeqCache = dmCache;
  SearchBaseHandler._dmSeqMissSynced = {};
  SearchBaseHandler._dmSeqCacheSyncedAt = Date.now();
  logger.info(TAG, "DM序列缓存已同步: count=" + ids.length + (ids.length ? " ids=" + ids.join(",") : ""));
  return dmCache;
};

SearchBaseHandler.syncDMSequences = function () {
  try {
    var apiClient = require("../core/api-client");
    var response = apiClient.fetchDMSequences();
    if (response && response.dm_sequences !== undefined) {
      return this.applyDMSequences(response.dm_sequences);
    }
    logger.warn(TAG, "DM序列同步返回为空，保留现有缓存");
  } catch (e) {
    logger.warn(TAG, "DM序列同步失败: " + e.message);
  }
  return this._dmSeqCache || {};
};

SearchBaseHandler._getDMCachedSequence = function (seqId) {
  return this._dmSeqCache && this._dmSeqCache[seqId];
};

/**
 * 解析消息序列，返回 [{order, content, delay_ms}]
 * 优先级: dm_sequence_id(缓存+变体) > dm_messages(内联回退) > content > AI 生成
 * 支持变体轮替: cached.variants 存在时轮替选取，设备重启后从 KV 恢复索引
 */
SearchBaseHandler.resolveMessages = function (params) {
  // 1. dm_sequence_id — 查 poll 缓存 (含 variants, 优先于内联 dm_messages)
  if (params.dm_sequence_id) {
    var cached = this._getDMCachedSequence(params.dm_sequence_id);
    if (!cached) {
      this._dmSeqMissSynced = this._dmSeqMissSynced || {};
      if (!this._dmSeqMissSynced[params.dm_sequence_id]) {
        this._dmSeqMissSynced[params.dm_sequence_id] = true;
        logger.warn(TAG, "DM序列模板缓存未命中: " + params.dm_sequence_id + "，重新同步序列缓存");
        this.syncDMSequences();
        cached = this._getDMCachedSequence(params.dm_sequence_id);
      }
    }
    if (cached) {
      // 有变体 → 轮替选取
      if (cached.variants && cached.variants.length > 0) {
        var storageKey = "dm_variant_idx_" + params.dm_sequence_id;
        var idx = this._storageGet(storageKey, 0);
        var picked = cached.variants[idx % cached.variants.length];
        this._storageSet(storageKey, (idx + 1) % cached.variants.length);
        logger.info(TAG, "DM变体轮替: seq=" + params.dm_sequence_id + " idx=" + idx + "/" + cached.variants.length + " msg1=" + (picked[0] ? (picked[0].content || "").substring(0, 30) : ""));
        return picked;
      }
      // 无变体 → 返回缓存消息
      logger.info(TAG, "DM使用缓存消息(无变体): seq=" + params.dm_sequence_id);
      return cached.messages;
    }
    var available = this._dmSeqCache ? Object.keys(this._dmSeqCache) : [];
    logger.warn(TAG, "DM序列模板同步后仍未命中: " + params.dm_sequence_id + "，available=" + available.join(",") + "，回退到内联消息");
    // 缓存未命中时继续往下走，用 dm_messages 作为回退
  }
  // 2. dm_messages — 内联消息 (服务端展开的回退，或手动指定)
  if (params.dm_messages && params.dm_messages.length > 0) {
    if (params.dm_sequence_id) {
      logger.info(TAG, "DM使用内联消息(dm_sequence_id缓存未命中): seq=" + params.dm_sequence_id + " msgs=" + params.dm_messages.length);
    } else {
      logger.info(TAG, "DM使用内联消息(无dm_sequence_id): msgs=" + params.dm_messages.length);
    }
    return params.dm_messages;
  }
  // 3. content — 单条消息
  if (params.content) {
    return [{order: 1, content: params.content, delay_ms: 0}];
  }
  var count = params.count || 1;
  var videoText = "";
  try { videoText = this._extractVideoText ? this._extractVideoText() : ""; } catch (e) {}
  if (count > 1 && videoText) {
    var seq = aiAnalyzer.generateVideoDMSequence(videoText, count);
    if (seq && seq.length > 0) return seq;
  }
  var single = videoText ? aiAnalyzer.generateVideoDM(videoText) : "";
  return single ? [{order: 1, content: single, delay_ms: 0}] : [];
};

/**
 * 变量替换 — 不存在的 key → 空字符串
 */
SearchBaseHandler.applyVariables = function (template, vars) {
  return template.replace(/\{\{(\w+)\}\}/g, function (_, key) {
    return vars[key] || "";
  });
};

/**
 * 发送消息序列通用循环（拟人输入 + 延迟）
 */
SearchBaseHandler._countSentDMResults = function (results) {
  var count = 0;
  if (!results) return count;
  for (var i = 0; i < results.length; i++) {
    if (results[i] && results[i].status === "sent") count++;
  }
  return count;
};

SearchBaseHandler._buildFallbackRecipientId = function (nickname) {
  var value = nickname || "unknown";
  var hash = 0;
  for (var i = 0; i < value.length; i++) {
    hash = ((hash << 5) - hash) + value.charCodeAt(i);
    hash |= 0;
  }
  return "fb_" + Math.abs(hash).toString(16);
};

SearchBaseHandler._buildDMMessageKey = function (conversationId, params, order) {
  var taskId = (params && params.task_id) || conversationId || "task";
  var sequenceId = (params && params.dm_sequence_id) || "single";
  return taskId + ":" + sequenceId + ":" + order;
};

SearchBaseHandler._reportDMSendResults = function (conversationId, results, params, stage, intent, keyword) {
  if (!conversationId || !results || results.length === 0) return 0;
  var apiClient = require("../core/api-client");
  var reported = 0;
  for (var i = 0; i < results.length; i++) {
    var result = results[i];
    if (!result) continue;
    var order = result.order != null ? result.order : (i + 1);
    try {
      apiClient.reportDMSend({
        conversation_id: conversationId,
        task_id: (params && params.task_id) || null,
        dm_sequence_id: (params && params.dm_sequence_id) || null,
        message_order: order,
        message_key: this._buildDMMessageKey(conversationId, params, order),
        stage: stage,
        intent: intent,
        keyword: keyword,
        content: result.content || "",
        status: result.status || "sent",
        error_message: result.error_message || null
      });
      reported++;
    } catch (e) {
      logger.warn(TAG, "DM发送结果上报失败: " + e.message);
    }
  }
  return reported;
};

SearchBaseHandler._buildDMFailureResults = function (messages, keyword, errorMessage) {
  var results = [];
  if (!messages) return results;
  for (var i = 0; i < messages.length; i++) {
    var msg = messages[i] || {};
    var order = msg.order != null ? msg.order : (i + 1);
    var content = this.applyVariables(msg.content || "", {keyword: keyword || ""});
    results.push({
      order: order,
      content: content,
      status: "failed",
      error_message: errorMessage,
      sent_at: new Date().toISOString()
    });
  }
  return results;
};

SearchBaseHandler._sendMessageSequence = function (messages, stats, keyword) {
  var results = [];
  var antiDetect = require("../core/anti-detect");
  antiDetect._skipDisabled = true;
  try {
    for (var i = 0; i < messages.length; i++) {
      var msg = messages[i] || {};
      var order = msg.order != null ? msg.order : (i + 1);
      var content = this.applyVariables(msg.content || "", {keyword: keyword || ""});
      var inputOk = this.safeInput("dm_input", content);
      if (!inputOk) {
        logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]输入失败，跳过本条");
        results.push({ order: order, content: content, status: "failed", error_message: "输入失败", sent_at: new Date().toISOString() });
        continue;
      }
      sleep(500);
      var sendBtn = uiOperator.findElement("dm_send", 3000);
      if (!sendBtn) {
        logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]发送按钮未找到，本条未发送");
        results.push({ order: order, content: content, status: "failed", error_message: "发送按钮未找到", sent_at: new Date().toISOString() });
        continue;
      }
      uiOperator.clickElement(sendBtn);
      sleep(1000);
      var sendFailed = !!uiOperator.findElement("dm_send_failed", 2000, true);
      if (sendFailed) {
        logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]发送失败，停止向该用户发送后续私信");
        results.push({ order: order, content: content, status: "failed", error_message: "发送失败", sent_at: new Date().toISOString() });
        break;
      }
      results.push({ order: order, content: content, status: "sent", error_message: null, sent_at: new Date().toISOString() });
      var extraDelay = msg.delay_ms != null ? msg.delay_ms : (Math.floor(Math.random() * 3000) + 2000);
      sleep(extraDelay);
      if (stats && stats.details) {
        stats.details.push("dm_sent[" + (i + 1) + "/" + messages.length + "]: " + content.substring(0, 30));
      }
    }
  } finally {
    antiDetect._skipDisabled = false;
  }
  return results;
};
module.exports = SearchBaseHandler;
