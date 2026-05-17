// device/handlers/search-collect.js
var CommentBaseHandler = require("./comment-base");
var uiOperator = require("../core/ui-operator");
var aiAnalyzer = require("../core/ai-analyzer");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");
var commentUtils = require("./comment-utils");

var TAG = "采集";

var SearchCollectHandler = Object.create(CommentBaseHandler);

SearchCollectHandler._config = { videoTimeoutMs: 0, interVideoDelay: 1500 };

SearchCollectHandler.execute = function (params) {
  if (params.share_links && params.share_links.length > 0) {
    return this._executeShareLinks(params);
  }
  return CommentBaseHandler.execute.call(this, params);
};

SearchCollectHandler._beforeSearch = function (params) {
  this._currentDest = aiAnalyzer.resolveDestination(params.keyword);
};

SearchCollectHandler._initStats = function (params) {
  return { success_count: 0, fail_count: 0, details: [],
    _taskId: params.task_id || "", _keyword: params.keyword || "" };
};

SearchCollectHandler._shouldProcessVideo = function (params, videoIndex) {
  // 残留在评论区则先退出
  if (uiOperator.isOnPage("is_comment_view")) {
    logger.info(TAG, "[耗时] 检测到评论面板残留，back 回到视频页");
    back();
    sleep(800);
  }
  return CommentBaseHandler._shouldProcessVideo.call(this, params, videoIndex);
};

SearchCollectHandler._closeComments = function () {
  this.safeClick("comment_off_btn", 2);
  sleep(400);
  if (uiOperator.isOnPage("is_comment_view")) {
    logger.info(TAG, "评论区未关闭，back 兜底");
    back();
    sleep(500);
  }
};

SearchCollectHandler._processComments = function (params, stats, videoIndex) {
  var keyword = params.keyword;
  var taskId = params.task_id || "";
  var maxComments = (params.count === -1) ? Infinity : (params.count || 50);
  var maxAgeDays = (params.max_age_days === -1) ? Infinity : (params.max_age_days || 30);
  var now = new Date();
  var cutoff = (maxAgeDays === Infinity) ? new Date(0) : new Date(now.getTime() - maxAgeDays * 24 * 60 * 60 * 1000);

  var dataSourceType = uiOperator.findElement("is_shopping_cart", 500) ? 1 : 0;
  logger.info(TAG, "[耗时] 数据来源类型: " + (dataSourceType === 1 ? "带货视频" : "普通视频"));

  var collected = 0;
  var visitedUsers = {};
  var seenComments = {};
  var consecutiveEmpty = 0;
  var consecutiveOld = 0;
  var scroll = 0;
  var reopenFailed = false;
  var t0 = Date.now();

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

      if (!commentUtils.localPreFilter(comment.text)) {
        localSkipped++;
        logger.debug(TAG, "  [" + i + "] 本地淘汰(纯表情/短文本): " + comment.nickname);
        continue;
      }
      var localCheck = aiAnalyzer._localRelevanceCheck(comment.text);
      if (localCheck === false) {
        localSkipped++;
        logger.info(TAG, "  [" + i + "] 本地淘汰(exclude): " + comment.nickname);
        continue;
      }

      var commentDate = commentUtils.parseTime(comment.time);
      if (!commentDate || commentDate < cutoff) {
        oldThisScroll++;
        logger.debug(TAG, "  [" + i + "] 过期: " + comment.nickname);
        continue;
      }

      var dedupKey = comment.nickname + "|" + comment.text.substring(0, 80);
      if (seenComments[dedupKey]) { dupSkipped++; continue; }
      seenComments[dedupKey] = true;

      comment._keyword = keyword;
      var tAI = Date.now();
      if (!this._aiQualify(comment)) { aiSkipped++; logger.info(TAG, "  [" + i + "] AI淘汰: " + comment.nickname); continue; }
      validThisScroll++;

      logger.info(TAG, "  [" + i + "] ★符合: " + comment.nickname);
      var commentData = this._collectCommentData(items[i], comment);

      var userData = null;
      var needReopen = false;
      if (!visitedUsers[comment.nickname]) {
        visitedUsers[comment.nickname] = true;
        try {
          userData = this._collectUserData(items[i]);
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

    logger.info(TAG, "[耗时] ══ 第 " + scroll + " 轮完成: 符合=" + validThisScroll + " AI淘汰=" + aiSkipped + " 过期=" + oldThisScroll + " 本地淘汰=" + localSkipped + " 重复=" + dupSkipped);

    if (validThisScroll === 0 && oldThisScroll === 0) {
      consecutiveEmpty = aiSkipped > 0 ? 0 : consecutiveEmpty + 1;
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
  if (params.share_links && params.share_links.length > 0) {
    return this._executeShareLinks(params);
  }
  return CommentBaseHandler.execute.call(this, params);
};

SearchCollectHandler._executeShareLinks = function (params) {
  var links = params.share_links;
  var taskId = params.task_id || "";
  logger.info(TAG, "分享链接采集: " + links.length + " 个链接, 关键词='" + (params.keyword || "") + "'");
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

    if (!CommentBaseHandler._shouldProcessVideo.call(this, params, 0)) { linkStats.fail_count++; }
    else if (commentUtils.openComments()) {
      this._processComments(params, linkStats, 0);
    } else { linkStats.fail_count++; }

    this.safeClick("comment_off_btn", 2);
    sleep(400);
    this._backToSearchResults();
  }
  logger.info(TAG, "链接采集完成: " + JSON.stringify(linkStats));
  return { success: true, result: linkStats };
};


module.exports = SearchCollectHandler;
