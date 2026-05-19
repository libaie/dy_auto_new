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

  for (var i = 0; i < videoCount; i++) {
    if (taskExecutor.isCancelled()) {
      logger.info(TAG, "任务已取消，停止处理视频");
      stats.details.push("cancelled at video " + (i + 1) + "/" + videoCount);
      break;
    }
    logger.info(TAG, "处理第 " + (i + 1) + "/" + videoCount + " 个结果");

    if (i === 0) {
      // 第一个视频：从搜索结果点击
      if (!this._clickSearchResult(0)) {
        logger.warn(TAG, "点击第一个视频失败，停止处理");
        break;
      }
      sleep(2000);
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
  sleep(1500);

  // 以图找图验证弹窗是否打开，没找到则重试一次
  var optionEl = uiOperator.findElement(actionName, 3000);
  if (!optionEl) {
    logger.info(TAG, "排序弹窗未检测到 " + sortBy + "，关闭弹窗后重试");
    // 第一次点击关闭可能残留的弹窗，第二次重新打开
    this.safeClick("sort_button", 1);
    sleep(800);
    optionEl = uiOperator.findElement(actionName, 3000);
  }

  if (!optionEl) {
    logger.warn(TAG, "排序选项未找到: " + sortBy);
    this.safeClick("sort_button", 1);
    return false;
  }

  // 点击排序选项
  uiOperator.clickElement(optionEl);
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
    if (b) return press(b.centerX(), b.centerY(), 80);
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
            this.safeClick("off_video", 1);
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
              this.safeClick("off_video", 1);
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
  try {
    var extDir = context.getExternalFilesDir(null);
    if (extDir) {
      var cacheDir = extDir.getAbsolutePath() + "/dy_auto_cache";
      files.ensureDir(cacheDir);
      return cacheDir;
    }
  } catch (e) {}
  var fallback = "/sdcard/dy_auto/cache";
  try { files.ensureDir(fallback); } catch (e2) {}
  return fallback;
};

SearchBaseHandler._storageGet = function (key, defaultVal) {
  try {
    var path = this._getCacheDir() + "/" + key + ".txt";
    if (files.exists(path)) {
      return parseInt(files.read(path).trim()) || defaultVal;
    }
  } catch (e) {}
  return defaultVal;
};

SearchBaseHandler._storageSet = function (key, val) {
  try {
    var path = this._getCacheDir() + "/" + key + ".txt";
    files.write(path, String(val));
  } catch (e) {}
};


// ==== DM 序列发送方法 (search-dm / reply-comment 共用) ====

/**
 * 解析消息序列，返回 [{order, content, delay_ms}]
 * 优先级: dm_sequence_id > params.content > AI 生成
 * 支持变体轮替: cached.variants 存在时轮替选取，设备重启后从 KV 恢复索引
 */
SearchBaseHandler.resolveMessages = function (params) {
  if (params.dm_messages && params.dm_messages.length > 0) {
    return params.dm_messages;
  }
  if (params.dm_sequence_id) {
    var cached = this._dmSeqCache && this._dmSeqCache[params.dm_sequence_id];
    if (cached) {
      // 有变体 → 轮替选取
      if (cached.variants && cached.variants.length > 0) {
        var storageKey = "dm_variant_idx_" + params.dm_sequence_id;
        var idx = this._storageGet(storageKey, 0);
        var picked = cached.variants[idx % cached.variants.length];
        this._storageSet(storageKey, (idx + 1) % cached.variants.length);
        return picked;
      }
      // 无变体 → 原逻辑
      return cached.messages;
    }
    logger.warn(TAG, "DM序列模板未命中: " + params.dm_sequence_id);
    return [];
  }
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
  for (var i = 0; i < messages.length; i++) {
    var msg = messages[i];
    var content = this.applyVariables(msg.content, {keyword: keyword || ""});
    var inputOk = this.safeInput("dm_input", content);
    if (!inputOk) {
      logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]输入失败，跳过本条");
      continue;
    }
    sleep(500);
    var sendBtn = uiOperator.findElement("dm_send", 3000);
    if (!sendBtn) {
      logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]发送按钮未找到，本条未发送");
      continue;
    }
    uiOperator.clickElement(sendBtn);
    sleep(1000);
    sentCount++;
    var extraDelay = msg.delay_ms != null ? msg.delay_ms : (Math.floor(Math.random() * 3000) + 2000);
    sleep(extraDelay);
    stats.details.push("dm_sent[" + (i + 1) + "/" + messages.length + "]: "
      + content.substring(0, 30));
  }
  return sentCount;
};

module.exports = SearchBaseHandler;
