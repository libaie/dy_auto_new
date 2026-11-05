// device/handlers/search-base.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");
var aiAnalyzer = require("../core/ai-analyzer");
var flowContext = require("../core/flow-context");
var taskCancellation = require("../core/task-cancellation");
var taskTimeout = require("../core/task-timeout");
var screenContext = require("../core/screen-context");
var commentUtils = require("./comment-utils");
var ocrLocator = require("../core/ocr-locator");

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
  var deadlineAt = Date.now() + taskTimeout.getTaskTimeoutMs({ type: "search", params: params });


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

  sleep(2000);

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

  for (var i = 0; videoCount === -1 || i < videoCount; i++) {
    if (taskCancellation.isCancelled()) {
      logger.info(TAG, "任务已取消，停止处理视频");
      stats.details.push("cancelled at video " + (i + 1) + "/" + videoCount);
      break;
    }
    if (Date.now() >= deadlineAt) {
      return { success: false, error: "搜索已达到任务执行时限", result: stats };
    }
    logger.info(TAG, "处理第 " + (i + 1) + "/" + videoCount + " 个结果");

    if (i === 0) {
      // ==== 首视频：前置弹窗清洗 + 状态断言 + 失败重试 ====
      // 排序弹窗残留会拦截视频点击——不能用 back()（抖音搜索结果页 back 直接回首页）
      var popupOpen = uiOperator.findElement("sort_latest", 800) || uiOperator.findElement("sort_most_liked", 800);
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
      if (!uiOperator.waitForElement("video_comment_btn", 5000)) {
        logger.info(TAG, "没有可继续处理的视频，结束搜索");
        break;
      }
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
  var ctx = screenContext.read();
  var header = commentUtils.usableBounds(ctx.contentBounds, ctx);
  if (!header) return false;
  header.bottom = Math.min(header.bottom, header.top + Math.max(screenContext.dp(96, ctx), (header.bottom - header.top) * 0.3));
  var allEdits = className("EditText").find();
  var editBox = null;
  for (var ei = 0; ei < allEdits.length; ei++) {
    try {
      if (!allEdits[ei].focusable()) continue;
      if (commentUtils.visibleNode(allEdits[ei], ctx, header)) { editBox = allEdits[ei]; break; }
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
  var ctx = screenContext.read();
  var rv = commentUtils.findListContainer(null);
  var scope = rv ? commentUtils.usableBounds(rv.bounds(), ctx) : null;
  if (scope) {
    var children = rv.children();
    for (var c = 0; c < children.length; c++) {
      var ct = children[c].findOne(text(keyword));
      if (ct && commentUtils.clickWithin(ct, scope)) {
        logger.info(TAG, "点击联想词: '" + keyword + "'");
        sleep(500);
        return true;
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
  var ctx = screenContext.read();
  var tabs = uiOperator.findElements("search_video_tab", 2000);
  var clicked = false;
  for (var ti = 0; ti < tabs.length; ti++) {
    if (commentUtils.clickWithin(tabs[ti], ctx.contentBounds)) { clicked = true; break; }
  }
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
        // Coordinates belong to this capture, not the later recognition time.
        // Preserve its signature/age so the live executor can reject staleness.
        var ocrContext = screenContext.read(ocrScreen);
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
          optionEl = ocrLocator.locateUnique(ocrResult, ocrKeywords, ocrContext, ocrContext.contentBounds);
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
  if (!uiOperator.clickElement(optionEl)) return false;
  logger.info(TAG, "排序方式: " + sortBy);
  sleep(500);

  // 关弹窗：抖音选完排序后可能自动关，也可能不关。连点可能反而重新打开。
  // 策略：先等 800ms 等自动关闭动画完成，再图找图判断，开着才关，关完验证
  var stillOpen = uiOperator.findElement(actionName, 2000);
  if (stillOpen) {
    logger.info(TAG, "排序弹窗未关闭，点击关闭");
    var closeBtn = uiOperator.findElement("sort_button", 2000);
    if (closeBtn) {
      uiOperator.clickElement(closeBtn);
      sleep(600);
      // 验证：如果还在，说明刚才那下可能反而打开了，再关一次
      if (uiOperator.findElement(actionName, 1000)) {
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
  sleep(3000);
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
  var maxScroll = 10;
  for (var scroll = 0; scroll < maxScroll; scroll++) {
    var ctx = screenContext.read();
    var rv = commentUtils.findListContainer("search_video_list");
    var scope = rv ? commentUtils.usableBounds(rv.bounds(), ctx) : ctx.contentBounds;
    if (!scope) return false;
    var items = uiOperator.findElements("search_video_list", 3000);
    var candidates = [];
    for (var i = 0; i < items.length; i++) {
      // Separate accessibility queries can wrap the same list node in distinct
      // objects. Container semantics, not JS identity, decide whether to expand
      // its visible result children below.
      if (!commentUtils.isListContainer(items[i]) && commentUtils.visibleNode(items[i], ctx, scope)) candidates.push(items[i]);
    }
    if (!candidates.length && rv) {
      var children = rv.children();
      for (var c = 0; c < children.length; c++) {
        if (commentUtils.visibleNode(children[c], ctx, scope)) candidates.push(children[c]);
      }
    }
    if (candidates.length > index && index >= 0) {
      if (!commentUtils.clickWithin(candidates[index], scope)) return false;
      sleep(2000);
      this.safeClick("off_video", 1);
      return true;
    }
    if (scroll < maxScroll - 1) {
      if (!rv || !commentUtils.swipeList("search_video_list", false)) break;
      sleep(2000);
    }
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
SearchBaseHandler._sendMessageSequence = function (messages, stats, keyword) {
  var sentCount = 0;
  this._lastSendOutcome = "not_attempted";
  var previousSkip = antiDetect._skipDisabled;
  antiDetect._skipDisabled = true;
  try {
    for (var i = 0; i < messages.length; i++) {
      var msg = messages[i];
      var content = this.applyVariables(msg.content, { keyword: keyword || "" });
      if (!this.safeInput("dm_input", content)) break;
      sleep(500);
      this._lastSendOutcome = commentUtils.submitAndObserve("dm_send", "dm_input", content, "dm_send_failed");
      if (this._lastSendOutcome !== "confirmed") {
        logger.warn(TAG, "DM发送未确认: " + this._lastSendOutcome + "，停止序列");
        break;
      }
      sentCount++;
      stats.details.push("dm_sent[" + (i + 1) + "/" + messages.length + "]: " + content.substring(0, 30));
      sleep(msg.delay_ms != null ? msg.delay_ms : (Math.floor(Math.random() * 3000) + 2000));
    }
  } finally {
    antiDetect._skipDisabled = previousSkip;
  }
  return sentCount;
};

module.exports = SearchBaseHandler;
