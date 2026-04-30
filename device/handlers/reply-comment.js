// device/handlers/reply-comment.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var uiOperator = require("../core/ui-operator");
var selectorLoader = require("../core/selector-loader");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "评论回复";

/**
 * 评论回复 + 关注 + 私信 Handler
 * 继承 SearchBaseHandler，复用搜索导航逻辑
 *
 * 完整流程:
 * 1. 搜索 → 排序 → 关闭弹出框 → 点击第一个视频
 * 2. 打开评论区
 * 3. 读取评论列表，按时效筛选
 * 4. 对符合条件的评论:
 *    a. AI 分析并生成回复
 *    b. 回复评论
 *    c. 点击评论者头像进入主页
 *    d. 关注
 *    e. 私信
 *    f. 返回评论区
 *
 * params:
 *   - keyword: string (搜索关键词)
 *   - content: string (私信内容，可选)
 *   - count: number (处理数量)
 *   - sort_by: string (排序方式: "latest"|"most_liked")
 *   - max_age_days: number (评论最大天数，默认 5)
 */
var ReplyCommentHandler = Object.create(SearchBaseHandler);

ReplyCommentHandler.execute = function (params) {
  var keyword = params.keyword;
  var content = params.content || "";
  var count = params.count || 5; // 每个视频处理的评论数
  var videoCount = params.video_count || 3; // 处理的视频数
  var sortBy = params.sort_by || "latest";
  var maxAgeDays = params.max_age_days || 5;

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "开始: 关键词='" + keyword + "', 视频数=" + videoCount +
    ", 每视频评论=" + count + ", 排序=" + sortBy + ", 最大天数=" + maxAgeDays + "天");

  if (!this.ensureAppActive()) {
    return { success: false, error: "打开抖音失败" };
  }

  // 1. 搜索 → 排序 → 关闭弹出框（不打开视频）
  if (!this._searchAndSort(keyword, sortBy)) {
    return { success: false, error: "搜索排序失败" };
  }

  var stats = { videos_processed: 0, success_count: 0, fail_count: 0, skipped: 0, details: [] };

  // 2. 逐个视频处理
  for (var v = 0; v < videoCount; v++) {
    logger.info(TAG, "=== 视频 " + (v + 1) + "/" + videoCount + " ===");

    // 2a. 点击第 v 个视频
    if (!this._clickSearchResult(v)) {
      logger.warn(TAG, "点击视频 " + (v + 1) + " 失败，停止处理");
      break;
    }
    sleep(2000);

    // 2b. 打开评论区
    if (!this._openComments()) {
      logger.warn(TAG, "视频 " + (v + 1) + " 打开评论区失败");
      back();
      sleep(1000);
      continue;
    }

    // 2c. 读取评论
    var comments = this._readComments(count * 2);
    logger.info(TAG, "读取 " + comments.length + " 条评论");

    // 2d. 按时效筛选
    var filtered = this._filterByTime(comments, maxAgeDays);
    logger.info(TAG, "时效筛选后: " + filtered.length + " 条评论");

    // 2e. 逐条处理评论
    var processed = 0;
    for (var i = 0; i < filtered.length && processed < count; i++) {
      var comment = filtered[i];
      logger.info(TAG, "分析评论 " + (i + 1) + "/" + filtered.length +
        ": [" + comment.nickname + "] " + comment.text.substring(0, 30));

      // AI 五维度分析
      var analysis = aiAnalyzer.analyzeComment({
        searchKeyword: keyword,
        nickname: comment.nickname,
        commentText: comment.text,
      });

      if (!analysis) {
        logger.warn(TAG, "AI 分析失败，跳过");
        stats.skipped++;
        continue;
      }

      logger.info(TAG, "分数=" + analysis.score + ", 层级=" + analysis.tier +
        ", 意图=" + (analysis.dimensions ? analysis.dimensions.intent : "未知"));

      // 检查分数阈值
      if (analysis.score < aiAnalyzer.SCORE_THRESHOLD) {
        logger.info(TAG, "分数 " + analysis.score + " 低于阈值，跳过");
        stats.skipped++;
        continue;
      }

      // 检查水军/同行
      if (analysis.dimensions && analysis.dimensions.lead_quality) {
        var lq = analysis.dimensions.lead_quality;
        if (lq.is_bot || lq.is_competitor) {
          logger.info(TAG, "检测到水军/同行，跳过");
          stats.skipped++;
          continue;
        }
      }

      // 回复评论
      logger.info(TAG, "回复: '" + analysis.reply.substring(0, 30) + "...'");
      var replySuccess = this._replyToComment(analysis.reply);
      if (!replySuccess) {
        stats.fail_count++;
        continue;
      }

      stats.success_count++;
      stats.details.push({
        video: v + 1,
        nickname: comment.nickname,
        score: analysis.score,
        tier: analysis.tier,
        intent: analysis.dimensions ? analysis.dimensions.intent : "unknown",
        reply: analysis.reply,
      });

      // 点击头像进入主页
      sleep(1000);
      var profileEntered = this._enterCommenterProfile(comment.nickname);
      if (!profileEntered) {
        logger.warn(TAG, "进入主页失败，跳过关注+私信");
        processed++;
        antiDetect.maybePause();
        continue;
      }

      // 关注
      this._followUser();
      sleep(1000);

      // 私信
      if (content) {
        var dmContent = content;
        if (analysis.tier === "high") {
          dmContent = this._generateDMGreeting(keyword, comment.nickname, comment.text, analysis);
        }
        this._sendDM(dmContent);
        sleep(1000);
      }

      // 返回评论区
      this._returnToComments();
      sleep(1500);

      processed++;
      antiDetect.maybePause();
    }

    // 返回搜索结果页
    back();
    sleep(1500);

    stats.videos_processed++;
    antiDetect.maybePause();
  }

  logger.info(TAG, "完成. " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 搜索 → 排序 → 关闭弹出框（不打开视频）
 * @param {string} keyword
 * @param {string} sortBy
 * @returns {boolean}
 */
ReplyCommentHandler._searchAndSort = function (keyword, sortBy) {
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
  return true;
};

/**
 * 打开评论区
 */
ReplyCommentHandler._openComments = function () {
  // 点击评论区入口（通常是底部的评论图标）
  var clicked = this.safeClick("comment_input", 3);
  if (clicked) {
    sleep(2000);
    return true;
  }
  return false;
};

/**
 * 读取评论列表
 * 使用服务端下发的选择器查找评论列表
 * @param {number} maxCount - 最多读取数量
 * @returns {Array} [{ nickname, text, time, element }]
 */
ReplyCommentHandler._readComments = function (maxCount) {
  var comments = [];

  try {
    // 使用选择器系统查找评论列表
    var commentList = uiOperator.findElement("comment_list", 5000);

    if (!commentList) {
      logger.warn(TAG, "评论列表未找到");
      return comments;
    }

    // findElement 返回的是 UiObject，需要获取子元素
    var children = commentList.children();
    logger.info(TAG, "评论列表共 " + children.length + " 条");

    for (var i = 0; i < Math.min(children.length, maxCount); i++) {
      var item = children[i];
      var comment = this._parseCommentItem(item);
      if (comment) {
        comments.push(comment);
      }
    }
  } catch (e) {
    logger.error(TAG, "读取评论出错: " + e.message);
  }

  return comments;
};

/**
 * 解析单条评论
 * 使用服务端下发的选择器策略查找子元素
 * @param {UiObject} item - 评论项元素
 * @returns {Object|null} { nickname, text, time, element }
 */
ReplyCommentHandler._parseCommentItem = function (item) {
  try {
    // 使用选择器系统查找昵称
    var nicknameEl = this._findChildBySelector(item, "comment_author");
    // 备用：第一个可点击的 TextView
    if (!nicknameEl) {
      nicknameEl = item.findOne(clickable(true).className("android.widget.TextView"));
    }
    var nickname = nicknameEl ? nicknameEl.text() : "unknown";

    // 使用选择器系统查找评论文本
    var textEl = this._findChildBySelector(item, "comment_text");
    // 备用：最长的 TextView
    if (!textEl) {
      var textViews = item.find(className("android.widget.TextView"));
      var maxLen = 0;
      for (var i = 0; i < textViews.length; i++) {
        var t = textViews[i].text() || "";
        if (t.length > maxLen && t !== nickname) {
          maxLen = t.length;
          textEl = textViews[i];
        }
      }
    }
    var text = textEl ? textEl.text() : "";
    if (!text) return null;

    // 使用选择器系统查找时间
    var timeEl = this._findChildBySelector(item, "comment_time");
    var timeStr = timeEl ? timeEl.text() : "";

    return {
      nickname: nickname,
      text: text,
      time: timeStr,
      element: item,
    };
  } catch (e) {
    logger.warn(TAG, "解析评论项出错: " + e.message);
    return null;
  }
};

/**
 * 在父元素内按选择器策略查找子元素
 * @param {UiObject} parent - 父元素
 * @param {string} actionName - 选择器动作名
 * @returns {UiObject|null}
 */
ReplyCommentHandler._findChildBySelector = function (parent, actionName) {
  var selector = selectorLoader.get(actionName);
  if (!selector) return null;

  var strategies = selector.strategies.slice().sort(function (a, b) {
    return a.priority - b.priority;
  });

  for (var i = 0; i < strategies.length; i++) {
    var s = strategies[i];
    var element = null;
    switch (s.type) {
      case "id":
        element = parent.findOne(id(s.value));
        break;
      case "text":
        element = parent.findOne(text(s.value));
        break;
      case "desc":
        element = parent.findOne(desc(s.value));
        break;
      case "className":
        element = parent.findOne(className(s.value));
        break;
    }
    if (element) return element;
  }
  return null;
};

/**
 * 按时效筛选评论
 * @param {Array} comments
 * @param {number} maxAgeDays
 * @returns {Array} 筛选后的评论
 */
ReplyCommentHandler._filterByTime = function (comments, maxAgeDays) {
  var now = new Date();
  var cutoff = new Date(now.getTime() - maxAgeDays * 24 * 60 * 60 * 1000);

  var filtered = [];
  for (var i = 0; i < comments.length; i++) {
    var comment = comments[i];
    var commentDate = this._parseTime(comment.time);

    if (!commentDate) {
      // 无法解析时间，默认保留
      filtered.push(comment);
      continue;
    }

    if (commentDate >= cutoff) {
      filtered.push(comment);
    } else {
      logger.debug(TAG, "过滤过期评论: " + comment.time + " > " + maxAgeDays + "天");
    }
  }

  return filtered;
};

/**
 * 解析评论时间
 * 支持格式:
 * - "刚刚"
 * - "X分钟前", "X小时前", "X天前"
 * - "MM-DD", "YYYY-MM-DD"
 * @param {string} timeStr
 * @returns {Date|null}
 */
ReplyCommentHandler._parseTime = function (timeStr) {
  if (!timeStr) return null;

  var now = new Date();

  // "刚刚"
  if (timeStr.indexOf("刚刚") !== -1) {
    return now;
  }

  // "X秒前"
  var secMatch = timeStr.match(/(\d+)\s*秒前/);
  if (secMatch) {
    return new Date(now.getTime() - parseInt(secMatch[1]) * 1000);
  }

  // "X分钟前"
  var minMatch = timeStr.match(/(\d+)\s*分钟前/);
  if (minMatch) {
    return new Date(now.getTime() - parseInt(minMatch[1]) * 60 * 1000);
  }

  // "X小时前"
  var hourMatch = timeStr.match(/(\d+)\s*小时前/);
  if (hourMatch) {
    return new Date(now.getTime() - parseInt(hourMatch[1]) * 60 * 60 * 1000);
  }

  // "X天前"
  var dayMatch = timeStr.match(/(\d+)\s*天前/);
  if (dayMatch) {
    return new Date(now.getTime() - parseInt(dayMatch[1]) * 24 * 60 * 60 * 1000);
  }

  // "MM-DD" (当年)
  var mdMatch = timeStr.match(/^(\d{1,2})-(\d{1,2})$/);
  if (mdMatch) {
    return new Date(now.getFullYear(), parseInt(mdMatch[1]) - 1, parseInt(mdMatch[2]));
  }

  // "YYYY-MM-DD"
  var ymdMatch = timeStr.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (ymdMatch) {
    return new Date(parseInt(ymdMatch[1]), parseInt(ymdMatch[2]) - 1, parseInt(ymdMatch[3]));
  }

  logger.warn(TAG, "无法解析时间: " + timeStr);
  return null;
};

/**
 * 回复评论
 * @param {string} replyText - 回复内容
 * @returns {boolean}
 */
ReplyCommentHandler._replyToComment = function (replyText) {
  // 点击回复按钮
  var replyClicked = this.safeClick("comment_reply_button", 2);
  if (!replyClicked) {
    logger.warn(TAG, "回复按钮未找到");
    return false;
  }
  sleep(1000);

  // 输入回复内容
  var inputResult = this.safeInput("comment_input", replyText);
  if (!inputResult) {
    logger.warn(TAG, "输入回复内容失败");
    return false;
  }
  sleep(500);

  // 发送
  var submitClicked = this.safeClick("comment_submit", 3);
  if (!submitClicked) {
    logger.warn(TAG, "提交回复失败");
    return false;
  }

  sleep(1500);
  logger.info(TAG, "回复已发送: '" + replyText.substring(0, 20) + "'");
  return true;
};

/**
 * 进入评论者主页
 * @param {string} nickname - 评论者昵称
 * @returns {boolean}
 */
ReplyCommentHandler._enterCommenterProfile = function (nickname) {
  // 点击评论者头像
  var avatarClicked = this.safeClick("comment_author_avatar", 2);
  if (!avatarClicked) {
    // 备用：点击昵称
    try {
      var nameEl = text(nickname).findOne(3000);
      if (nameEl) {
        nameEl.parent().click();
        sleep(2000);
        return true;
      }
    } catch (e) {
      logger.warn(TAG, "点击昵称失败: " + e.message);
    }
    return false;
  }
  sleep(2000);
  return true;
};

/**
 * 关注用户
 */
ReplyCommentHandler._followUser = function () {
  var followed = this.safeClick("follow_button", 2);
  if (followed) {
    logger.info(TAG, "关注成功");
  } else {
    logger.warn(TAG, "关注按钮未找到（可能已关注）");
  }
};

/**
 * 发送私信
 * @param {string} content - 私信内容
 */
ReplyCommentHandler._sendDM = function (content) {
  // 点击私信按钮
  var messageClicked = this.safeClick("message_button", 3);
  if (!messageClicked) {
    logger.warn(TAG, "私信按钮未找到");
    return false;
  }
  sleep(1500);

  // 输入私信内容
  var inputResult = this.safeInput("dm_input", content);
  if (!inputResult) {
    logger.warn(TAG, "输入私信内容失败");
    return false;
  }
  sleep(500);

  // 发送
  var sendClicked = this.safeClick("dm_send", 3);
  if (!sendClicked) {
    logger.warn(TAG, "发送私信失败");
    return false;
  }

  sleep(1000);
  logger.info(TAG, "私信已发送: '" + content.substring(0, 20) + "'");
  return true;
};

/**
 * 返回评论区（从用户主页返回）
 */
ReplyCommentHandler._returnToComments = function () {
  // 返回两次：第一次退出私信/主页，第二次回到评论区
  back();
  sleep(1000);
  back();
  sleep(1000);
  // 重新打开评论区（如果返回后评论区关闭了）
  this._openComments();
};

/**
 * 为高质量线索生成个性化私信招呼语
 * @param {string} searchKeyword
 * @param {string} nickname
 * @param {string} commentText
 * @param {Object} analysis - AI 分析结果
 * @returns {string} 私信内容
 */
ReplyCommentHandler._generateDMGreeting = function (searchKeyword, nickname, commentText, analysis) {
  // 基于意图生成不同的招呼语
  var intent = analysis.dimensions ? analysis.dimensions.intent : "other";
  var greeting = "";

  switch (intent) {
    case "buy_intent":
      greeting = "你好，看到你在评论区问" + searchKeyword + "的事，可以聊聊~";
      break;
    case "compare_intent":
      greeting = "你好，看到你在对比" + searchKeyword + "，有些经验可以分享";
      break;
    case "consult_intent":
      greeting = "你好，关于" + searchKeyword + "的问题，可以交流下~";
      break;
    default:
      greeting = "你好，看到你也关注" + searchKeyword + "，认识一下~";
  }

  return greeting;
};

module.exports = ReplyCommentHandler;
