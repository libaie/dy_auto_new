// device/handlers/search-collect.js
var SearchBaseHandler = require("./search-base");
var uiOperator = require("../core/ui-operator");
var aiAnalyzer = require("../core/ai-analyzer");
var selectorLoader = require("../core/selector-loader");
var apiClient = require("../core/api-client");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");
var ReplyCommentHandler = require("./reply-comment");

var TAG = "采集";

var SearchCollectHandler = Object.create(SearchBaseHandler);

SearchCollectHandler._interactWithVideo = function (content, stats, params) {
  params = params || {};
  var taskId = (stats._taskId || "");
  var keyword = (stats._keyword || "");
  var t0 = Date.now();

  logger.info(TAG, "[耗时] 尝试打开评论区...");
  if (!this._openComments()) {
    logger.warn(TAG, "[耗时] 评论区打开失败, 跳过此视频 (耗时 " + (Date.now() - t0) + "ms)");
    return false;
  }
  logger.info(TAG, "[耗时] 评论区已打开 (耗时 " + (Date.now() - t0) + "ms)");

  var collected = 0;
  var visitedUsers = {};
  var seenComments = {};  // 评论内容去重 (MD5-like: 昵称+前80字)
  var maxComments = params.count || 50;

  var maxAgeDays = params.max_age_days || 30;
  var now = new Date();
  var cutoff = new Date(now.getTime() - maxAgeDays * 24 * 60 * 60 * 1000);

  var consecutiveEmpty = 0;  // 连续无有效评论的轮次
  var consecutiveOld = 0;    // 连续全是过期评论的轮次
  var scroll = 0;

  while (true) {
    // P0: 评论区到底 — 最高优先级，直接停止
    if (uiOperator.findElement("is_comment_end", 500)) {
      logger.info(TAG, "[耗时] 评论已到底(is_comment_end), 停止 (第 " + scroll + " 次滚动)");
      break;
    }

    // P1: 连续3轮无有效评论 → 此视频没有更多可采集数据
    if (consecutiveEmpty >= 3) {
      logger.info(TAG, "[耗时] 连续 " + consecutiveEmpty + " 轮无有效评论, 停止");
      break;
    }

    // P2: 连续3轮评论全部超过 max_age_days → 已滚动到过期区域
    if (consecutiveOld >= 3) {
      logger.info(TAG, "[耗时] 连续 " + consecutiveOld + " 轮评论日期均超过 " + maxAgeDays + " 天, 停止");
      break;
    }

    var tScroll = Date.now();
    var items = uiOperator.findElements("comment_list", 2000);
    if (items.length === 0) { logger.info(TAG, "[耗时] 第 " + scroll + " 次滑动无评论项"); break; }
    logger.info(TAG, "[耗时] 第 " + scroll + " 次滚动, 可见 " + items.length + " 条评论 (耗时 " + (Date.now() - tScroll) + "ms)");

    var validThisScroll = 0;
    var oldThisScroll = 0;

    for (var i = 0; i < items.length; i++) {
      if (collected >= maxComments) break;
      var tItem = Date.now();
      var comment = ReplyCommentHandler._parseCommentItem(items[i]);
      if (!comment) continue;

      // 评论内容去重: 昵称+评论前80字
      var dedupKey = comment.nickname + "|" + comment.text.substring(0, 80);
      if (seenComments[dedupKey]) continue;
      seenComments[dedupKey] = true;

      // 过滤超过 max_age_days 的旧评论
      var commentDate = ReplyCommentHandler._parseTime(comment.time);
      if (commentDate && commentDate < cutoff) { oldThisScroll++; continue; }

      comment._keyword = keyword;
      if (!this._aiQualify(comment)) { logger.debug(TAG, "AI 筛选跳过: " + comment.nickname + " (" + (Date.now() - tItem) + "ms)"); continue; }
      validThisScroll++;

      logger.info(TAG, "[耗时] 符合: " + comment.nickname + " (AI耗时 " + (Date.now() - tItem) + "ms)");
      var commentData = this._collectCommentData(items[i], comment);

      var userData = null;
      var needReopen = false;
      if (!visitedUsers[comment.nickname]) {
        visitedUsers[comment.nickname] = true;
        var tUser = Date.now();
        try {
          userData = this._collectUserData(items[i]);
          logger.info(TAG, "[耗时] 用户数据采集完成: " + (userData ? userData.nickname : "null") + " (" + (Date.now() - tUser) + "ms)");
        } catch (e) { logger.warn(TAG, "用户数据采集失败: " + e.message); }
        needReopen = true;
      }

      // 先上报，确保数据不丢
      this._reportCollection(taskId, keyword, commentData, userData);
      collected++;

      // 再重新打开评论区，失败也不影响已上报的数据
      if (needReopen) {
        if (!this._openComments()) { logger.warn(TAG, "[耗时] 重新打开评论区失败"); break; }
        items = uiOperator.findElements("comment_list", 1000);
      }
    }

    if (collected >= maxComments) {
      logger.info(TAG, "[耗时] 已采集 " + collected + " 条, 达到目标");
      break;
    }

    // Update stopping counters
    if (validThisScroll === 0 && oldThisScroll === 0) {
      consecutiveEmpty++;
      consecutiveOld = 0;
    } else if (validThisScroll === 0 && oldThisScroll > 0) {
      consecutiveEmpty = 0;
      consecutiveOld++;
    } else {
      consecutiveEmpty = 0;
      consecutiveOld = 0;
    }

    scroll++;
    uiOperator.swipeUp();
    sleep(1000);
  }

  logger.info(TAG, "[耗时] 视频采集完成: " + collected + " 条 (总耗时 " + (Date.now() - t0) + "ms)");
  stats.details.push("collected: " + collected);
  stats.success_count += collected;
  return collected > 0;
};

SearchCollectHandler._openComments = function () {
  var commentBtn = uiOperator.findElement("video_comment_btn", 3000);
  if (commentBtn) {
    uiOperator.clickElement(commentBtn);
    sleep(1500);
    return true;
  }
  logger.warn(TAG, "评论入口按钮未找到");
  return false;
};

SearchCollectHandler._aiQualify = function (comment) {
  if (!comment || !comment.text) return false;
  // 本地预过滤：纯表情/无意义评论先拦掉，避免浪费 AI 调用
  // 复用 reply-comment 的成熟正则 (strip [xxx] / 标点 / 非中英文 → len <= 2 跳过)
  var stripped = comment.text
    .replace(/\[[^\]]+\]/g, "")
    .replace(/[\s~!@#$%^&*()_+\-={}|:;<>?,./'"'""'、。！，《》]+/g, "")
    .replace(/[^一-龥a-zA-Z0-9]/g, "")
    .trim();
  if (!stripped || stripped.length <= 2) {
    logger.debug(TAG, "本地筛选跳过(纯表情/短文本): " + comment.text.substring(0, 20));
    return false;
  }
  try {
    var result = aiAnalyzer.analyzeComment({
      searchKeyword: (comment._keyword || ""),
      nickname: comment.nickname,
      commentText: comment.text,
    });
    if (result && typeof result.score === "number") return result.score >= 50;
    return result && result.qualified === true;
  } catch (e) { logger.warn(TAG, "AI分析失败: " + e.message); return false; }
};

SearchCollectHandler._collectCommentData = function (item, comment) {
  // 将原始 UI 时间文本转换为标准 ISO 时间
  var timeStr = comment.time || "";
  var parsed = ReplyCommentHandler._parseTime(timeStr);
  var isoTime = parsed ? parsed.toISOString() : timeStr;

  var data = {
    nickname: comment.nickname, content: comment.text, time_str: isoTime,
    reply_count: "", like_count: "", dislike_count: "", location: "", is_author: comment.isAuthor || false
  };
  var extraFields = {
    "comment_reply_count": "reply_count", "comment_like_count": "like_count",
    "comment_dislike_count": "dislike_count", "comment_location": "location"
  };
  for (var actionName in extraFields) {
    var el = this._findChildBySelector(item, actionName);
    if (el) data[extraFields[actionName]] = this._extractChildValue(el, actionName, "");
  }
  // Strip "· " / "・ " prefix from IP location
  if (data.location) data.location = data.location.replace(/^[·•・\s]+/, "");
  return data;
};

SearchCollectHandler._collectUserData = function (item) {
  var avatarEl = this._findChildBySelector(item, "comment_author_avatar");
  if (!avatarEl) { logger.warn(TAG, "头像未找到"); return null; }
  // Virtual elements (image/coordinate matched) don't have bounds()/clickable()
  if (avatarEl.isImage || avatarEl.isCoordinate) { logger.warn(TAG, "头像为虚拟元素"); return null; }

  // Crop circular avatar from current screen before clicking
  // Uses avatar center point and bounds to create a circular clip
  var avatarBase64 = "";
  try {
    var avatarBounds = avatarEl.bounds();
    if (avatarBounds) {
      var w = avatarBounds.right - avatarBounds.left;
      var h = avatarBounds.bottom - avatarBounds.top;
      var size = Math.min(w, h);
      var cx = avatarBounds.left + w / 2;
      var cy = avatarBounds.top + h / 2;
      var radius = size / 2;
      var left = Math.round(cx - radius);
      var top = Math.round(cy - radius);
      var sz = Math.round(size);

      var screen = null, squareImg = null, srcBitmap = null, outBitmap = null;
      try {
        screen = images.captureScreen();
        squareImg = images.clip(screen, left, top, sz, sz);

        if (squareImg) {
          srcBitmap = squareImg.getBitmap();
          outBitmap = android.graphics.Bitmap.createBitmap(
            sz, sz, android.graphics.Bitmap.Config.ARGB_8888
          );
          var canvas = new android.graphics.Canvas(outBitmap);
          var paint = new android.graphics.Paint();
          paint.setAntiAlias(true);
          paint.setFilterBitmap(true);

          canvas.drawCircle(radius, radius, radius, paint);
          paint.setXfermode(new android.graphics.PorterDuffXfermode(
            android.graphics.PorterDuff.Mode.SRC_IN
          ));
          canvas.drawBitmap(srcBitmap, 0, 0, paint);

          avatarBase64 = images.toBase64(images.fromBitmap(outBitmap), "png");
        }
      } finally {
        if (outBitmap) outBitmap.recycle();
        if (srcBitmap) srcBitmap.recycle();
        if (squareImg) squareImg.recycle();
        if (screen) screen.recycle();
      }
    }
  } catch (e) { logger.debug(TAG, "头像裁剪失败: " + e.message); }

  try {
    avatarEl.clickable() ? avatarEl.click() : click(avatarEl.bounds().centerX(), avatarEl.bounds().centerY());
  } catch (e) { logger.warn(TAG, "头像点击失败"); return null; }
  sleep(2000);

  var isPrivate = "否";
  try { if (uiOperator.findElement("user_is_private", 2000)) isPrivate = "是"; } catch (e) {}

  var data = { nickname: "", douyin_id: "", likes_count: "", follow_count: "",
    fans_count: "", works_count: "", gender: "", age: "", ip_location: "", is_private: isPrivate };

  var fields = {
    "user_nickname": "nickname", "user_douyin_id": "douyin_id",
    "user_likes_count": "likes_count", "user_follow_count": "follow_count",
    "user_fans_count": "fans_count", "user_works_count": "works_count",
    "user_gender": "gender", "user_age": "age", "user_ip_location": "ip_location"
  };
  for (var actionName in fields) {
    var el = uiOperator.findElement(actionName, 2000);
    if (el) {
      var selector = selectorLoader.get(actionName);
      data[fields[actionName]] = (selector && selector.purpose === "extract")
        ? uiOperator.extractValue(el, selector) : (el.text() || "");
    }
  }
  // Strip "· " / "・ " prefix from user IP location
  if (data.ip_location) data.ip_location = data.ip_location.replace(/^[·•・\s]+/, "");

  // Clean numeric fields: extract digits, handle Chinese units (万/千), strip accessibility noise
  var numericFields = { likes_count: 1, follow_count: 1, fans_count: 1, works_count: 1 };
  for (var key in numericFields) {
    if (data[key]) {
      var raw = String(data[key]);
      // Detect "1.2万" / "3.5w" patterns: extract number * multiplier
      var m = raw.match(/([\d.]+)\s*[万wW万]/);
      if (m) {
        data[key] = String(Math.round(parseFloat(m[1]) * 10000));
      } else {
        m = raw.match(/([\d.]+)\s*[千kK千]/);
        if (m) {
          data[key] = String(Math.round(parseFloat(m[1]) * 1000));
        } else {
          var digits = raw.replace(/[^\d]/g, "");
          data[key] = digits || "";
        }
      }
    }
  }

  // Upload avatar if captured
  if (avatarBase64 && data.douyin_id) {
    try { apiClient.uploadUserAvatar(data.douyin_id, avatarBase64); } catch (e) {}
  }

  back(); sleep(1500);
  return data;
};

SearchCollectHandler._reportCollection = function (taskId, keyword, commentData, userData) {
  var payload = { task_id: taskId, keyword: keyword, comment: commentData };
  if (userData) payload.user = userData;
  try {
    var result = apiClient.post("/api/device/collect-report", payload);
    if (result && result.comment_saved) logger.debug(TAG, "已上报: " + commentData.nickname);
  } catch (e) { logger.warn(TAG, "上报失败: " + e.message); }
};

SearchCollectHandler.execute = function (params) {
  var keyword = params.keyword;
  var videoCount = params.video_count || params.count || 5;
  aiAnalyzer.useTemplate(params.prompt_template_id);
  if (!keyword) return { success: false, error: "缺少关键词" };
  logger.info(TAG, "采集: '" + keyword + "', 视频=" + videoCount + ", 每视频评论=" + (params.count || 50));

  var taskId = params.task_id || "";
  if (!this.ensureAppActive()) return { success: false, error: "打开抖音失败" };
  if (!this._openSearch()) return { success: false, error: "打开搜索页失败" };
  if (!this._inputKeyword(keyword)) return { success: false, error: "输入关键词失败" };
  sleep(2000);
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return { success: false, error: "提交搜索失败" };
  }
  sleep(3000);
  this._clickVideoTab();
  sleep(2000);

  var sortBy = params.sort_by || '';
  if (sortBy) {
    this._sortResults(sortBy);
    sleep(1500);
  }

  var stats = { success_count: 0, fail_count: 0, details: [], _taskId: taskId, _keyword: keyword };
  for (var i = 0; i < videoCount; i++) {
    logger.info(TAG, "第 " + (i + 1) + "/" + videoCount + " 个视频");
    if (i === 0) {
      if (!this._clickSearchResult(0)) break;
      sleep(2000);
    } else {
      back(); sleep(500);
      uiOperator.swipeUp();
      sleep(2500);
    }
    if (!this._interactWithVideo("", stats, params)) stats.fail_count++;
    antiDetect.maybePause();
  }
  logger.info(TAG, "采集完成: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

// 复用 reply-comment 的评论解析方法

module.exports = SearchCollectHandler;
