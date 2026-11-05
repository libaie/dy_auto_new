// device/core/ai-analyzer.js
var config = global.__config || require("../config");
var apiClient = require("./api-client");
var decisionClient = require("./decision-client");
var promptsConfig = require("./prompts-config");
var logger = require("../utils/logger");
var taskCancellation = require("./task-cancellation");

var TAG = "AI";

/**
 * 设备端 AI 分析模块
 * 通过服务端代理调用 AI，设备端不持有 API Key
 * 行业相关提示词统一在 prompts-config.js 管理
 */
var aiAnalyzer = {
  SCORE_THRESHOLD: 40,

  isDecisionEnabled: function () {
    return decisionClient.isEnabled();
  },

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
    if (taskCancellation.isCancelled()) return null;
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

      if (taskCancellation.isCancelled()) return null;
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

    if (this.isDecisionEnabled()) {
      try {
        return this._analyzeDecisionComment(params);
      } catch (e) {
        logger.warn(TAG, "决策分析配置或结果不可用，跳过当前评论");
        return null;
      }
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
   * 构建原生决策问题和当前模板上下文
   */
  _buildDecisionRequest: function (params) {
    var p = promptsConfig.get();
    var analysis = p.analysis;
    if (!analysis || !analysis.tiers) return null;
    var intentCriteria = {};
    var intentKeys = Object.keys(analysis.tiers);
    for (var i = 0; i < intentKeys.length; i++) {
      var key = intentKeys[i];
      intentCriteria[key] = analysis.tiers[key];
    }
    return {
      state: {
        industry: promptsConfig.industry,
        domain: p.domain,
        comment: { search_keyword: params.searchKeyword || "", nickname: params.nickname || "", text: params.commentText },
        analysis: {
          intents: analysis.intents,
          sentiments: analysis.sentiments,
          scoringRules: analysis.scoringRules,
          tiers: analysis.tiers
        },
        semanticGuide: p.semanticGuide
      },
      // 问题 ID 不会交给模型，每道题都说明输入、判断目标和依据。
      questions: {
        lead_score: {
          type: "score",
          instructions: "请评估 state.comment.text 中评论者对 state.domain 领域的真实需求强度。结合搜索词、state.semanticGuide 和 state.analysis.scoringRules 的现有 0 到 100 分规则，将总分映射到下面按低到高排列的十个等级。无意义、机器人水军或同行引流评论应为最低等级。只使用评论表达的需求，不推测人口属性。",
          criteria: [
            "0 分：无真实需求、无意义、机器人水军或同行引流",
            "约 11 分：几乎没有相关需求信号",
            "约 22 分：弱相关的泛泛表达，没有明确问题",
            "约 33 分：略有兴趣但不足以确认真实需求",
            "约 44 分：可确认的基础咨询或需求",
            "约 56 分：明确需求，并提供一定相关信息",
            "约 67 分：明确且较强的咨询、比较或购买需求",
            "约 78 分：具体需求强烈，有多项高价值信号",
            "约 89 分：强烈且急迫的具体需求或购买意向",
            "100 分：现有评分规则下最高强度的真实需求"
          ]
        },
        intent: {
          type: "choice",
          instructions: "请根据 state.comment.text 的原意，结合搜索词、state.domain、state.analysis.intents 和 state.semanticGuide 判断评论意图。从以下当前模板提供的意图候选中选择最匹配的一项；候选描述包含该意图适用的回复语气，判断时关注评论本身的需求。",
          criteria: intentCriteria
        },
        sentiment: {
          type: "choice",
          instructions: "请判断 state.comment.text 表达的情感倾向，结合 state.analysis.sentiments 理解语气，不因评论者提出问题就假定其情感正面或负面。",
          criteria: { positive: "正向、认可、满意或积极", negative: "负向、不满、痛苦或焦虑", neutral: "中性询问或客观描述" }
        },
        focus: {
          type: "choice",
          instructions: "请判断 state.comment.text 对 state.domain 领域最主要的关注点。结合搜索词和实际评论表达，从价格、质量或效果、地域和其他中选择一项，不推测评论者消费能力。",
          criteria: { price: "价格、费用或优惠", quality: "质量、效果、体验或解决问题的方法", location: "地域、地址、目的地或距离", other: "其他关注点或没有明确关注点" }
        },
        urgency: {
          type: "score",
          instructions: "请判断 state.comment.text 明确表达的需求紧迫程度，依据 state.domain 和评论内容，按以下从 1 到 10 的顺序选择程度。寻求解决方案、描述明显困扰或语气急切痛苦时通常至少为 7；没有证据时不虚构紧迫性。",
          criteria: ["1：没有需求或紧迫性", "2：随意提及", "3：一般兴趣", "4：希望了解", "5：有需求但不着急", "6：希望近期解决", "7：主动寻求方案或明显困扰", "8：较急切，需要帮助", "9：十分急切或明显痛苦", "10：表达最高程度的紧迫需求"]
        },
        specific_condition: {
          type: "noul",
          instructions: "请判断 state.comment.text 是否明确提及与 state.domain 相关的具体需求、问题或条件。依据评论原文和 state.semanticGuide；泛泛赞同、表情或无具体内容不算，不能从昵称推断。",
          criteria: { "true": "评论明确描述了行业相关的具体需求、问题或条件", "false": "评论没有明确描述行业相关的具体需求、问题或条件" }
        },
        is_bot: {
          type: "noul",
          instructions: "请判断 state.comment.text 是否有明确的机器人、水军或批量垃圾评论特征。仅依据评论文本的重复广告、无关灌水等实际证据；短句或一般提问本身不说明是机器人。",
          criteria: { "true": "有明确机器人、水军或批量垃圾评论特征", "false": "没有明确机器人、水军或批量垃圾评论特征" }
        },
        is_competitor: {
          type: "noul",
          instructions: "请判断 state.comment.text 是否明确表现为 state.domain 领域的同行或竞争商家在引流、招揽生意。依据评论实际文字；用户咨询产品或比较商家本身不代表是同行。",
          criteria: { "true": "明确是同行或竞争商家宣传引流", "false": "没有明确的同行或竞争商家宣传引流证据" }
        }
      }
    };
  },

  _analyzeDecisionComment: function (params) {
    var request = this._buildDecisionRequest(params);
    if (!request) return null;
    var response = decisionClient.decide(request.state, request.questions);
    if (!response) return null;
    var answers = response.answers;
    var score = Math.round(answers.lead_score.score / (request.questions.lead_score.criteria.length - 1) * 100);
    var result = {
      score: score,
      tier: score >= 70 ? "high" : (score >= this.SCORE_THRESHOLD ? "medium" : "low"),
      dimensions: {
        intent: answers.intent.choice,
        sentiment: answers.sentiment.choice,
        focus: answers.focus.choice,
        profile: { role: "unknown", spending: "mid" },
        lead_quality: {
          urgency: Math.round(answers.urgency.score) + 1,
          specific_condition: answers.specific_condition.noul > 0.5,
          is_bot: answers.is_bot.noul > 0.5,
          is_competitor: answers.is_competitor.noul > 0.5
        }
      },
      reply: ""
    };
    var quality = result.dimensions.lead_quality;
    if (params.generateReply === false || score < this.SCORE_THRESHOLD || quality.is_bot || quality.is_competitor) return result;
    var content = this._callAI(this._buildDecisionReplyPrompt(params, result), 256, 0.3);
    if (!content) return null;
    // 只取文案，即使生成模型附带 score 等字段也不能覆盖已确认的决策。
    var reply = content.trim();
    var jsonMatch = reply.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        var generated = JSON.parse(jsonMatch[0]);
        if (typeof generated.reply !== "string") return null;
        reply = generated.reply;
      } catch (e) { return null; }
    }
    reply = reply.replace(/^["“]|["”]$/g, "").trim();
    if (!reply) return null;
    result.reply = reply;
    return result;
  },

  _buildDecisionReplyPrompt: function (params, decision) {
    var p = promptsConfig.get();
    var an = p.analysis;
    var identity = p.identity;
    var tone = an.tiers[decision.dimensions.intent] || "自然接话";
    return "请为以下评论撰写一条中文回复。结构化需求判断已经完成，请只生成回复正文。\n\n" +
      "## 身份设定\n- 你是" + identity.role + "\n- " + identity.constraints.join("\n- ") + "\n" +
      "- 严禁自我代入，不要用我都是、我自己、我家等第一人称经验分享。\n" +
      "- 使用建议或指南风格，使用可以试试、建议等客观句式。\n\n" +
      "## 绝对禁用词（任何情况下不得出现）\n" + p.disabledWords + "\n\n" +
      "## 已确认的需求判断\n" + JSON.stringify(decision) + "\n\n" +
      "## 回复生成规则\n- " + an.replyRules.join("\n- ") + "\n" +
      "- 回复正文不要加回复 @昵称前缀，系统会自动显示。\n" +
      "- 当前意图适用语气：" + tone + "\n" +
      "- 输出示例：正确：" + an.replyExample.good + "；错误：" + an.replyExample.bad + "\n\n" +
      "## 输入\n- 搜索词：" + (params.searchKeyword || "") + "\n- 对方昵称：" + (params.nickname || "") +
      "\n- 对方的评论：" + params.commentText + "\n\n请直接输出回复正文。";
  },

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
  checkRelevance: function (contentText, domain, options) {
    var useDecision = this.isDecisionEnabled();
    if (!contentText || contentText.length < 2) return !useDecision;

    var localResult = options && options.skipLocalFilter ? null : this._localRelevanceCheck(contentText);
    if (localResult !== null) {
      logger.info(TAG, "本地预过滤: " + (localResult ? "相关" : "不相关") + " — " + contentText.substring(0, 30));
      return localResult;
    }

    domain = domain || promptsConfig.get().domain;

    if (useDecision) {
      var state = { content: contentText.substring(0, 300), domain: domain };
      if (options && options.keywords) state.keywords = options.keywords;
      var response = decisionClient.decide(state, {
        related: {
          type: "noul",
          instructions: "请判断 state.content 中的视频内容是否与 state.domain 所描述的目标领域相关。如 state.keywords 存在，请以这些目标关键词及其语义作为相关性依据。只根据内容实际表达判断，信息不足时不能确认相关。",
          criteria: { "true": "内容与目标领域或目标关键词语义明确相关", "false": "内容与目标领域或目标关键词语义无关，或信息不足以确认相关" }
        }
      });
      return !!(response && response.answers.related.noul > 0.5 &&
        response.answers.related.noul >= decisionClient.getSettings().min_probability);
    }

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
    // dmOpener.identity 兼容两种格式: {role, constraints} 对象 或 字符串列表
    var dmRole, dmConstraints;
    if (dmId instanceof Array) {
      dmRole = dmId[0] || "";
      dmConstraints = dmId.slice(1);
    } else {
      dmRole = dmId.role || "";
      dmConstraints = dmId.constraints || [];
    }

    var prompt = dm.context + "\n\n" +
      "## 绝对禁用词（任何情况下不得出现）\n" + dw + "\n\n" +
      "## 身份设定\n" +
      "- 你是" + dmRole + "\n" +
      "- " + dmConstraints.join("\n- ") + "\n" +
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
    var dmRole2 = dmId instanceof Array ? (dmId[0] || "") : (dmId.role || "");

    var prompt = "你是" + dmRole2 + "，与对方私信已有互动。当前阶段：" + cfg.name + "。\n\n" +
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
