// device/core/ai-analyzer.js
var config = global.__config || require("../config");
var apiClient = require("./api-client");
var promptsConfig = require("./prompts-config");
var logger = require("../utils/logger");

var TAG = "AI";

/**
 * 设备端 AI 分析模块
 * 通过服务端代理调用 AI，设备端不持有 API Key
 * 行业相关提示词统一在 prompts-config.js 管理
 */
var aiAnalyzer = {
  SCORE_THRESHOLD: 40,

  /**
   * 加载服务端提示词模板（从 promptTemplateLoader 缓存中查找）
   * 不传 id 或找不到时回退到 prompts-config.js 本地配置
   * @param {string} [id] — 模板 ID
   */
  useTemplate: function (id) {
    var loader = require("./prompt-template-loader");
    var tmpl = id ? loader.get(id) : null;
    if (tmpl && tmpl.content) {
      var ok = promptsConfig.setOverride(tmpl.content);
      if (ok) {
        promptsConfig.setIndustry(tmpl.industry || "health");
        logger.info(TAG, "使用服务端模板: " + tmpl.name + " (" + (tmpl.industry || "") + ")");
      } else {
        promptsConfig.setOverride(null);
        promptsConfig.setIndustry("health");
        this._destCache = {};
        logger.warn(TAG, "模板 " + tmpl.name + " 校验失败，回退本地配置");
      }
    } else {
      promptsConfig.setOverride(null);
      promptsConfig.setIndustry("health");
      this._destCache = {};
      if (id) logger.warn(TAG, "模板 " + id + " 未找到，使用本地默认配置");
    }
  },

  /**
   * 切换行业（本地配置）
   * @param {string} name — 行业标识，如 "health" / "travel"
   */
  setIndustry: function (name) {
    if (promptsConfig.industry !== name) this._destCache = {};
    promptsConfig.setIndustry(name);
    logger.info(TAG, "切换行业: " + (promptsConfig.get().name || name));
  },

  getIndustry: function () {
    return promptsConfig.industry;
  },

  _destCache: {},

  resolveDestination: function (keyword) {
    if (promptsConfig.industry !== "travel") return null;
    if (!keyword) return null;
    if (this._destCache[keyword]) return this._destCache[keyword];

    var prompt = [
      "将以下旅游关键词解析为目的地信息。",
      "关键词：" + keyword,
      "请输出一个 JSON：",
      "{\"province\": \"省份\", \"city\": \"城市\", \"attraction\": \"景点\"}",
      "如果关键词本身是省份或城市，对应字段填空字符串，其余字段正常填写。",
      "只输出 JSON，不要其他文本。"
    ].join("\n");

    var content = this._callAI(prompt, 200, 0.1);
    if (!content) return null;

    try {
      var jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        var data = JSON.parse(jsonMatch[0]);
        this._destCache[keyword] = data;
        logger.info(TAG, "目的地解析: " + keyword + " → " + JSON.stringify(data));
        return data;
      }
    } catch (e) {
      logger.warn(TAG, "目的地解析失败: " + keyword + " " + e.message);
    }
    return null;
  },

  /**
   * 调用服务端 AI 代理
   */
  _callAI: function (prompt, maxTokens, temperature) {
    if (!config.serverUrl || !config.deviceSecret) {
      logger.error(TAG, "设备未配对，无法调用 AI");
      return null;
    }

    try {
      var result = apiClient.post("/api/device/ai-proxy", {
        prompt: prompt,
        max_tokens: maxTokens || 4096,
        temperature: temperature != null ? temperature : 0.7,
      }, 120000);  // AI 生成最长等 2 分钟

      if (!result || !result.content) {
        logger.error(TAG, "AI 代理返回空内容");
        return null;
      }
      return result.content.trim();
    } catch (e) {
      logger.error(TAG, "AI 代理调用失败: " + e.message);
      return null;
    }
  },

  /**
   * 分析单条评论
   */
  analyzeComment: function (params) {
    var searchKeyword = params.searchKeyword;
    var nickname = params.nickname;
    var commentText = params.commentText;

    if (!commentText) {
      logger.warn(TAG, "Empty comment text");
      return null;
    }

    var prompt = this._buildAnalysisPrompt(searchKeyword, nickname, commentText);
    var content = this._callAI(prompt, 1024, 0.3);
    if (!content) {
      logger.warn(TAG, "AI analysis failed");
      return null;
    }

    var result = this._parseAnalysisResponse(content);
    if (!result) {
      logger.warn(TAG, "AI 解析失败，重试一次");
      content = this._callAI(prompt, 256, 0.3);
      if (content) {
        result = this._parseAnalysisResponse(content);
      }
    }
    return result;
  },

  /**
   * 解析 AI 分析响应
   */
  _parseAnalysisResponse: function (content) {
    try {
      var jsonMatch = content.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        logger.error(TAG, "No JSON found in AI response");
        return null;
      }

      var data = JSON.parse(jsonMatch[0]);

      if (typeof data.score !== "number" || !data.reply) {
        logger.error(TAG, "Invalid AI response structure");
        return null;
      }

      data.reply = data.reply.replace(/^["'「]|["'」]$/g, "");
      return data;
    } catch (e) {
      logger.error(TAG, "Parse AI response failed: " + e.message);
      return null;
    }
  },

  /**
   * 本地关键词预过滤
   */
  _localRelevanceCheck: function (text) {
    if (!text) return null;
    var t = text.toLowerCase();
    var filter = promptsConfig.get().localFilter;

    var excludePatterns = filter.exclude;
    for (var i = 0; i < excludePatterns.length; i++) {
      if (t.indexOf(excludePatterns[i]) !== -1) return false;
    }

    var includePatterns = filter.include;
    for (var j = 0; j < includePatterns.length; j++) {
      if (t.indexOf(includePatterns[j]) !== -1) return true;
    }

    return null;
  },

  /**
   * 检查当前内容是否与目标领域相关
   */
  checkRelevance: function (contentText, domain) {
    if (!contentText || contentText.length < 2) return true;

    var localResult = this._localRelevanceCheck(contentText);
    if (localResult !== null) {
      logger.info(TAG, "本地预过滤: " + (localResult ? "相关" : "不相关") + " — " + contentText.substring(0, 30));
      return localResult;
    }

    domain = domain || promptsConfig.get().domain;

    var prompt = "判断以下抖音视频内容是否与" + domain + "领域相关。\n\n" +
      "内容：" + contentText.substring(0, 300) + "\n\n" +
      "只回答一个JSON：{\"related\": true/false, \"reason\": \"简短原因\"}";

    var content = this._callAI(prompt, 100, 0.1);
    if (!content) {
      logger.warn(TAG, "内容判断失败，默认放行");
      return true;
    }

    try {
      var jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        var data = JSON.parse(jsonMatch[0]);
        logger.info(TAG, "内容相关性: " + (data.related ? "相关" : "不相关") + " - " + (data.reason || ""));
        return !!data.related;
      }
    } catch (e) {
      logger.warn(TAG, "内容判断解析失败: " + e.message);
    }
    return true;
  },

  // 兼容旧方法名
  checkHealthRelevance: function (contentText, domain) {
    return this.checkRelevance(contentText, domain);
  },

  /**
   * 根据视频内容生成评论
   */
  generateVideoComment: function (videoText) {
    if (!videoText || videoText.length < 2) {
      logger.warn(TAG, "视频文本太短，无法生成评论");
      return null;
    }

    var vc = promptsConfig.get().videoComment;
    var dw = promptsConfig.get().disabledWords;

    var prompt = vc.context + "\n\n" +
      "## 你的目标\n" + (vc.goal || "写一条自然真实的评论") + "\n\n" +
      "## 要求\n" +
      "- " + vc.rules.join("\n- ") + "\n" +
      "- 严禁禁用词：" + dw + "\n\n" +
      "## 视频内容\n" + videoText.substring(0, 500) + "\n\n" +
      "只输出评论文本，不要引号、不要其他解释。";

    var text = this._callAI(prompt, 200, 0.8);
    if (text) {
      text = text.replace(/^["'「]|["'」]$/g, "");
      logger.info(TAG, "AI 生成评论: '" + text.substring(0, 30) + "'");
    }
    return text;
  },

  /**
   * 生成私信 — opener 阶段（破冰）
   */
  generateDM: function (params) {
    var searchKeyword = params.searchKeyword || "";
    var nickname = params.nickname || "";
    var commentText = params.commentText || "";
    var tier = params.tier || "other";
    var videoText = params.videoText || "";
    var intendedCity = params.intendedCity || params.intended_city || "";

    var dm = promptsConfig.get().dmOpener;
    var dw = promptsConfig.get().disabledWords;
    // DM 专用身份优先，回退顶层身份
    var dmId = dm.identity || promptsConfig.get().identity;

    var prompt = dm.context + "\n\n" +
      "## 绝对禁用词（任何情况下不得出现）\n" + dw + "\n\n" +
      "## 身份设定\n" +
      "- 你是" + dmId.role + "\n" +
      "- " + dmId.constraints.join("\n- ") + "\n" +
      "- **严禁自我代入**：不要用\"我都是…\"、\"我自己…\"、\"我家…\"等第一人称经验分享。\n" +
      "- 使用建议/指南风格：用\"可以尝试\"、\"建议\"、\"若想…\"等客观建议句式。\n\n" +
      "## 这一条是破冰，唯一目标\n" + dm.goal + "\n\n" +
      "## 风格\n" +
      "- " + dm.style.join("\n- ") + "\n\n" +
      "根据 tier 选择语气：\n" +
      "- strong_buy: " + (dm.tierTones.strong_buy || "") + "\n" +
      "- health_consult: " + (dm.tierTones.health_consult || dm.tierTones.travel_consult || "") + "\n" +
      "- patient_self: " + (dm.tierTones.patient_self || dm.tierTones.strong_buy || "") + "\n" +
      "- other: " + (dm.tierTones.other || "") + "\n\n" +
      "## 输入\n" +
      "- 搜索词：" + searchKeyword + "\n" +
      "- 对方昵称：" + nickname + "\n" +
      (commentText ? "- 对方的评论：" + commentText + "\n" : "") +
      (videoText ? "- 视频内容：" + videoText.substring(0, 300) + "\n" : "") +
      (intendedCity ? "- 对方意向目的地：" + intendedCity + "\n" : "") +
      "- 命中分层：" + tier + "\n\n" +
      "请输出一条开场白，**只输出消息文本本身，不要引号、不要解释**。";

    var text = this._callAI(prompt, 200, 0.8);
    if (text) {
      text = text.replace(/^["'「]|["'」]$/g, "");
      logger.info(TAG, "AI 生成私信(opener): '" + text.substring(0, 30) + "'");
    }
    return text;
  },

  /**
   * 根据视频内容生成私信（兼容旧接口）
   */
  generateVideoDM: function (videoText) {
    return this.generateDM({ videoText: videoText });
  },

  /**
   * 多阶段私信生成
   */
  generateDMStage: function (stage, params) {
    var stages = promptsConfig.get().dmStages;
    var cfg = stages[stage];
    if (!cfg) { logger.warn(TAG, "未知私信阶段: " + stage); return null; }

    var dw = promptsConfig.get().disabledWords;
    var dmId = promptsConfig.get().dmOpener.identity || promptsConfig.get().identity;

    var prompt = "你是" + dmId.role + "，与对方私信已有互动。当前阶段：" + cfg.name + "。\n\n" +
      "## 禁用词（强制）\n" + dw + "\n\n" +
      "## 阶段目标\n" + cfg.goal + "\n\n" +
      "## 风格\n" + cfg.style + "\n\n" +
      "- **严禁自我代入**：不要用\"我家…\"\"我也是…\"\"我自己…\"等第一人称经验分享。\n" +
      "- 不给医嘱，不指导用药。\n\n" +
      "## 输入\n" +
      "- 搜索词：" + (params.searchKeyword || "") + "\n" +
      "- 对方昵称：" + (params.nickname || "") + "\n" +
      (params.silentDays ? "- 沉默天数：" + params.silentDays + "\n" : "") +
      "- 最近对话：\n" + (params.history || "(首轮对话)") + "\n\n" +
      "请**只输出消息文本本身**，不要引号、不要解释。";

    var text = this._callAI(prompt, cfg.maxTokens, 0.7);
    if (text) {
      text = text.replace(/^["'「]|["'」]$/g, "");
      logger.info(TAG, "AI 私信(" + stage + "): '" + text.substring(0, 30) + "'");
    }
    return text;
  },

  /**
   * 构建五维度分析提示词 — 从 prompts-config 拼接
   */
  _buildAnalysisPrompt: function (searchKeyword, nickname, commentText) {
    var p = promptsConfig.get();
    var id = p.identity;
    var dw = p.disabledWords;
    var sg = p.semanticGuide;
    var an = p.analysis;

    // 语义分析指南
    var highList = sg.highValueSignals.map(function (s, i) { return (i + 1) + ". " + s; }).join("\n");
    var lowList = sg.lowValueSignals.map(function (s, i) { return (i + 1) + ". " + s; }).join("\n");
    var exList = sg.keyExamples.join("\n");

    // 五维度
    var intents = an.intents.map(function (s) { return "- " + s; }).join("\n");
    var sentiments = an.sentiments.map(function (s) { return "- " + s; }).join("\n");
    var scoring = an.scoringRules.map(function (s) { return "- " + s; }).join("\n");
    var replyRules = an.replyRules.map(function (s) { return "- " + s; }).join("\n");

    // tier 语气
    var tierLines = [];
    for (var tierKey in an.tiers) {
      tierLines.push("- " + tierKey + ": " + an.tiers[tierKey]);
    }
    var tierText = tierLines.join("\n");

    return "你具有评论语义分析能力。当前视频的搜索关键词是【" + searchKeyword + "】，它代表了视频的主题和内容方向，评论与关键词关联越紧密，越可能是有真实需求的用户。\n\n" +
      "## 身份设定\n" +
      "- 你是" + id.role + "\n" +
      "- " + id.constraints.join("\n- ") + "\n" +
      "- **严禁自我代入**：不要用\"我都是…\"、\"我自己…\"、\"我家…\"等第一人称经验分享。\n" +
      "- 使用建议/指南风格：用\"可以试试\"、\"建议\"、\"若想…\"等客观建议句式。\n\n" +
      "## 绝对禁用词（任何情况下不得出现）\n" + dw + "\n\n" +
      "## 语义分析指南 — 先理解评论再打分\n\n" +
      "你的核心任务是判断：**" + sg.mission + "**。\n\n" +
      "### 高价值信号（满足任一即说明评论者有真实需求）：\n" + highList + "\n\n" +
      "### 低价值信号（不是真实需求）：\n" + lowList + "\n\n" +
      "### 关键区分示例：\n" + exList + "\n\n" +
      "## 五维度分析模型\n\n" +
      "### 1. 意图识别 (intent)\n" + intents + "\n\n" +
      "### 2. 情感倾向 (sentiment)\n" + sentiments + "\n\n" +
      "### 3. 关注实体 (focus)\n" +
      "- price (价格) / quality (功效/质量) / location (地域) / other\n\n" +
      "### 4. 用户画像 (profile)\n" +
      "- role: 宝妈、上班族、退休老人、学生等\n" +
      "- spending: low / mid / high\n\n" +
      "### 5. 线索质量 (lead_quality)\n" +
      "- urgency (1-10): 提及具体需求，或语气急切/痛苦 → 至少 7\n" +
      "- specific_condition (是否提及具体需求关键词): 评论包含行业相关的具体关键词 → true\n" +
      "- is_bot / is_competitor\n\n" +
      "## 评分规则\n" + scoring + "\n\n" +
      "## 回复生成规则\n" + replyRules + "\n" +
      "- **回复正文不要加「回复 @昵称」前缀，系统会自动显示**\n" +
      "- 输出示例：✅ \"" + an.replyExample.good + "\" | ❌ \"" + an.replyExample.bad + "\"\n\n" +
      "根据 tier 选择语气：\n" + tierText + "\n\n" +
      "## 输入\n" +
      "- 搜索词：" + searchKeyword + "\n" +
      "- 对方昵称：" + nickname + "\n" +
      "- 对方的评论：" + commentText + "\n\n" +
      "## 输出格式（严格 JSON）\n" +
      "{\n" +
      "  \"score\": 75,\n" +
      "  \"tier\": \"high\",\n" +
      "  \"dimensions\": {\n" +
      "    \"intent\": \"health_consult\",\n" +
      "    \"sentiment\": \"neutral\",\n" +
      "    \"focus\": \"quality\",\n" +
      "    \"profile\": { \"role\": \"unknown\", \"spending\": \"mid\" },\n" +
      "    \"lead_quality\": { \"urgency\": 8, \"specific_condition\": true, \"is_bot\": false, \"is_competitor\": false }\n" +
      "  },\n" +
      "  \"reply\": \"" + an.replyExample.good + "\"\n" +
      "}\n\n" +
      "tier 规则：score >= 70 为 \"high\"，40-69 为 \"medium\"，< 40 为 \"low\"\n" +
      "intent 必须是以下之一（根据 tier 语气说明选择最匹配的）：\"" + Object.keys(an.tiers).join("\" / \"") + "\"\n" +
      "请直接输出 JSON，不要其他文本。";
  },
};

module.exports = aiAnalyzer;
