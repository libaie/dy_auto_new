// device/handlers/nurture.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var aiAnalyzer = require("../core/ai-analyzer");
var logger = require("../utils/logger");
var flowContext = require("../core/flow-context");
var taskExecutor = require("../core/task-executor");

var TAG = "养号";

/**
 * 养号 Handler
 * V2 params:
 *   - sub_tasks: Array<{ type: string, count: number, content_template_id?: string }>
 *   - completion_mode: "all" | "any"
 *   - duration: number (最大时长，分钟)
 *   - keyword_matrix: string[] (可选，AI 扩展的关键词矩阵，用于内容语义过滤)
 * Legacy params:
 *   - duration: number (养号时长，分钟)
 *   - actions: Array<{ type: string, weight: number }>
 */
var NurtureHandler = Object.create(BaseHandler);

NurtureHandler.execute = function (params) {
  // V2 format: sub_tasks + completion_mode
  if (params.sub_tasks) {
    return this._executeV2(params);
  }
  // Legacy format: duration + actions
  return this._legacyExecute(params);
};

NurtureHandler._executeV2 = function (params) {
  var subTasks = params.sub_tasks;
  var completionMode = params.completion_mode || "all";
  var maxDuration = (params.duration || 60) * 60 * 1000;
  var startTime = Date.now();

  // Store keyword matrix for content filtering
  this._keywordMatrix = params.keyword_matrix || [];

  // 加载服务端提示词模板
  aiAnalyzer.useTemplate(params.prompt_template_id);

  logger.info(TAG, "开始养号 V2, 子任务数=" + subTasks.length + ", 模式=" + completionMode +
    (this._keywordMatrix.length > 0 ? ", 关键词=" + this._keywordMatrix.length + "个" : ""));

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  // Initialize progress for each sub-task
  var progress = subTasks.map(function (st) {
    return {
      type: st.type,
      target: st.count,
      done: 0,
      contentTemplateId: st.content_template_id || null,
    };
  });

  while (Date.now() - startTime < maxDuration) {
    if (taskExecutor.isCancelled()) {
      logger.info(TAG, "任务已取消，停止养号");
      break;
    }
    // Find incomplete sub-tasks
    var pending = progress.filter(function (p) { return p.done < p.target; });
    if (pending.length === 0) {
      logger.info(TAG, "所有子任务已完成");
      break;
    }

    // Randomly pick one incomplete sub-task
    var task = pending[Math.floor(Math.random() * pending.length)];

    // 执行前确保在推荐页（防止误触跳转后所有操作都在错误页面）
    this._ensureOnFeed();

    try {
      this._executeSubTask(task);
      task.done++;
    } catch (e) {
      logger.error(TAG, "子任务 '" + task.type + "' 出错: " + e.message);
    }

    // Log progress
    var progressSummary = progress.map(function (p) {
      return p.type + ":" + p.done + "/" + p.target;
    }).join(" ");
    logger.info(TAG, "进度: " + progressSummary);

    // Check completion condition
    if (completionMode === "any") {
      var anyDone = progress.some(function (p) { return p.done >= p.target; });
      if (anyDone) {
        logger.info(TAG, "任一子任务完成，结束养号");
        break;
      }
    }

    antiDetect.humanSwipeUp();
  }

  // Build stats
  var stats = { success_count: 0 };
  progress.forEach(function (p) {
    stats[p.type] = { target: p.target, done: p.done };
    if (p.type === "like" || p.type === "comment" || p.type === "follow") {
      stats.success_count += p.done;
    }
  });

  logger.info(TAG, "养号 V2 完成: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

NurtureHandler._executeSubTask = function (task) {
  switch (task.type) {
    case "browse":
      this._browseFeed();
      break;
    case "watch":
      this._watchVideo();
      break;
    case "like":
      this._likeCurrentVideo();
      break;
    case "comment":
      this._commentOnVideo(task.contentTemplateId);
      break;
    case "follow":
      this._followCurrentUser();
      break;
    default:
      this._browseFeed();
  }
};

NurtureHandler._browseFeed = function () {
  this._ensureOnFeed();
  // 浏览推荐页：快速扫一眼，大部分 2-5 秒，偶尔多停一会
  var watchTime = this._humanDuration(2000, 8000, 4000);
  logger.debug(TAG, "浏览推荐页 " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

NurtureHandler._watchVideo = function () {
  // 先检测是否是广告 — 广告直接跳过
  if (this._isAdContent()) {
    logger.info(TAG, "检测到广告，直接跳过");
    return;
  }

  // 检测内容互动数据来判断质量
  var quality = this._assessContentQuality();
  var watchTime;

  if (quality === "high") {
    // 精彩内容：看得久，30-60 秒，偶尔模拟看评论
    watchTime = this._humanDuration(25000, 60000, 40000);
    logger.debug(TAG, "精彩内容，深度观看 " + Math.round(watchTime / 1000) + "s");
  } else if (quality === "medium") {
    // 普通内容：15-30 秒
    watchTime = this._humanDuration(12000, 30000, 20000);
    logger.debug(TAG, "普通内容，正常观看 " + Math.round(watchTime / 1000) + "s");
  } else {
    // 无亮点内容：3-10 秒快速划走
    watchTime = this._humanDuration(3000, 10000, 5000);
    logger.debug(TAG, "无亮点内容，快速划走 " + Math.round(watchTime / 1000) + "s");
  }

  sleep(watchTime);

  // 精彩内容有概率模拟看评论区（停留更久）
  if (quality === "high" && Math.random() < 0.3) {
    var commentPause = Math.floor(Math.random() * 5000 + 3000);
    logger.debug(TAG, "模拟浏览评论区 " + Math.round(commentPause / 1000) + "s");
    sleep(commentPause);
  }
};

/**
 * 生成拟人化的观看时长 — 基于对数正态分布
 * 大部分时间偏短，偶尔有长停留，符合真实用户行为
 * @param {number} min - 最小时长(ms)
 * @param {number} max - 最大时长(ms)
 * @param {number} median - 中位数(ms)，控制主体集中位置
 * @returns {number} 拟人化的时长(ms)
 */
NurtureHandler._humanDuration = function (min, max, median) {
  // 对数正态分布：ln(N(mu, sigma)) 产生右偏分布
  var mu = Math.log(median);
  var sigma = 0.5; // 控制离散程度，0.3-0.6 较自然
  // Box-Muller 变换生成正态随机数
  var u1 = Math.random();
  var u2 = Math.random();
  var z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  var value = Math.exp(mu + sigma * z);
  // 限制在 [min, max] 范围内
  return Math.max(min, Math.min(max, Math.round(value)));
};

/**
 * 检测当前屏幕是否为广告内容
 * @returns {boolean}
 */
NurtureHandler._isAdContent = function () {
  try {
    // 常见广告标识文本
    var adTexts = [
      "广告", "推广", "赞助", "购物", "立即购买", "查看详情",
      "立即下载", "免费领取", "限时优惠", "立即抢购", "点击购买",
      "小黄车", "商品橱窗", "去购买", "马上抢",
    ];
    for (var i = 0; i < adTexts.length; i++) {
      var el = textContains(adTexts[i]).findOne(2000);
      if (el) {
        logger.info(TAG, "发现广告标识: " + adTexts[i]);
        return true;
      }
    }
    // 检查是否在购物/商品页面（右下角有购物车图标）
    var shopBtn = desc("购物车").findOne(2000);
    if (shopBtn) {
      logger.info(TAG, "发现购物车标识，判定为广告");
      return true;
    }
    // 检查带货标签
    var sellTags = descContains("购物车").findOne(2000);
    if (sellTags) {
      logger.info(TAG, "发现带货标签，判定为广告");
      return true;
    }
  } catch (e) {
    // 检测失败不影响正常流程
  }
  return false;
};

/**
 * 检查当前视频内容是否与关键词矩阵相关
 * 先做本地关键词匹配，匹配不到再用 AI 语义分析
 * @param {string} videoText - 视频文本内容
 * @returns {boolean} true=相关或无关键词过滤, false=不相关
 */
NurtureHandler._isKeywordRelevant = function (videoText) {
  if (!this._keywordMatrix || this._keywordMatrix.length === 0) return true;
  if (!videoText || videoText.length < 2) return true;

  var t = videoText.toLowerCase();

  // 本地关键词匹配 — 快速判断
  for (var i = 0; i < this._keywordMatrix.length; i++) {
    if (t.indexOf(this._keywordMatrix[i].toLowerCase()) !== -1) {
      logger.debug(TAG, "本地命中关键词: " + this._keywordMatrix[i]);
      return true;
    }
  }

  // 本地未命中，用 AI 做语义分析
  var keywords = this._keywordMatrix.join("、");
  var prompt = "判断以下抖音视频内容是否与下列关键词相关。\n\n" +
    "关键词：" + keywords + "\n\n" +
    "内容：" + videoText.substring(0, 300) + "\n\n" +
    "只回答一个JSON：{\"related\": true/false, \"reason\": \"简短原因\"}";

  var content = aiAnalyzer._callAI(prompt, 100, 0.1);
  if (!content) {
    logger.warn(TAG, "关键词语义分析失败，默认放行");
    return true;
  }

  try {
    var jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      var data = JSON.parse(jsonMatch[0]);
      logger.info(TAG, "关键词相关性: " + (data.related ? "相关" : "不相关") + " - " + (data.reason || ""));
      return !!data.related;
    }
  } catch (e) {
    logger.warn(TAG, "关键词语义分析解析失败: " + e.message);
  }
  return true;
};

/**
 * 评估当前视频内容质量 — 基于可见的互动数据
 * @returns {"high" | "medium" | "low"}
 */
NurtureHandler._assessContentQuality = function () {
  try {
    // 尝试读取点赞数（控件 id 可能随版本变化）
    var likeCountEl = id("com.ss.android.ugc.aweme:id/like_count").findOne(2000);
    if (likeCountEl) {
      var likeText = likeCountEl.text() || "";
      var likeNum = this._parseCount(likeText);
      // 高赞内容判定：万级以上
      if (likeNum >= 10000) return "high";
      if (likeNum >= 1000) return "medium";
    }

    // 尝试读取评论数
    var commentCountEl = id("com.ss.android.ugc.aweme:id/comment_count").findOne(2000);
    if (commentCountEl) {
      var commentText = commentCountEl.text() || "";
      var commentNum = this._parseCount(commentText);
      if (commentNum >= 1000) return "high";
      if (commentNum >= 100) return "medium";
    }
  } catch (e) {
    // 读取失败时降级为随机判定
  }

  // 无法读取数据时，用概率模拟：20% 高、50% 中、30% 低
  var r = Math.random();
  if (r < 0.2) return "high";
  if (r < 0.7) return "medium";
  return "low";
};

/**
 * 解析抖音互动数字文本（支持 "1.2万"、"3.5亿" 等格式）
 * @param {string} text - 数字文本
 * @returns {number}
 */
NurtureHandler._parseCount = function (text) {
  if (!text) return 0;
  text = text.replace(/,/g, "").trim();
  if (text.indexOf("w") !== -1 || text.indexOf("万") !== -1) {
    return Math.round(parseFloat(text) * 10000);
  }
  if (text.indexOf("亿") !== -1) {
    return Math.round(parseFloat(text) * 100000000);
  }
  var num = parseInt(text, 10);
  return isNaN(num) ? 0 : num;
};

/**
 * 确保在推荐页 — 如果误触跳转到其他页面，返回推荐页
 * 使用选择器系统检测点赞按钮（推荐页特征），避免硬编码 ID 失效
 * 支持最多重试 5 次，每次优先 safeClick("back_btn")，失败则回退系统 back()
 */
NurtureHandler._ensureOnFeed = function () {
  var maxRetries = 5;
  for (var attempt = 0; attempt < maxRetries; attempt++) {
    try {
      // 检测是否在推荐页
      if (uiOperator.isOnPage("feed")) { flowContext.enter("feed"); return; }

      // 检测是否在有底部 tab 的主页面（首页/朋友/消息/我的）
      var homeTab = text("首页").findOne(2000);
      if (homeTab) {
        // 在主页但不在推荐视频流，点击"首页" tab
        logger.info(TAG, "在主页面，点击首页 tab（第" + (attempt + 1) + "次）");
        homeTab.parent().click();
        sleep(2000);
        continue;
      }

      logger.info(TAG, "不在推荐页（第" + (attempt + 1) + "次），尝试返回");

      // 优先使用选择器系统的 back_btn
      var backed = this.safeClick("back_btn", 1);
      if (!backed) {
        // 选择器找不到，回退到系统 back() — 万能兜底
        logger.info(TAG, "back_btn 未找到，使用系统 back()");
        back();
      }
      sleep(1500);
    } catch (e) {
      logger.warn(TAG, "页面检测异常: " + e.message);
      back(); // 异常时也尝试系统 back
      sleep(1000);
    }
  }
  logger.warn(TAG, maxRetries + " 次尝试后仍未回到推荐页");
};

NurtureHandler._likeCurrentVideo = function () {
  if (this._isAdContent()) {
    logger.info(TAG, "广告内容，跳过点赞");
    return;
  }
  var videoText = this._extractVideoText();
  if (!this._isKeywordRelevant(videoText)) {
    logger.info(TAG, "内容与关键词不相关，跳过点赞");
    return;
  }
  if (!aiAnalyzer.checkHealthRelevance(videoText)) {
    logger.info(TAG, "内容与大健康不相关，跳过点赞");
    return;
  }
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "点赞成功");
  }
};

NurtureHandler._commentOnVideo = function (templateId) {
  if (this._isAdContent()) {
    logger.info(TAG, "广告内容，跳过评论");
    return;
  }
  var videoText = this._extractVideoText();
  if (!this._isKeywordRelevant(videoText)) {
    logger.info(TAG, "内容与关键词不相关，跳过评论");
    return;
  }
  // 1. AI 生成评论
  var content = aiAnalyzer.generateVideoComment(videoText);
  if (!content) {
    logger.warn(TAG, "AI 生成评论失败，跳过评论");
    return;
  }
  logger.info(TAG, "AI 生成评论: '" + content.substring(0, 20) + "'");

  // 2. 点击评论入口按钮，打开评论面板
  var opened = this.safeClick("video_comment_btn", 3);
  if (!opened) {
    logger.warn(TAG, "评论入口按钮未找到");
    return;
  }
  sleep(1500);

  // 3. 点击评论输入框，弹出键盘
  var inputClicked = this.safeClick("video_comment_input", 3);
  if (!inputClicked) {
    logger.warn(TAG, "评论输入框未找到");
    back();
    sleep(500);
    return;
  }
  sleep(1000);

  // 4. 输入评论内容
  var inputResult = this.safeInput("video_comment_input", content);
  if (!inputResult) {
    logger.warn(TAG, "输入评论内容失败");
    back();
    sleep(500);
    return;
  }
  sleep(500);

  // 5. 通过键盘回车提交评论
  sleep(500);
  this.submitViaKeyboard("comment_submit");
  sleep(1000);
  logger.info(TAG, "评论成功");

  // 6. 关闭评论面板
  this.safeClick("back_btn", 2);
  sleep(800);
};

NurtureHandler._followCurrentUser = function () {
  if (this._isAdContent()) {
    logger.info(TAG, "广告内容，跳过关注");
    return;
  }
  var videoText = this._extractVideoText();
  if (!this._isKeywordRelevant(videoText)) {
    logger.info(TAG, "内容与关键词不相关，跳过关注");
    return;
  }
  if (!aiAnalyzer.checkHealthRelevance(videoText)) {
    logger.info(TAG, "内容与大健康不相关，跳过关注");
    return;
  }
  var clicked = this.safeClick("follow_button", 2);
  if (clicked) {
    logger.info(TAG, "关注成功");
  }
};

// --- Legacy support ---
NurtureHandler._legacyExecute = function (params) {
  var duration = params.duration || 30;
  var actions = params.actions || [
    { type: "browse_feed", weight: 70 },
    { type: "like", weight: 20 },
    { type: "follow", weight: 10 },
  ];

  logger.info(TAG, "开始养号(旧版) " + duration + " 分钟");

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  var startTime = Date.now();
  var endTime = startTime + duration * 60 * 1000;
  var stats = { videos_watched: 0, likes: 0, follows: 0, errors: 0 };

  while (Date.now() < endTime) {
    this._ensureOnFeed();
    var action = this._weightedRandom(actions);
    try {
      switch (action.type) {
        case "browse_feed":
          this._browseFeed();
          break;
        case "like":
          this._likeCurrentVideo();
          break;
        case "follow":
          this._followCurrentUser();
          break;
        default:
          this._browseFeed();
      }
    } catch (e) {
      logger.error(TAG, "养号操作 '" + action.type + "' 出错: " + e.message);
      stats.errors++;
    }
    antiDetect.humanSwipeUp();
    stats.videos_watched++;
  }

  stats.success_count = stats.likes + stats.follows;
  logger.info(TAG, "养号完成. 统计: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

NurtureHandler._weightedRandom = function (actions) {
  var totalWeight = actions.reduce(function (sum, a) { return sum + a.weight; }, 0);
  var random = Math.random() * totalWeight;
  var cumulative = 0;
  for (var i = 0; i < actions.length; i++) {
    cumulative += actions[i].weight;
    if (random < cumulative) return actions[i];
  }
  return actions[0];
};

module.exports = NurtureHandler;
