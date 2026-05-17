// device/handlers/search-collect.js
var SearchBaseHandler = require("./search-base");
var uiOperator = require("../core/ui-operator");
var aiAnalyzer = require("../core/ai-analyzer");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");
var commentUtils = require("./comment-utils");

var TAG = "采集";

var SearchCollectHandler = Object.create(SearchBaseHandler);

SearchCollectHandler._interactWithVideo = function (content, stats, params) {
  params = params || {};
  var taskId = (stats._taskId || "");
  var keyword = (stats._keyword || "");
  this._currentDest = aiAnalyzer.resolveDestination(keyword);
  var t0 = Date.now();

  // 防止上个视频评论区残留：若已在评论页，先退回到视频页
  if (uiOperator.isOnPage("is_comment_view")) {
    logger.info(TAG, "[耗时] 检测到评论面板残留，back 回到视频页");
    back();
    sleep(800);
  }

  var dataSourceType = uiOperator.findElement("is_shopping_cart", 500) ? 1 : 0;
  logger.info(TAG, "[耗时] 数据来源类型: " + (dataSourceType === 1 ? "带货视频" : "普通视频"));

  // 预检评论数：零评论视频点评论按钮会直接唤起键盘，提前跳过
  var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
  var commentCount = -1;
  if (commentBtn && !commentBtn.isImage && !commentBtn.isCoordinate) {
    try {
      var rawDesc = commentBtn.desc() || "";
      logger.info(TAG, "[耗时] 评论按钮 desc: '" + rawDesc + "'");
      var numMatch = rawDesc.match(/(\d+)/);
      if (numMatch) commentCount = parseInt(numMatch[1]);
    } catch (e) {}
  }
  logger.info(TAG, "[耗时] 评论数: " + (commentCount >= 0 ? commentCount : "未知"));
  if (commentCount === 0) {
    logger.info(TAG, "[耗时] 该视频无评论，跳过 (耗时 " + (Date.now() - t0) + "ms)");
    return false;
  }

  logger.info(TAG, "[耗时] 尝试打开评论区...");
  if (!this._openComments()) {
    logger.warn(TAG, "[耗时] 评论区打开失败, 跳过此视频 (耗时 " + (Date.now() - t0) + "ms)");
    return false;
  }
  logger.info(TAG, "[耗时] 评论区已打开 (耗时 " + (Date.now() - t0) + "ms)");

  var collected = 0;
  var visitedUsers = {};
  var seenComments = {};
  var maxComments = (params.count === -1) ? Infinity : (params.count || 50);

  var maxAgeDays = (params.max_age_days === -1) ? Infinity : (params.max_age_days || 30);
  var now = new Date();
  var cutoff = (maxAgeDays === Infinity) ? new Date(0) : new Date(now.getTime() - maxAgeDays * 24 * 60 * 60 * 1000);

  var consecutiveEmpty = 0;
  var consecutiveOld = 0;
  var scroll = 0;
  var reopenFailed = false;

  while (true) {
    if (consecutiveEmpty >= 5) {
      logger.info(TAG, "[耗时] 连续 " + consecutiveEmpty + " 轮无有效评论, 停止");
      break;
    }

    if (consecutiveOld >= 5) {
      logger.info(TAG, "[耗时] 连续 " + consecutiveOld + " 轮评论日期均超过 " + maxAgeDays + " 天, 停止");
      break;
    }

    var tScroll = Date.now();
    var items = uiOperator.findElements("comment_list", 2000);
    if (items.length === 0) { logger.info(TAG, "[耗时] 第 " + scroll + " 次滑动无评论项"); break; }
    logger.info(TAG, "[耗时] ══ 第 " + scroll + " 轮滚动, 可见 " + items.length + " 条评论 (查找耗时 " + (Date.now() - tScroll) + "ms)");

    var validThisScroll = 0;
    var oldThisScroll = 0;
    var localSkipped = 0;
    var aiSkipped = 0;
    var dupSkipped = 0;
    var tScrollStart = Date.now();

    for (var i = 0; i < items.length; i++) {
      if (collected >= maxComments) break;
      var tItem = Date.now();
      var comment = commentUtils.parseCommentItem(items[i], this);
      if (!comment) { logger.debug(TAG, "  [" + i + "] 解析失败 (" + (Date.now() - tItem) + "ms)"); continue; }

      // ① 本地过滤: 纯表情/短文本 + 提示词模板 exclude 关键词
      if (!commentUtils.localPreFilter(comment.text)) {
        localSkipped++;
        logger.debug(TAG, "  [" + i + "] 本地淘汰(纯表情/短文本): " + comment.nickname + " (" + (Date.now() - tItem) + "ms)");
        continue;
      }
      var localCheck = aiAnalyzer._localRelevanceCheck(comment.text);
      if (localCheck === false) {
        localSkipped++;
        logger.info(TAG, "  [" + i + "] 本地淘汰(exclude): " + comment.nickname + " (" + (Date.now() - tItem) + "ms)");
        continue;
      }

      // ② 时效过滤
      var tAge = Date.now();
      var commentDate = commentUtils.parseTime(comment.time);
      if (!commentDate || commentDate < cutoff) {
        oldThisScroll++;
        logger.debug(TAG, "  [" + i + "] 过期: " + comment.nickname + " (" + (Date.now() - tItem) + "ms)");
        continue;
      }

      // ③ 查重过滤
      var dedupKey = comment.nickname + "|" + comment.text.substring(0, 80);
      if (seenComments[dedupKey]) { dupSkipped++; continue; }
      seenComments[dedupKey] = true;

      // ④ AI 语义分析（最昂贵，放最后）
      comment._keyword = keyword;
      var tAI = Date.now();
      if (!this._aiQualify(comment)) { aiSkipped++; logger.info(TAG, "  [" + i + "] AI淘汰: " + comment.nickname + " (前置" + (tAI - tItem) + "ms + AI " + (Date.now() - tAI) + "ms)"); continue; }
      validThisScroll++;

      logger.info(TAG, "  [" + i + "] ★符合: " + comment.nickname + " (前置" + (tAI - tItem) + "ms + AI " + (Date.now() - tAI) + "ms)");
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

      this._reportCollection(taskId, keyword, commentData, userData, dataSourceType);
      collected++;

      if (needReopen) {
        if (!this._openComments()) {
          logger.warn(TAG, "[耗时] 重新打开评论区失败，停止本视频采集");
          reopenFailed = true;
          break;
        }
        items = uiOperator.findElements("comment_list", 2000);
      }
    }

    if (reopenFailed) {
      logger.info(TAG, "[耗时] 评论区重开失败，停止 (已采集 " + collected + " 条)");
      break;
    }

    if (collected >= maxComments) {
      logger.info(TAG, "[耗时] 已采集 " + collected + " 条, 达到目标");
      break;
    }

    // 本轮滚动耗时摘要
    logger.info(TAG, "[耗时] ══ 第 " + scroll + " 轮完成: 符合=" + validThisScroll + " AI淘汰=" + aiSkipped + " 过期=" + oldThisScroll + " 本地淘汰=" + localSkipped + " 重复=" + dupSkipped + " (处理耗时 " + (Date.now() - tScrollStart) + "ms)");

    if (validThisScroll === 0 && oldThisScroll === 0) {
      if (aiSkipped > 0) {
        consecutiveEmpty = 0;  // 有评论但AI筛选未过，不计入空滚
      } else {
        consecutiveEmpty++;
      }
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
    sleep(500);

    if (uiOperator.findElement("is_comment_end", 500)) {
      logger.info(TAG, "[耗时] 评论已到底(is_comment_end), 停止 (第 " + scroll + " 次滚动)");
      break;
    }
  }

  logger.info(TAG, "[耗时] 视频采集完成: " + collected + " 条 (总耗时 " + (Date.now() - t0) + "ms)");
  stats.details.push("collected: " + collected);
  stats.success_count += collected;
  return collected > 0;
};

SearchCollectHandler._openComments = function () {
  return commentUtils.openComments();
};

SearchCollectHandler._aiQualify = function (comment) {
  if (!comment || !comment.text) return false;
  try {
    var result = aiAnalyzer.analyzeComment({
      searchKeyword: (comment._keyword || ""),
      nickname: comment.nickname,
      commentText: comment.text,
    });
    if (result && typeof result.score === "number") return result.score >= 40;
    return result && result.qualified === true;
  } catch (e) { logger.warn(TAG, "AI分析失败: " + e.message); return false; }
};

SearchCollectHandler._collectCommentData = function (item, comment) {
  var timeStr = comment.time || "";
  var parsed = commentUtils.parseTime(timeStr);
  var isoTime = parsed ? parsed.toISOString() : timeStr;

  var data = {
    nickname: comment.nickname, content: comment.text, time_str: isoTime,
    reply_count: "", like_count: "", dislike_count: "", location: "", is_author: comment.isAuthor || false,
  };
  var dest = this._currentDest;
  if (dest) {
    data.intended_province = dest.province || "";
    data.intended_city = dest.city || "";
    data.intended_attraction = dest.attraction || "";
  }
  var extraFields = {
    "comment_reply_count": "reply_count", "comment_like_count": "like_count",
    "comment_dislike_count": "dislike_count", "comment_location": "location"
  };
  for (var actionName in extraFields) {
    var el = this._findChildBySelector(item, actionName);
    if (el) data[extraFields[actionName]] = this._extractChildValue(el, actionName, "");
  }
  if (data.location) data.location = data.location.replace(/^[·•・\s]+/, "");
  return data;
};

SearchCollectHandler._collectUserData = function (item) {
  var avatarEl = this._findChildBySelector(item, "comment_author_avatar");
  if (!avatarEl) { logger.warn(TAG, "头像未找到"); return null; }
  if (avatarEl.isImage || avatarEl.isCoordinate) { logger.warn(TAG, "头像为虚拟元素"); return null; }

  var avatarBase64 = commentUtils._cropCircularAvatar(avatarEl);

  try {
    var b = avatarEl.bounds();
    if (avatarEl.clickable()) {
      avatarEl.click();
    } else if (b) {
      press(b.centerX(), b.centerY(), 80);
    }
  } catch (e) { logger.warn(TAG, "头像点击失败"); return null; }
  sleep(1700);

  var data = commentUtils.collectProfileData({ uploadAvatar: false });

  if (avatarBase64 && data && data.douyin_id) {
    try { apiClient.uploadUserAvatar(data.douyin_id, avatarBase64); } catch (e) {}
  }

  back(); sleep(300);
  return data;
};

SearchCollectHandler._reportCollection = function (taskId, keyword, commentData, userData, dataSourceType) {
  var payload = { task_id: taskId, keyword: keyword, comment: commentData, data_source_type: dataSourceType || 0 };
  if (userData) payload.user = userData;
  var result = apiClient.collectReport(payload);
  if (result && result.comment_saved) logger.debug(TAG, "已上报: " + commentData.nickname);
};

SearchCollectHandler.execute = function (params) {
  aiAnalyzer.useTemplate(params.prompt_template_id);
  if (!this.ensureAppActive()) return { success: false, error: "打开抖音失败" };

  var taskId = params.task_id || "";

  // 分享链接模式
  if (params.share_links && params.share_links.length > 0) {
    var links = params.share_links;
    logger.info(TAG, "分享链接采集: " + links.length + " 个链接, 关键词='" + (params.keyword || "") + "', 每视频评论=" + (params.count || 50));
    var linkStats = { success_count: 0, fail_count: 0, details: [], _taskId: taskId, _keyword: params.keyword || "" };

    for (var li = 0; li < links.length; li++) {
      var link = (links[li] || "").trim();
      if (!link) continue;
      logger.info(TAG, "第 " + (li + 1) + "/" + links.length + " 个链接: " + link.substring(0, 40) + "...");

      if (!this._openSearch()) { linkStats.fail_count++; continue; }
      var urlMatch = link.match(/https?:\/\/v\.douyin\.com\/[A-Za-z0-9_?=&%]+\/?/);
      var pasteText = urlMatch ? urlMatch[0] : link;
      if (!this._inputKeyword(pasteText)) { linkStats.fail_count++; continue; }
      sleep(300);
      if (!this._submitSearch()) { linkStats.fail_count++; continue; }
      sleep(2000);
      if (!uiOperator.isOnPage("is_video_view")) {
        logger.info(TAG, "未自动跳转视频页，尝试点击搜索结果");
        this._clickSearchResult(0);
        sleep(1700);
      }

      if (!this._interactWithVideo("", linkStats, params)) linkStats.fail_count++;
      this.safeClick("comment_off_btn", 2);
      sleep(400);
      this._backToSearchResults();
    }
    logger.info(TAG, "链接采集完成: " + JSON.stringify(linkStats));
    return { success: true, result: linkStats };
  }

  // 关键词搜索模式
  var keyword = params.keyword;
  var videoCount = (params.video_count === -1) ? 200 : (params.video_count || params.count || 5);
  if (!keyword) return { success: false, error: "缺少关键词或分享链接" };
  logger.info(TAG, "采集: '" + keyword + "', 视频=" + videoCount + ", 每视频评论=" + (params.count || 50));

  if (!this._openSearch()) return { success: false, error: "打开搜索页失败" };
  if (!this._inputKeyword(keyword)) return { success: false, error: "输入关键词失败" };
  sleep(1000);
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return { success: false, error: "提交搜索失败" };
  }
  sleep(2000);
  this._clickVideoTab();
  sleep(1000);

  var sortBy = params.sort_by || '';
  if (sortBy) {
    this._sortResults(sortBy);
    sleep(800);
  }

  var stats = { success_count: 0, fail_count: 0, details: [], _taskId: taskId, _keyword: keyword };
  for (var i = 0; i < videoCount; i++) {
    logger.info(TAG, "第 " + (i + 1) + "/" + videoCount + " 个视频");
    if (i === 0) {
      if (!this._clickSearchResult(0)) break;
      sleep(1700);
    } else {
      // 开关评论区后已在视频播放页，直接上滑切换到下一个搜索结果视频
      uiOperator.swipeUp();
      sleep(1500);
    }
    if (!this._interactWithVideo("", stats, params)) stats.fail_count++;
    // 确保评论区关闭，防止残留到下一个视频
    this.safeClick("comment_off_btn", 2);
    sleep(400);
    if (uiOperator.isOnPage("is_comment_view")) {
      logger.info(TAG, "评论区未关闭，back 兜底");
      back();
      sleep(500);
    }
  }
  shell("am start -a android.intent.action.VIEW -d 'snssdk1128://search/result'", true);
  sleep(2000);
  logger.info(TAG, "采集完成: " + JSON.stringify(stats));
  return { success: true, result: stats };
};


module.exports = SearchCollectHandler;
