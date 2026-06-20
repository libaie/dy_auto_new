// device/handlers/reply-comment.js
var CommentBaseHandler = require("./comment-base");
var aiAnalyzer = require("../core/ai-analyzer");
var uiOperator = require("../core/ui-operator");
var selectorLoader = require("../core/selector-loader");
var antiDetect = require("../core/anti-detect");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");
var commentUtils = require("./comment-utils");
var crashRecovery = require("../core/crash-recovery");
var humanInput = require("../core/human-input");

var TAG = "评论回复";
var flowContext = require("../core/flow-context");

var ReplyCommentHandler = Object.create(CommentBaseHandler);

ReplyCommentHandler._config = { videoTimeoutMs: 120000, interVideoDelay: 2500, defaultVideoCount: 3 };

ReplyCommentHandler._beforeSearch = function (params) {
  this._dest = aiAnalyzer.resolveDestination(params.keyword);
};

ReplyCommentHandler._initStats = function (params) {
  return { videos_processed: 0, success_count: 0, fail_count: 0, skipped: 0,
    follow_count: 0, dm_count: 0, details: [] };
};

ReplyCommentHandler._onVideoSkipped = function (params, stats, videoIndex) {
  stats.videos_processed++;
};

ReplyCommentHandler._ensureCommentsOpen = function (params, videoIndex) {
  var videoStartTime = Date.now();
  var VIDEO_TIMEOUT = this._config.videoTimeoutMs;
  for (var retry = 0; retry < 2; retry++) {
    if (Date.now() - videoStartTime > VIDEO_TIMEOUT) break;
    this.safeClick("video_comment_btn", 2);
    // 显式等待评论面板滑入动画完成
    if (uiOperator.waitForPage("is_comment_view", 4000)) {
      flowContext.enter("comment");
      return true;
    }
    logger.info(TAG, "评论区未打开，重试 (" + (retry + 1) + "/2)");
  }
  logger.warn(TAG, "评论区打开失败，跳过此视频");
  return false;
};

ReplyCommentHandler._processComments = function (params, stats, videoIndex) {
  var keyword = params.keyword;
  var content = params.content || "";
  var readAllMode = params.count === -1;
  var skipReply = params.skip_reply === true;  // 只关注+私信，不回复评论
  var maxPerVideo = params.max_comments_per_video || 50;
  // skipReply + readAllMode: 回复配额不限制阅读（只关注+私信，需读完全量）
  if (skipReply && readAllMode) { maxPerVideo = 999999; }
  var HARD_MAX_READ = 300;
  var count;
  if (readAllMode) {
    var detectedCount = this._currentVideoCommentCount || 0;
    var targetRead = (detectedCount > 0) ? Math.min(detectedCount, HARD_MAX_READ) : HARD_MAX_READ;
    count = targetRead;
    logger.info(TAG, "全量评论模式: targetRead=" + targetRead +
      " (detected=" + detectedCount + ", hardMax=" + HARD_MAX_READ + ", 有效回复上限=" + maxPerVideo + ")");
  } else {
    count = params.count || 5;
  }
  var maxAgeSecs;
  if (params.max_age_seconds !== undefined && params.max_age_seconds !== null) {
    maxAgeSecs = params.max_age_seconds;
  } else {
    var days = params.max_age_days;
    if (days === undefined || days === null) days = 5;
    maxAgeSecs = (days === -1) ? -1 : days * 86400;
  }
  var maxAgeMs = (maxAgeSecs === -1) ? Infinity : maxAgeSecs * 1000;
  // 单任务上限默认对齐日上限 — 日上限才是真正的风控防线
  var maxFollows = (params.max_follows != null) ? params.max_follows : (params.server_daily_limit_follow || params.max_daily_follow || 100);
  var maxDMs = (params.max_dms != null) ? params.max_dms : (params.max_daily_dm || 75);
  var taskId = params.task_id || "";
  var dest = this._dest;
  var VIDEO_TIMEOUT = this._config.videoTimeoutMs;

  // 当有 DM 序列时，扩展视频超时以容纳 cooldown
  var hasDMSequence = !!(params.dm_sequence_id || (params.dm_messages && params.dm_messages.length > 0));
  var dmCooldownMs = params.inter_user_cooldown_ms || (Math.floor(Math.random() * 100000) + 100000);
  if (hasDMSequence && dmCooldownMs > 0) {
    var maxDMsThisTask = maxDMs;
    VIDEO_TIMEOUT = Math.max(VIDEO_TIMEOUT, maxDMsThisTask * dmCooldownMs + 60000);
  }

  function _reportProgress(step, detail, prog) {
    if (taskId) { try { apiClient.reportProgress(taskId, step, detail, prog); } catch (e) {} }
  }

  // 日DM计数器
  function _getServerDate() {
    // 优先用服务端日期（main.js catchUpPoll 设置）
    if (ReplyCommentHandler._serverDate) return ReplyCommentHandler._serverDate;
    var d = new Date();
    return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
  }

  function _getDailyDMCount() {
    var dateKey = _getServerDate();
    return ReplyCommentHandler._storageGet("dm_daily_" + dateKey, 0);
  }

  function _incrementDailyDMCount() {
    var dateKey = _getServerDate();
    var current = ReplyCommentHandler._storageGet("dm_daily_" + dateKey, 0);
    ReplyCommentHandler._storageSet("dm_daily_" + dateKey, current + 1);

    // 清理3天前过期计数器
    try {
      var cacheDir = ReplyCommentHandler._getCacheDir();
      var flist = files.listDir(cacheDir);
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 3);
      var cutoffKey = "dm_daily_" + cutoff.getFullYear() + "-" + (cutoff.getMonth() + 1) + "-" + cutoff.getDate();
      for (var fi = 0; fi < flist.length; fi++) {
        if (flist[fi].indexOf("dm_daily_") === 0 && flist[fi] < cutoffKey) {
          try { files.remove(cacheDir + "/" + flist[fi]); } catch (e) {}
        }
      }
    } catch (e) {}

    return current + 1;
  }


  function _getDailyReplyCount() {
    var dateKey = _getServerDate();
    return ReplyCommentHandler._storageGet("reply_daily_" + dateKey, 0);
  }

  function _incrementDailyReplyCount() {
    var dateKey = _getServerDate();
    var current = ReplyCommentHandler._storageGet("reply_daily_" + dateKey, 0);
    ReplyCommentHandler._storageSet("reply_daily_" + dateKey, current + 1);
    return current + 1;
  }

  function _getDailyFollowCount() {
    var dateKey = _getServerDate();
    return ReplyCommentHandler._storageGet("follow_daily_" + dateKey, 0);
  }

  function _incrementDailyFollowCount() {
    var dateKey = _getServerDate();
    var current = ReplyCommentHandler._storageGet("follow_daily_" + dateKey, 0);
    ReplyCommentHandler._storageSet("follow_daily_" + dateKey, current + 1);
    return current + 1;
  }

  // 用服务端每日计数初始化本地计数器，保证日志与服务端同步
  function _syncDailyCounters() {
    var dateKey = _getServerDate();
    logger.info(TAG, "开始同步每日计数 (date=" + dateKey + " srvReply=" + params.server_today_reply + " srvFollow=" + params.server_today_follow + " srvDM=" + params.server_today_dm + ")");
    var synced = 0;
    if (params.server_today_reply != null) {
      var localReply = ReplyCommentHandler._storageGet("reply_daily_" + dateKey, 0);
      ReplyCommentHandler._storageSet("reply_daily_" + dateKey, Math.max(localReply, params.server_today_reply));
      synced++;
    }
    if (params.server_today_follow != null) {
      var localFollow = ReplyCommentHandler._storageGet("follow_daily_" + dateKey, 0);
      ReplyCommentHandler._storageSet("follow_daily_" + dateKey, Math.max(localFollow, params.server_today_follow));
      synced++;
    }
    if (params.server_today_dm != null) {
      var localDM = ReplyCommentHandler._storageGet("dm_daily_" + dateKey, 0);
      ReplyCommentHandler._storageSet("dm_daily_" + dateKey, Math.max(localDM, params.server_today_dm));
      synced++;
    }
    if (synced === 0) {
      logger.warn(TAG, "每日计数同步失败: server_today_* 均为 null，params 缺少服务端注入字段");
    }
  }
  _syncDailyCounters();
  var videoStartTime = Date.now();
  var processed = 0;  // finite mode: effective comments that reached AI analysis
  var uniqueRead = 0; // read-all mode: unique parsed comments seen in the UI
  var totalRead = 0;
  var emptyStreak = 0;
  var advanceOnlyStreak = 0;
  var stopCurrentVideo = false;
  var seenComments = {};

  function _commentKey(comment) {
    // 只按昵称+内容去重，不参与 time — 同一评论在 RecyclerView 复用/二次解析时
    // 相对时间（如"3小时前"）的 parseTime 依赖 new Date() 会变化，导致同一评论
    // 被判定为不同 key，产生重复 collectReport
    var nick = comment && comment.nickname ? comment.nickname : "";
    var text = comment && comment.text ? comment.text : "";
    return nick + "|" + text;
  }

  function _hasCommentEndMarker() {
    try {
      if (!selectorLoader._cache || !selectorLoader._cache.is_comment_end) return false;
      return !!uiOperator.findElement("is_comment_end", 500);
    } catch (e) {
      return false;
    }
  }

  function _advanceAfterSkip(reason) {
    var progress = readAllMode
      ? ("已读" + uniqueRead + "/" + count + ", 有效" + processed)
      : ("有效" + processed + "/" + count + ", 已读" + uniqueRead);
    logger.info(TAG, "跳过当前评论(" + (reason || "未分类") + "): " + progress);
    advanceOnlyStreak++;
    if (advanceOnlyStreak >= 12) {
      logger.info(TAG, "连续跳过推进 " + advanceOnlyStreak + " 次仍未形成新进度，停止当前视频评论处理");
      stopCurrentVideo = true;
      return;
    }
    // 不在 for 循环内滑动——滑动会使 items[i+1..n] 变 StaleReference
    // 统一由 while 循环末尾的 _swipeCommentList() 执行
  }

  while ((readAllMode ? uniqueRead : processed) < count && !stopCurrentVideo) {
    if (Date.now() - videoStartTime > VIDEO_TIMEOUT) {
      logger.warn(TAG, "视频 " + (videoIndex + 1) + " 处理超时 (" +
        Math.round((Date.now() - videoStartTime) / 1000) + "s)，强制跳过");
      break;
    }

    // 动态快照：每次迭代重新获取控件树，防止 RecyclerView 复用导致 StaleReference
    var findStart = Date.now();
    var items = uiOperator.findElements("comment_list", 3000);
    var findCost = Date.now() - findStart;
    if (findCost > 5000 || items.length === 0) {
      logger.info(TAG, "comment_list 查询结果: count=" + items.length + ", cost=" + findCost + "ms");
    }
    if (items.length === 0) {
      // ==== 空列表原因诊断：弹窗遮挡 vs 真正到底 ====
      var stillOnComment = uiOperator.isOnPage("is_comment_view");

      if (!stillOnComment) {
        // 评论区已关闭/未识别。这里不能滑动，否则外层视频循环还会再滑一次，导致跳过一个视频。
        emptyStreak++;
        logger.warn(TAG, "comment_list 为空且评论区未识别为打开，尝试恢复当前视频评论区 (" + emptyStreak + "/2)");
        if (emptyStreak === 1) {
          try {
            if (this._openComments()) {
              sleep(800);
              continue;
            }
          } catch (e) {
            logger.warn(TAG, "重新打开评论区失败: " + e.message);
          }
        }
        logger.info(TAG, "评论区已关闭或无法恢复，停止当前视频评论处理");
        break;
      }

      // 评论区开着但 items 为空 — 弹窗/浮窗/半透明遮罩抢夺了无障碍焦点
      logger.warn(TAG, "评论区打开但列表为空，疑似弹窗遮挡，尝试解除");
      crashRecovery.handleDialogs();
      sleep(600);

      // 解除后重试获取
      findStart = Date.now();
      items = uiOperator.findElements("comment_list", 2000);
      findCost = Date.now() - findStart;
      if (findCost > 4000 || items.length === 0) {
        logger.info(TAG, "comment_list 重试结果: count=" + items.length + ", cost=" + findCost + "ms");
      }
      if (items.length === 0) {
        emptyStreak++;
        // 提高阈值 + 交叉确认 is_comment_end 才退出
        if (emptyStreak >= 3 && _hasCommentEndMarker()) {
          logger.info(TAG, "评论已到底(is_comment_end)，停止（可见" + items.length + "条/已读" + totalRead + "条）");
          break;
        }
        if (emptyStreak >= 5) {
          logger.info(TAG, "连续" + emptyStreak + "轮为空且无结束标记，强制停止（疑似无限弹窗）");
          break;
        }
        uiOperator.swipeUp();
        sleep(1500);
        continue;
      }
      // 弹窗解除后 items 恢复 → 继续正常处理
      emptyStreak = 0;
      logger.info(TAG, "弹窗已解除，评论列表恢复 (" + items.length + " 条)");
    } else {
      emptyStreak = 0;
    }

    // 遍历当前屏所有可见评论，处理完再滑动
    var roundHadNew = false;
    for (var i = 0; i < items.length && (readAllMode ? uniqueRead : processed) < count; i++) {
      try {
        var comment = this._parseCommentItem(items[i]);
        if (!comment) {
          stats.skipped++;
          continue;
        }

        var commentKey = _commentKey(comment);
        if (seenComments[commentKey]) {
          continue;
        }
        seenComments[commentKey] = true;
        uniqueRead++;
        totalRead = uniqueRead;
        advanceOnlyStreak = 0;
        roundHadNew = true;
        logger.info(TAG, "读取评论 " + uniqueRead + "/" + count + ": [" + comment.nickname + "] " + ((comment.text || "").substring(0, 30)));

      if (comment.nickname === "unknown" || !comment.text ||
          comment.text.indexOf("发条评论") !== -1) {
        stats.skipped++;
        _advanceAfterSkip("昵称或正文无效");
        continue;
      }

      if (comment.isAuthor) {
        stats.skipped++;
        _advanceAfterSkip("作者评论");
        continue;
      }

      if (!this._filterByTime([comment], maxAgeMs).length) {
        stats.skipped++;
        _advanceAfterSkip("超出时间范围");
        continue;
      }

      if (!commentUtils.localPreFilter(comment.text)) {
        logger.debug(TAG, "跳过无意义评论（纯表情/短文本）: " + comment.text.substring(0, 20));
        stats.skipped++;
        _advanceAfterSkip("本地预过滤");
        continue;
      }

      var canReply = true;
      try {
        var claimResult = apiClient.claimCommentReply(comment.nickname, comment.text);
        canReply = claimResult && claimResult.claimed;
      } catch (e) {}
      if (!canReply) {
        stats.skipped++;
        _advanceAfterSkip("全局去重");
        continue;
      }

      var analysis = aiAnalyzer.analyzeComment({
        searchKeyword: keyword,
        nickname: comment.nickname,
        commentText: comment.text,
      });

      if (!analysis) {
        stats.skipped++;
        _advanceAfterSkip("AI分析为空");
        continue;
      }

      processed++;
      advanceOnlyStreak = 0;
      logger.info(TAG, "分析 " + (readAllMode ? (uniqueRead + "/" + count) : (processed + "/" + count)) +
        ": [" + comment.nickname + "] " + comment.text.substring(0, 30));

      logger.info(TAG, "分数=" + analysis.score + ", 层级=" + analysis.tier +
        ", 意图=" + (analysis.dimensions ? analysis.dimensions.intent : "未知"));

      if (analysis.score < aiAnalyzer.SCORE_THRESHOLD) {
        logger.info(TAG, "分数 " + analysis.score + " 低于阈值，跳过");
        stats.skipped++;
        _advanceAfterSkip("低分");
        continue;
      }

      if (analysis.dimensions && analysis.dimensions.lead_quality) {
        var lq = analysis.dimensions.lead_quality;
        if (lq.is_bot || lq.is_competitor) {
          logger.info(TAG, "检测到水军/同行，跳过");
          stats.skipped++;
          _advanceAfterSkip("水军或同行");
          continue;
        }
      }

      // 回复（skipReply=true 时跳过，只做关注+私信）
      var replySuccess = skipReply;
      if (!skipReply) {
        logger.debug(TAG, "回复: '" + analysis.reply.substring(0, 30) + "...'");
        if (comment.replyBtn) {
          logger.info(TAG, "点击回复按钮...");
          comment.replyBtn.click();
        } else {
          logger.info(TAG, "无回复按钮，直接输入");
        }
        logger.info(TAG, "开始输入回复...");
        if (this._replyToComment(analysis.reply, comment.nickname)) {
          replySuccess = true;
          stats.success_count++;
          try { apiClient.incrementStats(params.account_id, "reply_comment", comment.nickname || "", 1); } catch (e) {}
          var dailyReply = _incrementDailyReplyCount();
          logger.info(TAG, "当日回复: " + dailyReply + "/" + (params.server_daily_limit_reply != null ? params.server_daily_limit_reply : (params.max_daily_reply || 200)));
          try { apiClient.saveCommentAIReply(comment.nickname, comment.text, analysis.reply, taskId, dest ? dest.province : null, dest ? dest.city : null, dest ? dest.attraction : null); } catch (e) {}
          // collectReport 统一在用户主页采集后发送（含 ai_reply + user），避免重复记录
        } else {
          stats.fail_count++;
          try { apiClient.releaseCommentReply(comment.nickname, comment.text); } catch (e) {}
          continue;
        }
      }

      stats.details.push({
        video: videoIndex + 1, nickname: comment.nickname,
        comment: comment.text,
        score: analysis.score, tier: analysis.tier,
        intent: analysis.dimensions ? analysis.dimensions.intent : "unknown",
        reply: analysis.reply,
      });

      // 关注+私信
      sleep(Math.floor(Math.random() * 500 + 800));
      var shouldFollow = analysis.tier === "high" || analysis.tier === "medium";
      var shouldDM = analysis.tier === "high" || analysis.tier === "medium";
      var canFollow = shouldFollow && stats.follow_count < maxFollows;
      var canDM = shouldDM && stats.dm_count < maxDMs;
      if (shouldDM && !canDM) {
        logger.warn(TAG, "单任务DM已达上限(" + stats.dm_count + "/" + maxDMs + ")，跳过后续私信");
      }
      if (shouldFollow && !canFollow) {
        logger.warn(TAG, "单任务关注已达上限(" + stats.follow_count + "/" + maxFollows + ")，跳过后续关注");
      }
      // 协调 per-task maxFollows 与日上限（-1 = 不限）
      var maxDailyFollow = params.server_daily_limit_follow != null
        ? params.server_daily_limit_follow
        : (params.max_daily_follow || 100);
      if (maxDailyFollow !== -1) {
        var followTodayRemaining = maxDailyFollow - _getDailyFollowCount();
        if (canFollow && followTodayRemaining <= 0) {
          logger.warn(TAG, "当日关注已达上限(" + maxDailyFollow + ")，跳过关注");
          canFollow = false;
        }
      }
      // 协调 per-task maxDMs 与日上限（-1 = 不限）
      var maxDaily = params.max_daily_dm || 75;
      if (maxDaily !== -1) {
        var todayRemaining = maxDaily - _getDailyDMCount();
        if (canDM && todayRemaining <= 0) {
          logger.warn(TAG, "当日DM已达上限(" + maxDaily + ")，跳过私信");
          canDM = false;
        }
      }
      if (canFollow || canDM) {
        if (this._enterCommenterProfile(comment.commentAuthorAvatarEl, comment.nickname)) {
          var profileStart = Date.now();
          var PROFILE_TIMEOUT = hasDMSequence
            ? Math.max(30000, (dmCooldownMs || 0) + 15000)
            : 30000;

          var isPrivate = !!uiOperator.findElement("user_is_private", 2000);
          if (isPrivate) {
            logger.info(TAG, "私密账号，跳过关注，仅尝试私信");
            canFollow = false;
          }
          {
            var userData = this._collectProfileData();
            if (userData) {
              var lastDetail = stats.details[stats.details.length - 1];
              if (lastDetail) lastDetail.user = userData;
              userData._keyword = keyword;
              userData._taskId = taskId;
              if (dest) {
                userData._intended_province = dest.province || "";
                userData._intended_city = dest.city || "";
                userData._intended_attraction = dest.attraction || "";
              }
              try { apiClient.saveUserProfile(userData); } catch (e) {}
              try { apiClient.collectReport({
                task_id: taskId, keyword: keyword,
                comment: {
                  nickname: comment.nickname, content: comment.text,
                  time_str: commentUtils.toBeijingTime(comment.time), is_author: comment.isAuthor || false,
                  reply_count: "", like_count: "", ai_reply: analysis.reply,
                },
                user: userData, data_source_type: 0,
              }); } catch (e) {}
            } else {
              // Profile data extraction failed, but still report the comment with ai_reply
              try { apiClient.collectReport({
                task_id: taskId, keyword: keyword,
                comment: {
                  nickname: comment.nickname, content: comment.text,
                  time_str: commentUtils.toBeijingTime(comment.time), is_author: comment.isAuthor || false,
                  reply_count: "", like_count: "", ai_reply: analysis.reply,
                },
                data_source_type: 0,
              }); } catch (e) {}
            }
            if (Date.now() - profileStart < PROFILE_TIMEOUT && canFollow && this._followUser()) {
              stats.follow_count++;
              try { apiClient.incrementStats(params.account_id, "follow", (userData && userData.uniqueId) || "", 1); } catch (e) {}
              var dailyFollow = _incrementDailyFollowCount();
              logger.info(TAG, "当日关注: " + dailyFollow + "/" + (params.server_daily_limit_follow != null ? params.server_daily_limit_follow : (params.max_daily_follow || 100)));
            }
            sleep(Math.floor(Math.random() * 500 + 800));

            // DM cooldown: 发送前等待冷却时间，序列和单条共用
            if (canDM && this._lastDMSendTime) {
              var cooldownRemaining = (dmCooldownMs || 0) - (Date.now() - this._lastDMSendTime);
              if (cooldownRemaining > 0) {
                logger.info(TAG, "DM冷却等待 " + Math.round(cooldownRemaining / 1000) + "s");
              var chunkMs = 30000;
              var waited = 0;
              while (waited < cooldownRemaining) {
                var step = Math.min(chunkMs, cooldownRemaining - waited);
                sleep(step);
                waited += step;
                if (waited < cooldownRemaining) {
                  try { device.wakeUpIfNeeded(); } catch(e) {}
                }
              }
              }
            }

            logger.info(TAG, "DM check: canDM=" + canDM + " shouldDM=" + shouldDM +
              " perTask=" + stats.dm_count + "/" + maxDMs +
              " daily=" + _getDailyDMCount() + "/" + (params.max_daily_dm || 75) +
              " profileAge=" + Math.round((Date.now() - profileStart)/1000) + "s/" + Math.round(PROFILE_TIMEOUT/1000) + "s");
            if (Date.now() - profileStart < PROFILE_TIMEOUT && canDM) {
              var dmContent = "";
              var dmIntent = "other";
              try {
                dmIntent = (analysis.dimensions && analysis.dimensions.intent) || "other";
                if (!hasDMSequence) {
                  var aiDM = aiAnalyzer.generateDM({
                    searchKeyword: keyword, nickname: comment.nickname,
                    commentText: comment.text, tier: dmIntent,
                    intendedCity: (dest && (dest.city || dest.attraction || dest.province)) || "",
                  });
                  if (aiDM) dmContent = aiDM;
                }
              } catch (e) {}
              if (!hasDMSequence && !dmContent && content) dmContent = content;
              if (hasDMSequence || dmContent) {
                var recipientId = (userData && userData.douyin_id) || this._buildFallbackRecipientId(comment.nickname || "unknown");
                var dmClaimResult = apiClient.claimDMRecipient({
                  account_id: params.account_id,
                  recipient_douyin_id: recipientId,
                  recipient_nickname: comment.nickname
                });
                if (dmClaimResult && dmClaimResult.claimed) {
                  var sendResults = [];
                  var sentCount = 0;
                  if (hasDMSequence) {
                    var seqMsgs = this.resolveMessages(params);
                    if (!seqMsgs || !seqMsgs.length) { seqMsgs = []; }
                    var dmBtnOk = this.safeClick("dm_entry_btn", 5);
                    if (dmBtnOk) { sleep(1500); }
                    if (dmBtnOk && seqMsgs.length > 0) {
                      sendResults = this._sendMessageSequence(seqMsgs, stats, keyword);
                    } else if (seqMsgs.length > 0) {
                      sendResults = this._buildDMFailureResults(seqMsgs, keyword, dmBtnOk ? "私信内容为空" : "私信按钮未找到");
                    }
                    sentCount = this._countSentDMResults(sendResults);
                  } else {
                    var singleSent = this._sendDM(dmContent);
                    sendResults = [{
                      order: 1,
                      content: dmContent,
                      status: singleSent ? "sent" : "failed",
                      error_message: singleSent ? null : "私信发送失败",
                      sent_at: new Date().toISOString()
                    }];
                    sentCount = singleSent ? 1 : 0;
                  }
                  this._reportDMSendResults(dmClaimResult.conversation_id, sendResults, params, dmIntent, dmIntent, keyword);
                  if (sentCount > 0) {
                    stats.dm_count++;
                    try { apiClient.incrementStats(params.account_id, "search_dm", recipientId, 1); } catch (e) {}
                    if (hasDMSequence) {
                      this._lastDMSendTime = Date.now();
                      var dailyCount = _incrementDailyDMCount();
                      logger.info(TAG, "当日DM: " + dailyCount + "/" + (params.server_daily_limit_dm != null ? params.server_daily_limit_dm : (params.max_daily_dm || 75)));
                    }
                  } else if (sendResults.length === 0) {
                    apiClient.releaseDMRecipient({ conversation_id: dmClaimResult.conversation_id });
                  }
                } else {
                  logger.info(TAG, "用户 " + comment.nickname + " 已被其他设备 DM，跳过");
                }
              }
              sleep(Math.floor(Math.random() * 500 + 800));
            }
          }

          if (Date.now() - profileStart > PROFILE_TIMEOUT) {
            logger.warn(TAG, "主页操作超时 (" + Math.round((Date.now() - profileStart) / 1000) + "s)，强制返回");
          }

          this._returnToComments();
          var onComment = uiOperator.isOnPage("is_comment_view");
          if (!onComment) {
            back(); sleep(800);
            this._openComments();
            sleep(1500);
            onComment = uiOperator.isOnPage("is_comment_view");
          }
          if (!onComment) {
            logger.warn(TAG, "返回评论区失败，跳过后续评论");
            processed = count;
            uniqueRead = count;
            break;
          }
          videoStartTime = Date.now();
          // 关注/DM 已导航离开评论区，打断 for 循环，由 while 顶部重新 fetch 控件树
          break;
        } else {
          logger.warn(TAG, "进入主页失败，跳过关注+私信");
          this._dismissKeyboard();
          // 主页进入失败，仍需上报评论（含 ai_reply）
          try { apiClient.collectReport({
            task_id: taskId, keyword: keyword,
            comment: {
              nickname: comment.nickname, content: comment.text,
              time_str: commentUtils.toBeijingTime(comment.time), is_author: comment.isAuthor || false,
              reply_count: "", like_count: "", ai_reply: analysis.reply,
            },
            data_source_type: 0,
          }); } catch (e) {}
        }
      } else {
        // 无需关注+私信（低层级或配额已满），仅上报评论数据
        try { apiClient.collectReport({
          task_id: taskId, keyword: keyword,
          comment: {
            nickname: comment.nickname, content: comment.text,
            time_str: commentUtils.toBeijingTime(comment.time), is_author: comment.isAuthor || false,
            reply_count: "", like_count: "", ai_reply: analysis.reply,
          },
          data_source_type: 0,
        }); } catch (e) {}
      }
      sleep(1000);

      _reportProgress("视频 " + (videoIndex + 1) + "/" + params.video_count,
        "已回复 " + stats.success_count + " 条，跳过 " + stats.skipped + " 条",
        (videoIndex + (readAllMode ? uniqueRead : processed) / count) / (params.video_count || 3));
      antiDetect.maybePause();
      } catch (e) {
        logger.error(TAG, "处理评论异常: " + e.message + "，跳过继续");
        stats.skipped++;
        try { this._returnToComments(); } catch (e2) {}
      }
    }  // for 循环结束：当前屏所有可见评论已遍历

    // 退出条件：有效回复达标 OR 指定数量读完 OR 到底
    if (readAllMode) {
      if (processed >= maxPerVideo) {
        logger.info(TAG, "有效回复达标 " + processed + "/" + maxPerVideo + "（已读" + uniqueRead + "条）");
        break;
      }
    } else {
      if (processed >= count) {
        logger.info(TAG, "已读完指定数量 " + processed + "/" + count + "（已读" + uniqueRead + "条）");
        break;
      }
    }
    if (_hasCommentEndMarker()) {
      logger.info(TAG, "评论已到底(is_comment_end)，停止（已读" + uniqueRead + "条，有效" + processed + "）");
      break;
    }

    if (readAllMode ? (processed < maxPerVideo) : (processed < count)) {
      if (_hasCommentEndMarker()) {
        logger.info(TAG, "评论已到底(is_comment_end)，停止（已读" + totalRead + "条）");
        break;
      }
      // 统一滑动：for 循环内不滑，此处滑一次推进到下一屏
      var sx2 = device.width * (0.35 + Math.random() * 0.2);
      var sy2 = device.height * (0.80 + Math.random() * 0.08);
      var ex2 = sx2 + Math.floor(Math.random() * 30 + 20);
      var ey2 = device.height * (0.50 + Math.random() * 0.06);
      var dur2 = Math.floor(Math.random() * 150 + 400);
      gestures([0, dur2, [sx2, sy2], [ex2, ey2]]);
      sleep(600);
      // 控件树刷新由 while 循环顶部动态快照执行
    }
  }
};

/**
 * 打开评论区 — 点击视频评论入口按钮
 */
ReplyCommentHandler._openComments = function () {
  return commentUtils.openComments();
};

/**
 * 读取评论列表
 * 使用 findElements 直接获取所有评论控件（不走 children）
 * 支持滑动加载更多评论
 * @param {number} maxCount - 最多读取数量
 * @returns {Array} [{ nickname, text, time, element }]
 */
ReplyCommentHandler._readComments = function (maxCount) {
  var comments = [];

  try {
    // 等待评论面板打开
    sleep(1000);

    // 使用 findElements 直接获取评论控件数组
    var items = uiOperator.findElements("comment_list", 5000);
    if (!items || items.length === 0) {
      logger.warn(TAG, "评论列表未找到或为空");
      return comments;
    }
    logger.info(TAG, "评论列表: " + items.length + " 条");

    // 滑动加载更多直到满足数量要求
    var maxScroll = 10;
    var lastProcessed = 0; // 已处理到的下标，避免重复解析
    for (var scroll = 0; scroll < maxScroll && comments.length < maxCount; scroll++) {
      for (var i = lastProcessed; i < items.length && comments.length < maxCount; i++) {
        var comment = this._parseCommentItem(items[i]);
        if (comment) {
          comments.push(comment);
        }
      }
      lastProcessed = items.length;

      if (comments.length < maxCount) {
        logger.info(TAG, "已读取 " + comments.length + "/" + maxCount + " 条，滑动加载更多...");
        uiOperator.swipeUp();
        sleep(1500);
        items = uiOperator.findElements("comment_list", 3000);
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
  var result = commentUtils.parseCommentItem(item, this);
  if (result) result.element = item;  // 保持向后兼容
  return result;
};


/**
 * 按时效筛选评论
 * @param {Array} comments
 * @param {number} maxAgeDays
 * @returns {Array} 筛选后的评论
 */
ReplyCommentHandler._filterByTime = function (comments, maxAgeMs) {
  return commentUtils.filterByTime(comments, maxAgeMs);
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
  return commentUtils.parseTime(timeStr);
};

/**
 * 回复评论
 * 流程: 点回复(键盘唤起+输入框聚焦) → input()模拟打字 → 图找图发送
 */
ReplyCommentHandler._replyToComment = function (replyText, nickname) {
  // 1. 点回复按钮 → 键盘唤起，输入框自动获得焦点
  // if (!this.safeClick("comment_reply_button", 3)) {
  //   logger.warn(TAG, "回复按钮未找到");
  //   return false;
  // }
  // sleep(1000);

  // 2. 输入文字：input() 直接模拟键盘打字（输入框已聚焦，比 setText/粘贴都可靠）
  // 安全裁剪：AI 可能误加前缀
  var cleanText = replyText;
  // 裁剪「回复 @昵称」
  if (nickname) {
    var prefix = "回复 @" + nickname;
    if (cleanText.indexOf(prefix) === 0) {
      cleanText = cleanText.substring(prefix.length).replace(/^\s*/, "");
    }
  }
  // 裁剪 AI 误输出的元格式「评论'xxx' → 回复：'yyy'」，只保留 yyy 部分
  var arrowIdx = cleanText.indexOf("→ 回复：");
  if (arrowIdx !== -1) {
    cleanText = cleanText.substring(arrowIdx + 5).replace(/^['\"\s]+/, "").replace(/['\"]+$/, "");
  }
  var pasted = false;
  try {
    var focusedNode = className("EditText").focused(true).findOne(3000);
    if (focusedNode) {
        focusedNode.setText(" ");
        sleep(200);
        for (var di = 0; di < 5; di++) { shell("input keyevent 67", false); }
        sleep(100);
    }
    // 分块模拟真人打字：2-3 个词一起敲、单字单独敲，块间随机延迟
    var pos = 0;
    while (pos < cleanText.length) {
      var chunkSize = Math.random() < 0.4 ? 1 : (Math.floor(Math.random() * 2) + 2);  // 40% 单字, 60% 2-3字
      chunkSize = Math.min(chunkSize, cleanText.length - pos);
      var chunk = cleanText.substring(pos, pos + chunkSize);
      input(chunk);
      pos += chunkSize;
      sleep(Math.floor(Math.random() * 250 + 150));  // 150-400ms 块间停顿
    }
    pasted = true;
    logger.debug(TAG, "input 输入成功: " + cleanText.substring(0, 20) + "'");
  } catch (e) {
    logger.warn(TAG, "input 异常: " + e.message);
  }

  // 3. 兜底：剪贴板 + keyevent 279 粘贴
  if (!pasted) {
    try {
      setClip(cleanText);
      sleep(200);
      shell("input keyevent 279", false);
      sleep(500);
      pasted = true;
    } catch (e) { /* ignore */ }
  }

  // 4. 兜底：setText
  if (!pasted) {
    try {
      var et = className("EditText").findOne(1000);
      if (et) { et.setText(replyText); pasted = true; }
    } catch (e2) { /* ignore */ }
  }

  if (!pasted) {
    logger.warn(TAG, "输入失败");
    back(); sleep(500);
    return false;
  }
  sleep(500);

  // 5. 以图找图点击发送按钮（comment_submit 使用 image 策略）
  var sent = false;
  var sendBtn = uiOperator.findElement("comment_submit", 3000);
  if (sendBtn) {
    uiOperator.clickElement(sendBtn);
    sleep(1200);
    sent = true;
    logger.debug(TAG, "回复已发送(图找图): " + replyText.substring(0, 20) + "'");
  }

  // 兜底：回车发送
  if (!sent) {
    logger.info(TAG, "comment_submit 未找到，尝试回车发送");
    try { shell("input keyevent 66", false); } catch (e) { /* ignore */ }
    back();
    sleep(1200);
    sent = true;  // Enter 后假定发送成功（无法验证）
  }

  return sent;
};

/**
 * 关闭输入键盘
 */
/**
 * 安全关闭键盘 — 仅在非评论区页面使用 back
 * 评论区用 back 会关闭评论面板，所以评论面板内不调用此方法
 */
ReplyCommentHandler._dismissKeyboard = function () {
  // 如果在评论面板，不用 back（会退出评论）
  if (uiOperator.findElement("is_comment_view", 300)) {
    return;
  }
  // 在视频详情页/个人主页/私信页，back 安全
  try { back(); sleep(500); } catch (e) { /* ignore */ }
};

/**
 * 进入评论者主页
 * @param {string} nickname - 评论者昵称
 * @returns {boolean}
 */
ReplyCommentHandler._enterCommenterProfile = function (commentAuthorAvatarEl, nickname) {
  // 先判断目标评论者昵称是否可见（昵称可见=头像在同一行可见）
  var nameVisible = false;
  try { nameVisible = !!text(nickname).findOne(500); } catch (e) {}
  if (!nameVisible) {
    logger.info(TAG, "头像不可见，评论列表内滚动查找目标评论");
    var rv = uiOperator.findElement("comment_list", 1000);
    // 在列表区域下拉——先小幅滚动查找近处评论，再大幅滚动扫长列表
    if (rv && !rv.isImage && !rv.isCoordinate) {
      try {
        var rvb = rv.bounds();
        var rvcx = rvb.centerX();
        // 第一阶段：小幅滚动 4 次（近处评论）
        var found = false;
        for (var si = 0; si < 6; si++) {
          var sd = Math.floor(Math.random() * 200 + 400);
          gestures([0, sd, [rvcx, rvb.top + rvb.height() * 0.20],
                           [rvcx + Math.floor(Math.random() * 20 + 10), rvb.top + rvb.height() * 0.75]]);
          sleep(400);
          try { if (text(nickname).findOne(300)) { found = true; break; } } catch (e) {}
          if (!uiOperator.findElement("is_comment_view", 300)) break;
        }
        // 第二阶段：大幅翻页滚动 8 次（评论极多时目标在深处）
        if (!found) {
          for (var si2 = 0; si2 < 8; si2++) {
            var sd2 = Math.floor(Math.random() * 300 + 600);
            gestures([0, sd2, [rvcx, rvb.top + rvb.height() * 0.60],
                             [rvcx + Math.floor(Math.random() * 20 + 10), rvb.top + rvb.height() * 0.20]]);
            sleep(400);
            try { if (text(nickname).findOne(300)) break; } catch (e) {}
            if (!uiOperator.findElement("is_comment_view", 300)) break;
          }
        }
      } catch (e) {}
    } else {
      // 兜底：找不到 comment_list，全屏滚动
      var sc = device.width / 2;
      var found2 = false;
      for (var sj = 0; sj < 4; sj++) {
        var sd3 = Math.floor(Math.random() * 200 + 400);
        gestures([0, sd3, [sc, device.height * 0.45],
                         [sc + Math.floor(Math.random() * 20 + 10), device.height * 0.70]]);
        sleep(400);
        try { if (text(nickname).findOne(300)) { found2 = true; break; } } catch (e) {}
        if (!uiOperator.findElement("is_comment_view", 300)) break;
      }
      if (!found2) {
        for (var sj2 = 0; sj2 < 6; sj2++) {
          var sd4 = Math.floor(Math.random() * 300 + 600);
          gestures([0, sd4, [sc, device.height * 0.60],
                           [sc + Math.floor(Math.random() * 20 + 10), device.height * 0.20]]);
          sleep(400);
          try { if (text(nickname).findOne(300)) break; } catch (e) {}
          if (!uiOperator.findElement("is_comment_view", 300)) break;
        }
      }
    }
  }

  // 进入目标用户主页。
  // 不依赖传入的 commentAuthorAvatarEl —— 评论列表滚动后元素引用会失效。
  // 前面的滚动逻辑已将目标昵称拉回可见区域，直接按昵称文本点击最可靠。
  try {
    var nameEl = text(nickname).findOne(3000);
    if (nameEl) {
      try { nameEl.click(); } catch (e) { nameEl.parent().click(); }
      if (uiOperator.waitForPage("is_user_view", 5000)) {
        flowContext.enter("profile");
        return true;
      }
      logger.warn(TAG, "点击昵称后未检测到主页，尝试点头像");
    }
  } catch (e) {
    logger.warn(TAG, "点击昵称失败: " + e.message);
  }

  // 回退：safeClick 按头像 selector 搜索
  var avatarClicked = this.safeClick("comment_author_avatar", 2);
  if (avatarClicked) {
    if (uiOperator.waitForPage("is_user_view", 5000)) {
      flowContext.enter("profile");
      return true;
    }
    logger.warn(TAG, "点击头像后未检测到主页");
  }
  return false;
};

/**
 * 关注用户 — 拟人化操作，避免被检测
 * 进入主页后：浏览一下 → 随机延迟 → 点关注 → 验证
 */
ReplyCommentHandler._followUser = function () {
  try {
    // 1. 随机停留，给主页加载时间
    sleep(Math.floor(Math.random() * 1000 + 1000));
    // 30% 概率拟人浏览主页（轻滑一下看作品，用 gestures 不会误触发点击）
    if (Math.random() < 0.3) {
      var bwx = device.width * (0.35 + Math.random() * 0.2);
      var bwy1 = device.height * (0.45 + Math.random() * 0.05);
      var bwy2 = device.height * (0.25 + Math.random() * 0.1);
      var bwd = Math.floor(Math.random() * 200 + 300);
      gestures([0, bwd, [bwx, bwy1], [bwx + Math.floor(Math.random() * 20 + 10), bwy2]]);
      sleep(Math.floor(Math.random() * 800 + 600));
    }

    // 2. 确保回到主页顶部（关注/私信按钮在顶部）
    var backToTop = false;
    for (var si = 0; si < 4; si++) {
      if (uiOperator.findElement("user_nickname", 1000)) {
        backToTop = true;
        break;
      }
      var btx = device.width / 2;
      var btd = Math.floor(Math.random() * 200 + 400);
      gestures([0, btd, [btx, device.height * (Math.random() * 0.1 + 0.20)],
                       [btx + Math.floor(Math.random() * 20 + 10), device.height * (Math.random() * 0.1 + 0.75)]]);
      sleep(Math.floor(Math.random() * 200 + 300));
    }
    if (!backToTop) {
      logger.warn(TAG, "下拉回顶未检测到 user_nickname，可能影响关注/私信按钮可见性");
    }
    sleep(Math.floor(Math.random() * 400 + 400));

    // 3. 找关注按钮 — 用随机按压时长模拟真人（80~180ms）
    var followed = false;
    var followBtn = uiOperator.findElement("follow_button", 3000);
    if (followBtn) {
      // 图找图/坐标返回的是虚拟元素，控件返回的是 UiObject，统一取坐标
      var fbx, fby;
      if (followBtn.isImage || followBtn.isCoordinate) {
        fbx = followBtn.x; fby = followBtn.y;
      } else {
        try { var fb = followBtn.bounds(); if (fb) { fbx = fb.centerX(); fby = fb.centerY(); } } catch (e) {}
      }
      if (!fbx) { fbx = device.width / 2; fby = device.height * 0.3; }

      // 随机延迟后点击（真人不会一到主页就秒点关注）
      sleep(Math.floor(Math.random() * 1500 + 500));
      press(fbx, fby, Math.floor(Math.random() * 100 + 80));
      sleep(Math.floor(Math.random() * 1000 + 1000));

      // 验证：图找图检测关注成功
      if (uiOperator.findElement("is_follow", 2000)) {
        followed = true;
      }

      // 可能被风控，换随机时长重试
      // 重试前先检查 follow_button 是否仍可见——第一次 press 可能已生效
      // 只是 is_follow 选择器匹配慢。按钮变"已关注"后 follow_button 模板不再匹配
      if (!followed) {
        sleep(Math.floor(Math.random() * 600 + 400));
        var retryBtn = uiOperator.findElement("follow_button", 2000);
        if (!retryBtn) {
          followed = true;
        } else {
          press(fbx, fby, Math.floor(Math.random() * 100 + 80));
          sleep(Math.floor(Math.random() * 1000 + 1000));
          if (uiOperator.findElement("is_follow", 2000)) followed = true;
        }
      }
    }

    if (followed) {
      logger.info(TAG, "关注成功");
    } else {
      logger.warn(TAG, "关注按钮未找到（可能已关注）");
    }
    return followed;
  } catch (e) {
    logger.warn(TAG, "关注流程异常: " + (e.message || e));
    return false;
  }
};

/**
 * 采集用户主页数据 — 抖音号/获赞/粉丝/作品/性别/年龄/IP/是否私密
 * 调用时机：已在个人主页时采集，不 back（调用方负责返回评论区）
 */
ReplyCommentHandler._collectProfileData = function () {
  return commentUtils.collectProfileData({ uploadAvatar: false });
};

/**
 * 发送私信
 * @param {string} content - 私信内容
 */
ReplyCommentHandler._sendDM = function (content) {
  // 1. 进入私信页：点 dm_entry_btn
  var messageClicked = this.safeClick("dm_entry_btn", 5);
  if (!messageClicked) {
    logger.warn(TAG, "私信按钮未找到");
    return false;
  }
  // 显式等待聊天室加载完成（dm_input 出现 = 页面就绪）
  if (!uiOperator.waitForElement("dm_input", 5000)) {
    logger.warn(TAG, "私信聊天室加载超时");
    back(); sleep(500);
    return false;
  }
  flowContext.enter("dm");

  // 2. 点击 dm_input 触发键盘，输入框自动获得焦点
  if (!this.safeClick("dm_input", 2)) {
    logger.warn(TAG, "dm_input 未找到");
    return false;
  }
  // 显式等待输入框获得焦点
  if (!uiOperator.waitForElement("dm_input", 3000)) {
    logger.warn(TAG, "dm_input 键盘唤起超时");
    return false;
  }

  // 3. 清空+拟人输入
  var pasted = false;
  try {
    // 用无障碍直接清空输入框（不依赖焦点，不要 shell 键）
    var dmEdit = className("EditText").focused(true).findOne(1000);
    if (dmEdit) {
      dmEdit.setText("");
      sleep(300);
      logger.info(TAG, "DM 输入框已清空");
    } else {
      logger.warn(TAG, "DM 输入框未找到");
    }
    // 拟人：随机敲1字符 → 删除 → 逐块输入AI内容
    pasted = humanInput.typeFocusedText(content, { requireVerification: true });
    if (!pasted) {
    // 用无障碍删除随机字符（比 shell 可靠）
      logger.warn(TAG, "DM input verification failed, cancel send to avoid dirty data");
      back(); sleep(500);
      return false;
    }
    logger.info(TAG, "私信 input 输入成功: '" + content.substring(0, 20) + "'");
  } catch (e) {
    logger.warn(TAG, "私信 input 异常: " + e.message);
  }

  // 4. 兜底：剪贴板粘贴
  if (!pasted) {
    logger.warn(TAG, "私信输入失败");
    back(); sleep(500);
    return false;
  }

  // 5. 等几十毫秒让输入生效，然后点击发送
  sleep(Math.floor(Math.random() * 150 + 100));
  var sent = uiOperator.findElement("dm_send", 3000);
  if (sent) {
    uiOperator.clickElement(sent);
    sleep(800);
  } else {
    logger.warn(TAG, "私信发送按钮未找到，取消发送");
    return false;
  }

  logger.info(TAG, "私信已发送: '" + content.substring(0, 20) + "'");
  return true;
};

ReplyCommentHandler._returnToComments = function () {
  var maxBacks = 5;
  for (var i = 0; i < maxBacks; i++) {
    // 已在评论面板 → 完成
    if (uiOperator.isOnPage("is_comment_view")) {
      logger.info(TAG, "回到评论区 (back " + i + " 次)");
      flowContext.enter("comment");
      return;
    }

    // 在个人主页 → back
    if (uiOperator.isOnPage("is_user_view")) {
      logger.info(TAG, "在个人主页，back 到评论区");
      back(); sleep(800);
      continue;
    }

    // 在私信页 → back
    if (uiOperator.isOnPage("is_dm_view")) {
      logger.info(TAG, "在私信页，back 到个人主页");
      back(); sleep(800);
      continue;
    }

    // 已确认是视频详情页 → 判断上下文
    if (uiOperator.isOnPage("is_video_view")) {
      if (flowContext.is("profile")) {
        // 从个人主页误触进来的 → back
        logger.info(TAG, "检测到误触（profile→video），back");
        back(); sleep(500);
        flowContext.enter("profile");
        continue;
      }
      // 搜索流中的视频 → 打开评论区
      logger.info(TAG, "在视频页，打开评论区 (back " + i + " 次)");
      this._openComments();
      return;
    }

    // 未知页面，back 重试
    logger.info(TAG, "第 " + (i + 1) + " 次 back，未知页面");
    back();
    sleep(1000);
  }

  logger.warn(TAG, "无法回到评论区，兜底打开");
  this._openComments();
};

module.exports = ReplyCommentHandler;
