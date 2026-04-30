// device/core/ai-analyzer.js
var config = global.__config || require("../config");
var logger = require("../utils/logger");

var TAG = "AI";

/**
 * 设备端 AI 分析模块
 * 五维度打分模型：意图识别 + 情感倾向 + 关注实体 + 用户画像 + 线索质量
 */
var aiAnalyzer = {
  // 阈值：达到此分数才触发回复
  SCORE_THRESHOLD: 60,

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

    // 调用 AI 进行五维度分析 + 生成回复
    var result = this._analyzeAndReply(searchKeyword, nickname, commentText);
    if (!result) {
      logger.warn(TAG, "AI analysis failed");
      return null;
    }

    return result;
  },

  /**
   * 调用 AI 进行五维度分析并生成回复
   * @param {string} searchKeyword
   * @param {string} nickname
   * @param {string} commentText
   * @returns {Object|null} { score, tier, dimensions, reply }
   */
  _analyzeAndReply: function (searchKeyword, nickname, commentText) {
    var aiConfig = config.ai;
    if (!aiConfig.apiKey) {
      logger.error(TAG, "AI API key not configured");
      return null;
    }

    var prompt = this._buildAnalysisPrompt(searchKeyword, nickname, commentText);

    try {
      var response = http.post(aiConfig.apiUrl, {
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + aiConfig.apiKey,
        },
        body: JSON.stringify({
          model: aiConfig.model,
          max_tokens: 512,
          temperature: 0.3, // 低温度保证分析稳定性
          messages: [
            { role: "user", content: prompt },
          ],
        }),
        timeout: 30000,
      });

      if (response.statusCode !== 200) {
        logger.error(TAG, "AI API error: " + response.statusCode + " - " + response.body);
        return null;
      }

      var result = JSON.parse(response.body);
      var content = result.choices[0].message.content.trim();

      // 解析 JSON 响应
      return this._parseAnalysisResponse(content);
    } catch (e) {
      logger.error(TAG, "AI API call failed: " + e.message);
      return null;
    }
  },

  /**
   * 解析 AI 分析响应
   * @param {string} content - AI 返回的 JSON 字符串
   * @returns {Object|null}
   */
  _parseAnalysisResponse: function (content) {
    try {
      // 提取 JSON（AI 可能会添加额外文本）
      var jsonMatch = content.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        logger.error(TAG, "No JSON found in AI response");
        return null;
      }

      var data = JSON.parse(jsonMatch[0]);

      // 验证必要字段
      if (typeof data.score !== "number" || !data.reply) {
        logger.error(TAG, "Invalid AI response structure");
        return null;
      }

      // 清理回复（去掉引号等）
      data.reply = data.reply.replace(/^["'「]|["'」]$/g, "");

      return data;
    } catch (e) {
      logger.error(TAG, "Parse AI response failed: " + e.message);
      return null;
    }
  },

  /**
   * 构建五维度分析提示词
   */
  _buildAnalysisPrompt: function (searchKeyword, nickname, commentText) {
    return '你是一个抖音评论分析专家，需要对评论进行五维度分析并生成回复。\n\n' +
      '## 任务\n' +
      '分析以下评论，输出 JSON 格式的分析结果和回复。\n\n' +
      '## 五维度分析模型\n\n' +
      '### 1. 意图识别 (intent) - 核心转化指标\n' +
      '判断用户发这条评论的真实目的：\n' +
      '- buy_intent (求购/交易意图): 高价值线索。"怎么买？"、"多少钱？"、"求链接"、"小黄车里没有啊"\n' +
      '- consult_intent (求知/咨询意图): 潜在线索。"这个怎么用？"、"敏感肌可以用吗？"\n' +
      '- compare_intent (对比/摇摆意图): 极佳切入点。"这个和XX比哪个好？"、"有没有平替？"\n' +
      '- meaningless (无意义/闲聊): 需过滤。"哈哈哈"、"第一"、"打卡"或纯表情\n\n' +
      '### 2. 情感倾向 (sentiment) - 切入策略指标\n' +
      '- positive (正向): 赞赏、喜欢、期待\n' +
      '- negative (负向): 抱怨、吐槽、踩坑 - 极具截流价值的痛点\n' +
      '- neutral (中立): 客观陈述、疑问\n\n' +
      '### 3. 关注实体 (focus) - 产品痛点指标\n' +
      '- price (价格敏感): "贵"、"便宜"、"折扣"、"运费"\n' +
      '- quality (质量/功能): "材质"、"续航"、"掉色"、"售后"\n' +
      '- location (地域/本地): 具体城市、商圈\n' +
      '- other (其他)\n\n' +
      '### 4. 用户画像 (profile) - 客户资质指标\n' +
      '- role (社会角色): 宝妈、学生、职场人等\n' +
      '- spending (消费能力): low/mid/high\n\n' +
      '### 5. 线索质量 (lead_quality) - 清洗与排序\n' +
      '- urgency (紧急度): 1-10分\n' +
      '- is_bot (是否水军/机器人): true/false\n' +
      '- is_competitor (是否同行): true/false\n\n' +
      '## 评分规则\n' +
      '总分 = intent分 + sentiment分 + focus分 + profile分 + urgency分\n' +
      '- buy_intent: 50分\n' +
      '- compare_intent: 40分\n' +
      '- consult_intent: 30分\n' +
      '- meaningless: 0分\n' +
      '- negative情感: +20分\n' +
      '- positive情感: +10分\n' +
      '- price敏感: +10分\n' +
      '- urgency > 7: +10分\n' +
      '- is_bot/is_competitor: 直接0分\n\n' +
      '## 回复生成规则\n' +
      '- 搜索词是健康/养生领域时，使用健康科普风格\n' +
      '- 严禁禁用词：治愈/根治/治好/疗效保证/替代药物/停药/医生/专家/保证有效/百分百/神药\n' +
      '- 不做诊断，不保证疗效，讨论日常饮食生活习惯\n' +
      '- 严禁自我代入：不要用"我都是…"、"我自己…"\n' +
      '- 使用建议风格："可以试试"、"建议"、"若想…"\n' +
      '- 单条不超过30字，严禁以"同感"、"我也是"、"确实"开头\n' +
      '- 根据意图和情感调整话术：\n' +
      '  - buy_intent: 可分享使用经验或提出建议角度\n' +
      '  - consult_intent: 从饮食/运动/习惯角度切入\n' +
      '  - negative: 理解痛点，提供替代方案\n' +
      '  - compare_intent: 客观对比，突出优势\n\n' +
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
      '    "focus": "price",\n' +
      '    "profile": { "role": "unknown", "spending": "mid" },\n' +
      '    "lead_quality": { "urgency": 8, "is_bot": false, "is_competitor": false }\n' +
      '  },\n' +
      '  "reply": "可以试试饭前喝点稀释的苹果水，对胃比较温和"\n' +
      '}\n\n' +
      'tier 规则：score >= 70 为 "high"，40-69 为 "medium"，< 40 为 "low"\n' +
      '请直接输出 JSON，不要其他文本。';
  },
};

module.exports = aiAnalyzer;
