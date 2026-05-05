// device/core/ai-analyzer.js
var config = global.__config || require("../config");
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "AI";

/**
 * 设备端 AI 分析模块
 * 通过服务端代理调用 AI，设备端不持有 API Key
 */
var aiAnalyzer = {
  // 阈值：达到此分数才触发回复
  SCORE_THRESHOLD: 55,

  /**
   * 调用服务端 AI 代理
   * @param {string} prompt - 提示词
   * @param {number} maxTokens
   * @param {number} temperature
   * @returns {string|null} AI 返回的文本，失败返回 null
   */
  _callAI: function (prompt, maxTokens, temperature) {
    if (!config.serverUrl || !config.deviceSecret) {
      logger.error(TAG, "设备未配对，无法调用 AI");
      return null;
    }

    try {
      var result = apiClient.post("/api/device/ai-proxy", {
        prompt: prompt,
        max_tokens: maxTokens || 512,
        temperature: temperature != null ? temperature : 0.7,
      });

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
   * @param {Object} params
   *   - searchKeyword: string (搜索关键词)
   *   - nickname: string (评论者昵称)
   *   - commentText: string (评论内容)
   * @returns {Object|null} { score, tier, dimensions, reply }
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
    var content = this._callAI(prompt, 512, 0.3);
    if (!content) {
      logger.warn(TAG, "AI analysis failed");
      return null;
    }

    return this._parseAnalysisResponse(content);
  },

  /**
   * 解析 AI 分析响应
   * @param {string} content - AI 返回的 JSON 字符串
   * @returns {Object|null}
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
   * 本地关键词预过滤 — 快速判断是否明显不相关，避免不必要的 AI 调用
   * @param {string} text
   * @returns {boolean|null} true=明显相关, false=明显不相关, null=需要 AI 判断
   */
  _localRelevanceCheck: function (text) {
    if (!text) return null;
    var t = text.toLowerCase();

    // 明确不相关的领域关键词 — 命中即跳过
    var excludePatterns = [
      "游戏", "电竞", "王者荣耀", "原神", "吃鸡", "英雄联盟",
      "汽车", "改装", "二手车", "驾照", "科目",
      "编程", "python", "java", "代码", "程序员",
      "美妆", "口红", "粉底", "眼影", "护肤",
      "穿搭", "潮牌", "aj", "球鞋", "aj1",
      "装修", "硬装", "软装", "瓷砖", "地板",
      "股票", "基金", "a股", "k线", "涨停",
      "追星", "饭圈", "爱豆", "应援",
    ];
    for (var i = 0; i < excludePatterns.length; i++) {
      if (t.indexOf(excludePatterns[i]) !== -1) return false;
    }

    // 大健康相关关键词 — 命中即通过
    var includePatterns = [
      "养生", "保健", "中医", "食疗", "营养", "运动", "健身",
      "心理", "睡眠", "失眠", "减肥", "瘦身", "排毒",
      "气血", "经络", "穴位", "艾灸", "拔罐", "推拿",
      "食补", "药膳", "茶饮", "枸杞", "红枣",
      "瑜伽", "太极", "跑步", "拉伸", "有氧",
      "血压", "血糖", "血脂", "胆固醇", "尿酸",
      "肠胃", "便秘", "湿气", "上火", "感冒",
      "免疫力", "抗衰老", "胶原蛋白", "维c", "维生素",
      "慢病", "亚健康", "调理", "体质", "寒凉",
      "大健康", "健康管理", "体重管理",
    ];
    for (var j = 0; j < includePatterns.length; j++) {
      if (t.indexOf(includePatterns[j]) !== -1) return true;
    }

    return null; // 无法本地判断，交给 AI
  },

  /**
   * 检查当前内容是否与大健康领域相关
   * @param {string} contentText - 从屏幕提取的文本
   * @param {string} [domain] - 目标领域描述
   * @returns {boolean} true=相关，false=不相关或判断失败
   */
  checkHealthRelevance: function (contentText, domain) {
    if (!contentText || contentText.length < 2) return true;

    // 本地预过滤 — 快速判断，避免 AI 调用延迟
    var localResult = this._localRelevanceCheck(contentText);
    if (localResult !== null) {
      logger.info(TAG, "本地预过滤: " + (localResult ? "相关" : "不相关") + " — " + contentText.substring(0, 30));
      return localResult;
    }

    domain = domain || "大健康（养生、保健、中医、食疗、营养、运动健身、心理健康、慢病管理、亚健康调理）";

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

  /**
   * 根据视频内容生成评论
   * @param {string} videoText - 从屏幕提取的视频文本
   * @returns {string|null} 生成的评论内容，失败返回 null
   */
  generateVideoComment: function (videoText) {
    if (!videoText || videoText.length < 2) {
      logger.warn(TAG, "视频文本太短，无法生成评论");
      return null;
    }

    var prompt = "你是一个抖音用户，正在浏览健康/养生类短视频。请根据视频内容写一条自然、真实的评论。\n\n" +
      "## 要求\n" +
      "- 像真人刷抖音时随手写的评论，不要太正式\n" +
      "- 15-30字，口语化\n" +
      "- 结合视频具体内容（标题、话题、描述）\n" +
      "- 可以用语气词、表情符号\n" +
      "- 严禁禁用词：治愈/根治/治好/疗效保证/替代药物/停药/医生/专家/保证有效/百分百/神药\n" +
      "- 严禁营销感：不要带链接、不要引导加微信\n" +
      "- 不要以「同感」「我也是」「确实」开头\n\n" +
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
   * 根据视频内容生成私信
   * @param {string} videoText - 从屏幕提取的视频文本
   * @returns {string|null} 生成的私信内容，失败返回 null
   */
  generateVideoDM: function (videoText) {
    if (!videoText || videoText.length < 2) {
      logger.warn(TAG, "视频文本太短，无法生成私信");
      return null;
    }

    var prompt = "你是一个抖音用户，看到一条健康/养生相关视频后想和博主私信交流。请根据视频内容写一条友好的私信。\n\n" +
      "## 要求\n" +
      "- 像普通人私信，自然亲切\n" +
      "- 20-40字\n" +
      "- 结合视频具体内容，表明你是看了他的视频才来聊的\n" +
      "- 可以表达共鸣、请教、分享经验\n" +
      "- 严禁禁用词：治愈/根治/治好/疗效保证/替代药物/停药/医生/专家/保证有效/百分百/神药\n" +
      "- 严禁营销感：不要带链接、不要推销\n\n" +
      "## 视频内容\n" + videoText.substring(0, 500) + "\n\n" +
      "只输出私信文本，不要引号、不要其他解释。";

    var text = this._callAI(prompt, 200, 0.8);
    if (text) {
      text = text.replace(/^["'「]|["'」]$/g, "");
      logger.info(TAG, "AI 生成私信: '" + text.substring(0, 30) + "'");
    }
    return text;
  },

  /**
   * 构建五维度分析提示词
   */
  _buildAnalysisPrompt: function (searchKeyword, nickname, commentText) {
    return '你是一个关心家人健康的普通抖音用户，在视频评论区回复一位对【' + searchKeyword + '】话题感兴趣的网友。\n\n' +
      '## 绝对禁用词（任何情况下不得出现）\n' +
      '治愈 / 根治 / 治好 / 疗效保证 / 包好 / 替代药物 / 停药 / 不用吃药 /\n' +
      '医生 / 我是医生 / 专家 / 我是专家 / 保证有效 / 百分百 / 100% / 神药\n\n' +
      '## 身份设定\n' +
      '- 你是「健康生活指南」视角，像一个靠谱的健康科普评论者。\n' +
      '- 不是医生，不做诊断，不保证疗效。\n' +
      '- 讨论的是日常饮食、生活习惯，不是治疗方案。\n' +
      '- **严禁自我代入**：不要用"我都是…"、"我自己…"、"我家…"等第一人称经验分享。\n' +
      '- 使用建议/指南风格：用"可以试试"、"建议"、"若想…"等客观建议句式。\n\n' +
      '## 这一条是公开评论回复，目标\n' +
      '- 自然地接住对方的评论，给出一条实用的小建议，让对方觉得有收获。\n' +
      '- 引起对方兴趣，为后续私聊做铺垫，但不能在评论区留联系方式。\n' +
      '- 回复要像真实用户的评论，不像营销话术。\n\n' +
      '## 风格\n' +
      '- 像健康科普博主评论区互动一样自然，避免"亲/亲亲/宝"等营销口吻。\n' +
      '- 中老年用户居多，不用年轻化网络梗。\n' +
      '- 单条不超过 30 字，评论区要简短。\n' +
      '- **严禁以"同感"、"我也是"、"确实"开头**，这太千篇一律了。每条回复的开头句式必须不同。\n' +
      '- 开头可以多样化：直接回应对方问题、给出建议角度、提出一个新角度、用反问句引发思考等。\n\n' +
      '## 输出示例（参考风格，不要照抄）\n' +
      '- ✅ "可以试试饭前喝点稀释的苹果水，对胃比较温和"\n' +
      '- ✅ "若血糖偏高，餐后散步 15 分钟比坐着好很多"\n' +
      '- ❌ "我都是饭前喝点苹果兑水，感觉好多了"（禁止第一人称自我代入）\n\n' +
      '## 五维度分析\n' +
      '### 1. 意图识别 (intent)\n' +
      '- buy_intent (求购/交易): "怎么买？"、"多少钱？"、"求链接"\n' +
      '- health_consult (健康咨询): "这个能吃吗？"、"血糖高怎么办？"\n' +
      '- patient_self (自述患者): "我也是糖尿病"、"我妈血糖也高"\n' +
      '- meaningless (无意义): "哈哈哈"、"第一"、纯表情\n\n' +
      '### 2. 情感倾向 (sentiment)\n' +
      '- positive / negative / neutral\n\n' +
      '### 3. 关注点 (focus)\n' +
      '- diet (饮食) / exercise (运动) / symptom (症状) / price (价格) / other\n\n' +
      '### 4. 线索质量 (lead_quality)\n' +
      '- urgency: 1-10\n' +
      '- is_bot: 是否水军\n' +
      '- is_competitor: 是否同行\n\n' +
      '## 评分规则\n' +
      '- buy_intent: 50分\n' +
      '- health_consult: 40分\n' +
      '- patient_self: 35分\n' +
      '- meaningless: 0分\n' +
      '- negative情感: +15分\n' +
      '- urgency > 7: +10分\n' +
      '- is_bot / is_competitor: 直接 0 分\n\n' +
      '根据 tier 选择语气（但开头不要固定套路）：\n' +
      '- strong_buy：对方询价/求购，可分享自己使用经验或提出建议角度。\n' +
      '- health_consult：对方在做健康咨询，可从饮食/运动/习惯角度切入。\n' +
      '- patient_self：对方自述患者，可从家人经历或自身感受切入，但不要每次都以"我也是"开头。\n' +
      '- other：自然接话即可，不要机械地以"同感"切入。\n\n' +
      '## 输入\n' +
      '- 搜索词：' + searchKeyword + '\n' +
      '- 对方昵称：' + nickname + '\n' +
      '- 对方的评论：' + commentText + '\n\n' +
      '## 输出格式（严格 JSON）\n' +
      '{\n' +
      '  "score": 75,\n' +
      '  "tier": "high",\n' +
      '  "dimensions": {\n' +
      '    "intent": "buy_intent",\n' +
      '    "sentiment": "positive",\n' +
      '    "focus": "diet",\n' +
      '    "lead_quality": { "urgency": 8, "is_bot": false, "is_competitor": false }\n' +
      '  },\n' +
      '  "reply": "可以试试饭前喝点稀释的苹果水，对胃比较温和"\n' +
      '}\n\n' +
      'tier 规则：score >= 70 为 "high"，40-69 为 "medium"，< 40 为 "low"\n' +
      '请直接输出 JSON，不要其他文本。';
  },
};

module.exports = aiAnalyzer;
