// device/handlers/reply-comment.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var uiOperator = require("../core/ui-operator");
var selectorLoader = require("../core/selector-loader");
var antiDetect = require("../core/anti-detect");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");

var TAG = "评论回复";

// 页面指纹表 — 每个页面至少一个指纹命中即确认
// 指纹选择原则：只放该页面独有的、稳定存在的元素
// 顺序很重要：先检查具体页面，最后检查宽泛的 home
// home 的 search_tab 在视频页/搜索页也可能可见，必须放最后
var PAGE_DETECTORS = {
  comment:  ["is_comment_view"],                                         // 评论面板（最具体）
  dm:       ["dm_input", "dm_send"],                                     // 私信页
  profile:  ["user_nickname"],                                           // 个人主页
  video:    ["is_video_view"],                                           // 视频详情页
  search:   ["search_video_list", "search_video_tab"],                   // 搜索结果页
  home:     ["search_tab"],                                              // 抖音首页（最后兜底）
};

/**
 * 检测当前处于哪个已知页面，返回页面名，未知返回 null
 */
function detectCurrentPage() {
  for (var pageName in PAGE_DETECTORS) {
    var fingerprints = PAGE_DETECTORS[pageName];
    for (var i = 0; i < fingerprints.length; i++) {
      if (uiOperator.findElement(fingerprints[i], 800)) {
        return pageName;
      }
    }
  }
  return null;
}

/**
 * 从当前未知页面逐层 back 回到已知页面
 * 每 back 一次检测指纹，直到命中目标页或耗尽
 * @param {string} targetPage - 目标页面名
 * @param {number} maxBacks - 最大 back 次数
 * @returns {boolean} 是否到达目标页面
 */
function recoverToPage(targetPage, maxBacks) {
  maxBacks = maxBacks || 5;
  for (var i = 0; i < maxBacks; i++) {
    var current = detectCurrentPage();
    if (current === targetPage) {
      if (i > 0) logger.info(TAG, "已恢复到 " + targetPage + " (back " + i + " 次)");
      return true;
    }
    if (current && current !== targetPage) {
      // 在别的已知页面但不是目标，继续 back
      logger.debug(TAG, "当前在 " + current + "，继续 back 前往 " + targetPage);
    }
    back();
    sleep(800);
  }
  // 耗尽 back，检查是否至少到了目标
  return detectCurrentPage() === targetPage;
}

/**
 * 确保当前在指定页面，不在则自动恢复
 * @param {string} page - 页面名
 * @param {Function} recoverFn - 首选恢复函数，返回 true 表示恢复成功
 * @param {number} maxRetries - 最大重试次数
 * @returns {boolean} 是否已在目标页面
 */
function ensurePage(page, recoverFn, maxRetries) {
  maxRetries = maxRetries || 3;
  var detectors = PAGE_DETECTORS[page] || [];

  for (var attempt = 0; attempt < maxRetries; attempt++) {
    // 检测是否已在目标页
    for (var d = 0; d < detectors.length; d++) {
      if (uiOperator.findElement(detectors[d], 1000)) {
        if (attempt > 0) logger.info(TAG, "页面恢复: " + page + " (尝试 " + attempt + ")");
        return true;
      }
    }

    // 不在目标页 — 先判断当前实际在哪
    var actualPage = detectCurrentPage();
    if (actualPage) {
      logger.info(TAG, "当前在 " + actualPage + "，需要 " + page + "，尝试恢复 (" + (attempt + 1) + "/" + maxRetries + ")");
    } else {
      logger.warn(TAG, "未知页面，需要 " + page + "，尝试 back 链恢复 (" + (attempt + 1) + "/" + maxRetries + ")");
    }

    // 已知页面 + 有自定义恢复 → 用自定义恢复
    if (actualPage && recoverFn && attempt < maxRetries - 1) {
      recoverFn();
      continue;
    }

    // 没有自定义恢复函数 → 只验证，不做破坏性 back 链（back 链会摧毁页面状态）
    if (!recoverFn) {
      return false;
    }

    // 有自定义恢复但不可用 → 尝试 back 链兜底
    if (recoverToPage(page, 3)) {
      return true;
    }
  }

  // 有自定义恢复但次数耗尽 → back 链最后一搏
  if (recoverFn && recoverToPage(page, 5)) {
    return true;
  }

  logger.warn(TAG, "无法恢复到 " + page + " 页面");
  return false;
}

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
  var count = params.count || 5;
  var videoCount = params.video_count || 3;
  var sortBy = params.sort_by || "latest";
  var maxAgeDays = params.max_age_days || 5;
  // 每日上限（从服务端下发或设备配置获取）
  var maxFollows = params.max_follows || 20;
  var maxDMs = params.max_dms || 10;

  // 加载服务端提示词模板
  aiAnalyzer.useTemplate(params.prompt_template_id);

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "开始: 关键词='" + keyword + "', 视频数=" + videoCount +
    ", 每视频评论=" + count + ", 排序=" + sortBy + ", 最大天数=" + maxAgeDays + "天");

  var taskId = params.task_id || "";
  function _reportProgress(step, detail, prog) {
    if (taskId) { try { apiClient.reportProgress(taskId, step, detail, prog); } catch (e) {} }
  }

  if (!this.ensureAppActive()) {
    return { success: false, error: "打开抖音失败" };
  }

  // 1. 搜索 → 排序 → 关闭弹出框（不打开视频）
  if (!this._searchAndSort(keyword, sortBy)) {
    return { success: false, error: "搜索排序失败" };
  }

  var stats = { videos_processed: 0, success_count: 0, fail_count: 0, skipped: 0,
    follow_count: 0, dm_count: 0, details: [] };

  // 2. 逐个视频处理
  // 第一个视频从搜索结果点击进入
  if (!this._clickSearchResult(0)) {
    return { success: false, error: "点击第一个视频失败" };
  }
  sleep(2000);

  for (var v = 0; v < videoCount; v++) {
    var videoStartTime = Date.now();
    var VIDEO_TIMEOUT = 120000;  // 单视频超时 2 分钟，防止卡死
    logger.info(TAG, "=== 视频 " + (v + 1) + "/" + videoCount + " ===");
    _reportProgress("视频 " + (v + 1) + "/" + videoCount, "关键词: " + keyword, (v / videoCount));

    // 验证在视频详情页 + 预判评论数
    var commentCount = 0;
    var commentBtn = null;
    for (var wait = 0; wait < 5; wait++) {
      if (Date.now() - videoStartTime > VIDEO_TIMEOUT) {
        logger.warn(TAG, "视频 " + (v + 1) + " 等待进入视频页超时，跳过"); break;
      }
      commentBtn = uiOperator.findElement("video_comment_btn", 2000);
      if (commentBtn) break;
      logger.info(TAG, "等待进入视频页 (" + (wait + 1) + "/5)");
    }
    if (!commentBtn) {
      logger.warn(TAG, "未进入视频详情页，跳过");
      continue;
    }
    try {
      if (!commentBtn.isImage && !commentBtn.isCoordinate) {
        var numMatch = (commentBtn.desc() || "").match(/(\d+)/);
        if (numMatch) commentCount = parseInt(numMatch[1]);
      }
    } catch (e) { /* ignore */ }
    logger.info(TAG, "视频 " + (v + 1) + " 评论数: " + (commentCount || "未知"));

    if (commentCount === 0) {
      logger.info(TAG, "该视频无评论，跳过");
      stats.videos_processed++;
      if (v < videoCount - 1) { uiOperator.swipeUp(); sleep(2500); }
      continue;
    }

    // 2c. 打开评论区（带重试）
    var commentsOpened = false;
    for (var retry = 0; retry < 2; retry++) {
      if (Date.now() - videoStartTime > VIDEO_TIMEOUT) break;
      // 点击评论入口
      this.safeClick("video_comment_btn", 2);
      sleep(2000);
      // 验证是否真正打开
      if (ensurePage("comment", null, 1)) {
        commentsOpened = true;
        break;
      }
      logger.info(TAG, "评论区未打开，重试 (" + (retry + 1) + "/2)");
    }
    if (!commentsOpened) {
      logger.warn(TAG, "评论区打开失败，跳过此视频");
      continue;
    }

    // 2d. 逐批读取+处理评论（不限批次，直到读完所有或达成目标）
    var processed = 0;
    var totalRead = 0;
    var prevItemCount = 0;
    var emptyStreak = 0;  // 连续空列表计数器，防止死循环

    var items = uiOperator.findElements("comment_list", 3000);

    while (processed < count && (commentCount === 0 || totalRead < commentCount)) {
      // 连续空列表保护：2 次迭代 items 都为空则到底
      if (items.length === 0) {
        emptyStreak++;
        if (emptyStreak >= 2) {
          logger.info(TAG, "评论列表连续为空，已到底");
          break;
        }
      } else {
        emptyStreak = 0;
      }
      // 视频级超时保护：单视频处理超过 2 分钟强制切下一个
      if (Date.now() - videoStartTime > VIDEO_TIMEOUT) {
        logger.warn(TAG, "视频 " + (v + 1) + " 处理超时 (" +
          Math.round((Date.now() - videoStartTime) / 1000) + "s)，强制跳过");
        break;
      }
      // 检查是否已到底：可见条目不再增长且已全部读取
      // （无论 commentCount 是否已知，RecyclerView 不加载新条目就到底了）
      if (items.length <= prevItemCount && totalRead >= items.length && prevItemCount > 0) {
        logger.info(TAG, "评论已到底（可见" + items.length + "条/已读" + totalRead + "条），停止");
        break;
      }
      prevItemCount = items.length;

      // 处理本批新评论（每条独立 try-catch，失败不级联）
      for (var i = totalRead; i < items.length && processed < count; i++) {
        if (Date.now() - videoStartTime > VIDEO_TIMEOUT) {
          logger.warn(TAG, "评论处理超时，跳出内循环");
          break;
        }
        try {
        var comment = this._parseCommentItem(items[i]);
        if (!comment) { stats.skipped++; totalRead++; continue; }

        // 跳过假评论（占位符/空昵称/空文本）
        if (comment.nickname === "unknown" || !comment.text ||
            comment.text.indexOf("发条评论") !== -1) {
          stats.skipped++; totalRead++; continue;
        }

        // 跳过作者自己的评论
        if (comment.isAuthor) {
          logger.info(TAG, "跳过作者评论: " + comment.nickname);
          stats.skipped++; totalRead++; continue;
        }

        // 时效筛选
        if (!this._filterByTime([comment], maxAgeDays).length) {
          stats.skipped++; totalRead++; continue;
        }

        // 本地预过滤：纯表情/无意义评论先拦掉，避免无价值的 claim 和 AI 调用
        var stripped = comment.text
          .replace(/\[[^\]]+\]/g, "")
          .replace(/[\s~!@#$%^&*()_+\-={}|:;<>?,./'""'""、。！，《》]+/g, "")
          .replace(/[^一-龥a-zA-Z0-9]/g, "")
          .trim();
        if (!stripped || stripped.length <= 2) {
          logger.info(TAG, "跳过无意义评论（纯表情/短文本）: " + comment.text.substring(0, 20));
          stats.skipped++; totalRead++;
          _reportProgress("视频 " + (v + 1) + "/" + videoCount,
            "已跳过 " + stats.skipped + " 条（无意义）",
            (v + totalRead / Math.max(commentCount, 1)) / videoCount);
          continue;
        }

        // 全局去重：原子检查+标记（预过滤之后才调 API，避免浪费 claim）
        var canReply = true;
        try {
          var claimResult = apiClient.claimCommentReply(comment.nickname, comment.text);
          canReply = claimResult && claimResult.claimed;
        } catch (e) { /* 网络异常默认放行 */ }
        if (!canReply) {
          logger.info(TAG, "评论已被回复过（全局去重）: " + comment.nickname);
          stats.skipped++; totalRead++;
          _reportProgress("视频 " + (v + 1) + "/" + videoCount,
            "已跳过 " + stats.skipped + " 条（去重）",
            (v + totalRead / Math.max(commentCount, 1)) / videoCount);
          continue;
        }

        logger.info(TAG, "分析 " + (processed + 1) + "/" + count +
          ": [" + comment.nickname + "] " + comment.text.substring(0, 30));

        var analysis = aiAnalyzer.analyzeComment({
          searchKeyword: keyword,
          nickname: comment.nickname,
          commentText: comment.text,
        });

        if (!analysis) {
          stats.skipped++; totalRead++;
          _reportProgress("视频 " + (v + 1) + "/" + videoCount,
            "已跳过 " + stats.skipped + " 条（分析失败）",
            (v + totalRead / Math.max(commentCount, 1)) / videoCount);
          continue;
        }

        logger.info(TAG, "分数=" + analysis.score + ", 层级=" + analysis.tier +
          ", 意图=" + (analysis.dimensions ? analysis.dimensions.intent : "未知"));

        if (analysis.score < aiAnalyzer.SCORE_THRESHOLD) {
          logger.info(TAG, "分数 " + analysis.score + " 低于阈值，跳过");
          stats.skipped++; totalRead++;
          _reportProgress("视频 " + (v + 1) + "/" + videoCount,
            "已跳过 " + stats.skipped + " 条（" + analysis.score + "分）",
            (v + totalRead / Math.max(commentCount, 1)) / videoCount);
          continue;
        }

        if (analysis.dimensions && analysis.dimensions.lead_quality) {
          var lq = analysis.dimensions.lead_quality;
          if (lq.is_bot || lq.is_competitor) {
            logger.info(TAG, "检测到水军/同行，跳过");
            stats.skipped++; totalRead++;
            _reportProgress("视频 " + (v + 1) + "/" + videoCount,
              "已跳过 " + stats.skipped + " 条（水军/同行）",
              (v + totalRead / Math.max(commentCount, 1)) / videoCount);
            continue;
          }
        }

        // 回复
        logger.info(TAG, "回复: '" + analysis.reply.substring(0, 30) + "...'");
        // 点击回复按钮，预先唤起输入框（部分评论项可能没有回复按钮，需兼容）
        if (comment.replyBtn) {
          logger.info(TAG, "点击回复按钮...");
          comment.replyBtn.click();
          sleep(1000);
        } else {
          logger.info(TAG, "无回复按钮，直接输入");
        }
        logger.info(TAG, "开始输入回复...");
        if (this._replyToComment(analysis.reply, comment.nickname)) {
          stats.success_count++;
          // 保存 AI 回复到采集记录，供前端展示
          try { apiClient.saveCommentAIReply(comment.nickname, comment.text, analysis.reply, params.task_id); } catch (e) {}
        } else {
          stats.fail_count++;
          // 回复失败 → 释放 global claim，避免误标记为"已回复"
          try { apiClient.releaseCommentReply(comment.nickname, comment.text); } catch (e) {}
          totalRead++;
          continue;
        }

        stats.details.push({
          video: v + 1, nickname: comment.nickname,
          comment: comment.text,
          score: analysis.score, tier: analysis.tier,
          intent: analysis.dimensions ? analysis.dimensions.intent : "unknown",
          reply: analysis.reply,
        });

        // 关注+私信（AI 语义分析决定动作）
        // high → 关注+私信 | medium → 仅关注 | low → 只回复
        sleep(Math.floor(Math.random() * 500 + 800));
        var shouldFollow = analysis.tier === "high" || analysis.tier === "medium";
        var shouldDM = analysis.tier === "high";
        var canFollow = shouldFollow && stats.follow_count < maxFollows;
        var canDM = shouldDM && stats.dm_count < maxDMs;
        if (canFollow || canDM) {
          if (this._enterCommenterProfile(comment.commentAuthorAvatarEl, comment.nickname)) {
            // 个人主页操作超时保护（30s），防止卡死在异常页面
            var profileStart = Date.now();
            var PROFILE_TIMEOUT = 30000;

            // 进主页先判断是否私密账号 — 是则跳过后续所有操作
            var isPrivate = !!uiOperator.findElement("user_is_private", 2000);
            if (isPrivate) {
              logger.info(TAG, "私密账号，跳过关注和私信");
            } else {
              // 采集用户主页数据
              var userData = this._collectProfileData();
              if (userData) {
                var lastDetail = stats.details[stats.details.length - 1];
                if (lastDetail) lastDetail.user = userData;
                userData._keyword = keyword;
                userData._taskId = taskId;
                try { apiClient.saveUserProfile(userData); } catch (e) {}
              }
              if (Date.now() - profileStart < PROFILE_TIMEOUT && canFollow && this._followUser()) {
                stats.follow_count++;
              }
              sleep(Math.floor(Math.random() * 500 + 800));

              if (Date.now() - profileStart < PROFILE_TIMEOUT && canDM) {
                // 优先 AI 生成私信内容，失败兜底用 params.content
                var dmContent = "";
                var dmIntent = "other";
                try {
                  dmIntent = (analysis.dimensions && analysis.dimensions.intent) || "other";
                  var aiDM = aiAnalyzer.generateDM({
                    searchKeyword: keyword, nickname: comment.nickname,
                    commentText: comment.text, tier: dmIntent,
                  });
                  if (aiDM) dmContent = aiDM;
                } catch (e) { /* ignore */ }
                if (!dmContent && content) dmContent = content;
                if (dmContent) {
                  var recipientId = (userData && userData.douyin_id) || "";
                  if (recipientId) {
                    // 全局去重：服务端原子 claim
                    var claimResult = apiClient.claimDMRecipient({
                      account_id: params.account_id,
                      recipient_douyin_id: recipientId,
                      recipient_nickname: comment.nickname,
                    });
                    if (claimResult && claimResult.claimed) {
                      var sent = this._sendDM(dmContent);
                      if (sent) {
                        apiClient.reportDMSend({
                          conversation_id: claimResult.conversation_id,
                          stage: dmIntent,
                          intent: dmIntent,
                          keyword: keyword,
                          content: dmContent,
                        });
                        stats.dm_count++;
                      } else {
                        apiClient.releaseDMRecipient({
                          conversation_id: claimResult.conversation_id,
                        });
                      }
                    } else {
                      logger.info(TAG, "用户 " + comment.nickname + " 已被其他设备 DM，跳过");
                    }
                  } else {
                    // 无抖音 ID，用昵称 djb2 hash 生成 fallback 标识，保持去重机制
                    var fbNick = comment.nickname || "unknown";
                    var fbHash = 0;
                    for (var hi = 0; hi < fbNick.length; hi++) {
                      fbHash = ((fbHash << 5) - fbHash) + fbNick.charCodeAt(hi); fbHash |= 0;
                    }
                    var fallbackId = "fb_" + Math.abs(fbHash).toString(16);
                    claimResult = apiClient.claimDMRecipient({
                      account_id: params.account_id,
                      recipient_douyin_id: fallbackId,
                      recipient_nickname: comment.nickname,
                    });
                    if (claimResult && claimResult.claimed) {
                      var sent2 = this._sendDM(dmContent);
                      if (sent2) {
                        apiClient.reportDMSend({
                          conversation_id: claimResult.conversation_id,
                          stage: dmIntent, intent: dmIntent, keyword: keyword, content: dmContent,
                        });
                        stats.dm_count++;
                      } else {
                        apiClient.releaseDMRecipient({ conversation_id: claimResult.conversation_id });
                      }
                    }
                  }
                }
                sleep(Math.floor(Math.random() * 500 + 800));
              }
            }

            if (Date.now() - profileStart > PROFILE_TIMEOUT) {
              logger.warn(TAG, "主页操作超时 (" + Math.round((Date.now() - profileStart) / 1000) + "s)，强制返回");
            }

            // 确保回到评论区
            this._returnToComments();
            // 二次确认，不在评论区就重试
            if (!ensurePage("comment", function () {
              back(); sleep(800);
              this._openComments();
              sleep(1500);
            }.bind(this), 2)) {
              logger.warn(TAG, "返回评论区失败，跳过后续评论");
              processed = count;  // 终止 while 循环
              break;
            }
            // 刷新评论列表（位置已变，旧 items 已失效）
            uiOperator.swipeUp();
            sleep(800);
            items = uiOperator.findElements("comment_list", 3000);
            prevItemCount = items.length;  // 用刷新后的实际条目数，避免多一次无效循环
            videoStartTime = Date.now();   // 重置超时计时，profile 操作时间不计入评论处理
          } else {
            logger.warn(TAG, "进入主页失败，跳过关注+私信");
            this._dismissKeyboard();
          }
        }
        sleep(1000);

        processed++;
        totalRead++;
        _reportProgress("视频 " + (v + 1) + "/" + videoCount,
          "已回复 " + stats.success_count + " 条，跳过 " + stats.skipped + " 条",
          (v + processed / count) / videoCount);
        antiDetect.maybePause();
        } catch (e) {
          logger.error(TAG, "处理评论异常: " + e.message + "，跳过继续");
          stats.skipped++; totalRead++;
          // 恢复到评论面板
          try { this._returnToComments(); } catch (e2) { /* ignore */ }
        }
      }

      // 还需更多评论，滑动加载
      if (processed < count && (commentCount === 0 || totalRead < commentCount)) {
        uiOperator.swipeUp();
        sleep(1500);
        items = uiOperator.findElements("comment_list", 3000);
      }
    }

    stats.videos_processed++;
    antiDetect.maybePause();

    // 当前视频处理完，切到下一个（最后一个不用切）
    if (v < videoCount - 1) {
      // 1. comment_off_btn 关闭评论面板
      this.safeClick("comment_off_btn", 2);
      sleep(600);
      // 2. 确认关闭，否则 back 兜底
      if (uiOperator.findElement("is_comment_view", 300)) {
        back(); sleep(600);
      }
      // 3. 上滑切下一个视频
      uiOperator.swipeUp();
      sleep(2500);
    }
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
 * 打开评论区 — 点击视频评论入口按钮
 */
ReplyCommentHandler._openComments = function () {
  // 检测评论区是否真正打开（comment_list 可见才算）执行进度
  var items = uiOperator.findElements("comment_list", 500);
  if (items && items.length > 0) {
    logger.info(TAG, "评论区已打开 (" + items.length + " 条可见)");
    return true;
  }

  // 点视频评论按钮
  this.safeClick("video_comment_btn", 3);
  sleep(2000);

  // 验证：评论列表是否加载
  items = uiOperator.findElements("comment_list", 3000);
  if (items && items.length > 0) {
    logger.info(TAG, "评论区已打开 (" + items.length + " 条)");
    return true;
  }

  // 重试：备用方式
  this.safeClick("comment_input", 2);
  sleep(2000);
  items = uiOperator.findElements("comment_list", 3000);
  if (items && items.length > 0) return true;

  logger.warn(TAG, "评论区未能打开");
  return false;
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
  try {
    var uiOperator = require("../core/ui-operator");

    // 使用选择器系统提取昵称
    var nicknameEl = this._findChildBySelector(item, "comment_author");
    var nickname = nicknameEl ? this._extractChildValue(nicknameEl, "comment_author", "unknown") : null;
    if (!nickname) {
      nicknameEl = item.findOne(clickable(true).className("android.widget.TextView"));
      nickname = nicknameEl ? this._extractChildValue(nicknameEl, "comment_author", "unknown") : "unknown";
    }

    // 使用选择器系统提取评论文本
    var textEl = this._findChildBySelector(item, "comment_text");
    var text = textEl ? this._extractChildValue(textEl, "comment_text", "") : "";
    if (!text) {
      var textViews = item.find(className("android.widget.TextView"));
      var maxLen = 0;
      for (var i = 0; i < textViews.length; i++) {
        var t = textViews[i].text() || "";
        if (t.length > maxLen && t !== nickname) {
          maxLen = t.length;
          textEl = textViews[i];
        }
      }
      text = textEl ? this._extractChildValue(textEl, "comment_text", "") : "";
    }
    if (!text) return null;

    // 使用选择器系统提取时间
    var timeEl = this._findChildBySelector(item, "comment_time");
    var timeStr = timeEl ? this._extractChildValue(timeEl, "comment_time", "") : "";

    // 检测是否为作者自己的评论 — 优先用选择器，兜底硬编码
    var isAuthor = false;
    try {
      var authorEl = this._findChildBySelector(item, "comment_is_author");
      if (!authorEl) authorEl = item.findOne(text("作者"));
      if (authorEl) isAuthor = true;
    } catch (e) { /* ignore */ }

    return {
      nickname: nickname,
      text: text,
      time: timeStr,
      element: item,
      isAuthor: isAuthor,
      replyBtn: this._findChildBySelector(item, "comment_reply_button"),
      commentAuthorAvatarEl: this._findChildBySelector(item, "comment_author_avatar"),  
    };
  } catch (e) {
    logger.warn(TAG, "解析评论项出错: " + e.message);
    return null;
  }
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

  // "昨天 HH:MM"
  if (timeStr.indexOf("昨天") !== -1) {
    var yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    var hmMatch = timeStr.match(/(\d{1,2}):(\d{2})/);
    if (hmMatch) {
      yesterday.setHours(parseInt(hmMatch[1]), parseInt(hmMatch[2]), 0, 0);
    }
    return yesterday;
  }

  // "前天 HH:MM"
  if (timeStr.indexOf("前天") !== -1) {
    var dayBefore = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 2);
    var hm2 = timeStr.match(/(\d{1,2}):(\d{2})/);
    if (hm2) {
      dayBefore.setHours(parseInt(hm2[1]), parseInt(hm2[2]), 0, 0);
    }
    return dayBefore;
  }

  // "X天前"
  var dayMatch = timeStr.match(/(\d+)\s*天前/);
  if (dayMatch) {
    return new Date(now.getTime() - parseInt(dayMatch[1]) * 24 * 60 * 60 * 1000);
  }

  // "X周前"
  var weekMatch = timeStr.match(/(\d+)\s*周前/);
  if (weekMatch) {
    return new Date(now.getTime() - parseInt(weekMatch[1]) * 7 * 24 * 60 * 60 * 1000);
  }

  // "MM-DD" (当年)
  var mdMatch = timeStr.match(/^(\d{1,2})-(\d{1,2})$/);
  if (mdMatch) {
    return new Date(now.getFullYear(), parseInt(mdMatch[1]) - 1, parseInt(mdMatch[2]));
  }

  // "MM-DD HH:MM" (当年，带时间)
  var mdtMatch = timeStr.match(/^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
  if (mdtMatch) {
    return new Date(now.getFullYear(), parseInt(mdtMatch[1]) - 1, parseInt(mdtMatch[2]),
                    parseInt(mdtMatch[3]), parseInt(mdtMatch[4]), 0);
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
    var focusedNode = className("EditText").focused(true).findOne(500);
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
    logger.info(TAG, "input 输入成功: '" + cleanText.substring(0, 20) + "'");
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
    logger.info(TAG, "回复已发送(图找图): '" + replyText.substring(0, 20) + "'");
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
    logger.info(TAG, "头像不可见，评论列表内轻量下拉拉回");
    var rv = uiOperator.findElement("comment_list", 1000);
    // 在列表中间区域小幅下拉，避开顶部（顶部下拉=关闭评论区）
    if (rv && !rv.isImage && !rv.isCoordinate) {
      try {
        var rvb = rv.bounds();
        var rvcx = rvb.centerX();
        for (var si = 0; si < 4; si++) {
          var sd = Math.floor(Math.random() * 200 + 400);
          gestures([0, sd, [rvcx, rvb.top + rvb.height() * 0.40],
                           [rvcx + Math.floor(Math.random() * 20 + 10), rvb.top + rvb.height() * 0.70]]);
          sleep(400);
          // 昵称出现了就停
          try { if (text(nickname).findOne(300)) break; } catch (e) {}
          if (!uiOperator.findElement("is_comment_view", 300)) break;
        }
      } catch (e) {}
    } else {
      // 兜底：找不到 comment_list，全屏中部小幅下拉
      for (var sj = 0; sj < 2; sj++) {
        var sc = device.width / 2;
        var sd2 = Math.floor(Math.random() * 200 + 400);
        gestures([0, sd2, [sc, device.height * 0.45],
                         [sc + Math.floor(Math.random() * 20 + 10), device.height * 0.70]]);
        sleep(400);
        try { if (text(nickname).findOne(300)) break; } catch (e) {}
        if (!uiOperator.findElement("is_comment_view", 300)) break;
      }
    }
  }

  // 点击头像进入主页
  var avatarClicked = this.safeClick("comment_author_avatar", 2);
  if (avatarClicked) {
    sleep(2000);
    if (uiOperator.findElement("user_nickname", 3000)) {
      return true;
    }
    logger.warn(TAG, "点击头像后未检测到主页，回退重试");
  }

  // 降级：找该昵称文本
  try {
    var nameEl = text(nickname).findOne(3000);
    if (nameEl) {
      nameEl.parent().click();
      sleep(2000);
      if (uiOperator.findElement("user_nickname", 3000)) {
        return true;
      }
    }
  } catch (e) {
    logger.warn(TAG, "点击昵称失败: " + e.message);
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
      if (!followed) {
        sleep(Math.floor(Math.random() * 600 + 400));
        press(fbx, fby, Math.floor(Math.random() * 100 + 80));
        sleep(Math.floor(Math.random() * 1000 + 1000));
        if (uiOperator.findElement("is_follow", 2000)) followed = true;
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
  var data = { nickname: "", douyin_id: "", likes_count: "", follow_count: "",
    fans_count: "", works_count: "", gender: "", age: "", ip_location: "", is_private: "否" };

  var fields = {
    "user_nickname": "nickname", "user_douyin_id": "douyin_id",
    "user_likes_count": "likes_count", "user_follow_count": "follow_count",
    "user_fans_count": "fans_count", "user_works_count": "works_count",
    "user_gender": "gender", "user_age": "age", "user_ip_location": "ip_location"
  };
  var hasData = false;
  for (var actionName in fields) {
    try {
      var el = uiOperator.findElement(actionName, 2000);
      if (el) {
        var selector = selectorLoader.get(actionName);
        data[fields[actionName]] = (selector && selector.purpose === "extract")
          ? uiOperator.extractValue(el, selector) : (el.text() || "");
        if (data[fields[actionName]]) hasData = true;
      }
    } catch (e) {}
  }
  // Strip "· " / "・ " prefix from user IP location
  if (data.ip_location) data.ip_location = data.ip_location.replace(/^[·•・\s]+/, "");

  // Clean numeric fields: extract digits, handle Chinese units (万/千), strip accessibility noise
  var numericFields = { likes_count: 1, follow_count: 1, fans_count: 1, works_count: 1 };
  for (var key in numericFields) {
    if (data[key]) {
      var raw = String(data[key]);
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

  if (hasData) {
    logger.info(TAG, "用户数据: " + data.nickname + " | 抖音号=" + data.douyin_id +
      " | 粉丝=" + data.fans_count + " | 获赞=" + data.likes_count + " | 作品=" + data.works_count);
    return data;
  }
  return null;
};

/**
 * 发送私信
 * @param {string} content - 私信内容
 */
ReplyCommentHandler._sendDM = function (content) {
  // 1. 进入私信页：点 dm_entry_btn
  var messageClicked = this.safeClick("dm_entry_btn", 3);
  if (!messageClicked) {
    logger.warn(TAG, "私信按钮未找到");
    return false;
  }
  sleep(1500);

  // 2. 点击 dm_input 触发键盘，输入框自动获得焦点
  if (!this.safeClick("dm_input", 2)) {
    logger.warn(TAG, "dm_input 未找到");
    return false;
  }
  sleep(800);

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
    var dummyChars = "abcdefghijklmnopqrstuvwxyz";
    var dummy = dummyChars.charAt(Math.floor(Math.random() * dummyChars.length));
    input(dummy);
    sleep(Math.floor(Math.random() * 150 + 100));
    // 用无障碍删除随机字符（比 shell 可靠）
    if (dmEdit) { dmEdit.setText(" "); sleep(200); }
    var pos = 0;
    while (pos < content.length) {
      var chunkSize = Math.random() < 0.4 ? 1 : (Math.floor(Math.random() * 2) + 2);
      chunkSize = Math.min(chunkSize, content.length - pos);
      input(content.substring(pos, pos + chunkSize));
      pos += chunkSize;
      sleep(Math.floor(Math.random() * 150 + 80));
    }
    pasted = true;
    logger.info(TAG, "私信 input 输入成功: '" + content.substring(0, 20) + "'");
  } catch (e) {
    logger.warn(TAG, "私信 input 异常: " + e.message);
  }

  // 4. 兜底：剪贴板粘贴
  if (!pasted) {
    try {
      setClip(content);
      sleep(200);
      shell("input keyevent 279", false);
      sleep(500);
      pasted = true;
    } catch (e) { /* ignore */ }
  }

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
    // 兜底：回车发送
    try { shell("input keyevent 66", false); } catch (e) {}
    sleep(500);
  }

  logger.info(TAG, "私信已发送: '" + content.substring(0, 20) + "'");
  return true;
};

/**
 * 容错返回评论区（从私信页/个人主页/任意页面回到评论区）
 * 使用选择器动作名检测当前页面，不依赖固定次数 back
 *
 * 页面检测选择器（需在管理后台配置）：
 *   is_comment_view  — 当前在评论面板？
 *   is_user_view     — 当前在个人主页？
 */
ReplyCommentHandler._returnToComments = function () {
  var maxBacks = 5;
  for (var i = 0; i < maxBacks; i++) {
    // 已在评论面板 → 完成
    if (uiOperator.findElement("is_comment_view", 500)) {
      logger.info(TAG, "回到评论区 (back " + i + " 次)");
      return;
    }

    // 在个人主页 → 优先级高于视频页（主页作品Tab有视频缩略图，is_video_view 会误匹配）
    if (uiOperator.findElement("is_user_view", 300) ||
        uiOperator.findElement("user_nickname", 300)) {
      logger.info(TAG, "在个人主页，back 到评论区");
      back(); sleep(800);
      continue;  // back 后重新检测，可能到视频页或评论面板
    }

    // 在私信页 → back 到个人主页
    var onDMPage = uiOperator.findElement("dm_input", 300)
                || uiOperator.findElement("dm_send", 300);
    if (onDMPage) {
      logger.info(TAG, "在私信页，back 到个人主页");
      back(); sleep(800);
      continue;
    }

    // 已在视频详情页 → 打开评论区
    if (uiOperator.findElement("is_video_view", 500) ||
        uiOperator.findElement("video_comment_btn", 500)) {
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
