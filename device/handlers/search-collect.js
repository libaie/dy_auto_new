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

SearchCollectHandler._interactWithVideo = function (content, stats) {
  var taskId = (stats._taskId || "");
  var keyword = (stats._keyword || "");

  if (!this._openComments()) return false;

  var collected = 0;
  var visitedUsers = {};
  var maxComments = 50;
  var maxScroll = 20;

  for (var scroll = 0; scroll < maxScroll; scroll++) {
    var items = uiOperator.findElements("comment_list", 3000);
    if (items.length === 0) break;

    for (var i = 0; i < items.length; i++) {
      if (collected >= maxComments) break;
      var comment = ReplyCommentHandler._parseCommentItem(items[i]);
      if (!comment) continue;
      comment._keyword = keyword;
      if (!this._aiQualify(comment)) continue;

      logger.info(TAG, "符合: " + comment.nickname);
      var commentData = this._collectCommentData(items[i], comment);

      var userData = null;
      if (!visitedUsers[comment.nickname]) {
        visitedUsers[comment.nickname] = true;
        userData = this._collectUserData(items[i]);
      }

      this._reportCollection(taskId, keyword, commentData, userData);
      collected++;
    }

    if (collected >= maxComments) break;
    uiOperator.swipeUp();
    sleep(2000);
  }

  logger.info(TAG, "视频采集完成: " + collected);
  stats.details.push("collected: " + collected);
  stats.success_count += collected;
  return collected > 0;
};

SearchCollectHandler._openComments = function () {
  var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
  if (commentBtn) {
    uiOperator.clickElement(commentBtn);
    sleep(1500);
    return true;
  }
  // 兜底：评论按钮通常在屏幕右侧，坐标点击
  logger.info(TAG, "策略未找到评论入口，坐标兜底");
  click(device.width * 0.92, device.height * 0.55);
  sleep(1500);
  // 验证是否打开了评论面板
  if (uiOperator.findElement("is_comment_view", 2000)) return true;
  if (uiOperator.findElement("comment_list", 2000)) return true;
  logger.warn(TAG, "评论入口打开失败");
  return false;
};

SearchCollectHandler._aiQualify = function (comment) {
  if (!comment || !comment.text) return false;
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
  var data = {
    nickname: comment.nickname, content: comment.text, time_str: comment.time,
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
  return data;
};

SearchCollectHandler._collectUserData = function (item) {
  var avatarEl = this._findChildBySelector(item, "comment_author_avatar");
  if (!avatarEl) { logger.warn(TAG, "头像未找到"); return null; }

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
  var count = params.count || 5;
  aiAnalyzer.useTemplate(params.prompt_template_id);
  if (!keyword) return { success: false, error: "缺少关键词" };
  logger.info(TAG, "采集: '" + keyword + "', 视频=" + count);

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
  for (var i = 0; i < count; i++) {
    logger.info(TAG, "第 " + (i + 1) + "/" + count + " 个视频");
    if (i === 0) {
      if (!this._clickSearchResult(0)) break;
      sleep(2000);
    } else {
      back(); sleep(500);
      uiOperator.swipeUp();
      sleep(2500);
    }
    if (!this._interactWithVideo("", stats)) stats.fail_count++;
    antiDetect.maybePause();
  }
  logger.info(TAG, "采集完成: " + JSON.stringify(stats));
  uiOperator.closeApp();
  return { success: true, result: stats };
};

// 复用 reply-comment 的评论解析方法

module.exports = SearchCollectHandler;
