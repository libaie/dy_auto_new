// Jev 原生结构化决策。只调用已配对服务端，设备不持有上游密钥或地址。
var config = global.__config || require("../config");
var apiClient = require("./api-client");
var logger = require("../utils/logger");
var TAG = "Decision";
var REQUEST_TIMEOUT = 25000;
var own = Object.prototype.hasOwnProperty;

function isObject(value) {
  return value !== null && typeof value === "object" &&
    Object.prototype.toString.call(value) === "[object Object]";
}

function isProbability(value) {
  return typeof value === "number" && isFinite(value) && value >= 0 && value <= 1;
}

function isDescription(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function hasKeys(value, keys) {
  if (!isObject(value) || Object.keys(value).length !== keys.length) return false;
  for (var i = 0; i < keys.length; i++) {
    if (!own.call(value, keys[i])) return false;
  }
  return true;
}

function validDistribution(probabilities, keys) {
  if (!hasKeys(probabilities, keys)) return false;
  var total = 0;
  for (var i = 0; i < keys.length; i++) {
    var probability = probabilities[keys[i]];
    if (!isProbability(probability)) return false;
    total += probability;
  }
  // 允许上游序列化浮点数带来的舍入误差。
  return Math.abs(total - 1) <= 0.01;
}

function criterionKeys(question) {
  if (!isObject(question) || !isDescription(question.instructions)) return null;
  var criteria = question.criteria;
  var keys = [];
  var i;
  if (question.type === "score") {
    if (!Array.isArray(criteria) || criteria.length < 2 || criteria.length > 10) return null;
    for (i = 0; i < criteria.length; i++) {
      if (!isDescription(criteria[i])) return null;
      keys.push(String(i));
    }
  } else if (question.type === "choice") {
    if (!isObject(criteria)) return null;
    keys = Object.keys(criteria);
    if (keys.length < 1 || keys.length > 255) return null;
    for (i = 0; i < keys.length; i++) {
      if (!isDescription(keys[i]) || !isDescription(criteria[keys[i]])) return null;
    }
  } else if (question.type === "noul") {
    if (criteria !== undefined && (!hasKeys(criteria, ["true", "false"]) ||
      !isDescription(criteria["true"]) || !isDescription(criteria["false"]))) return null;
  } else {
    return null;
  }
  return keys;
}

function validAnswer(answer, question, keys, settings) {
  if (!isObject(answer) || answer.type !== question.type) return false;
  if (question.type === "noul") {
    return isProbability(answer.noul) && answer.noul !== 0.5 &&
      Math.max(answer.noul, 1 - answer.noul) >= settings.min_probability;
  }
  if (!isProbability(answer.confidence) || !validDistribution(answer.probabilities, keys)) return false;
  if (question.type === "choice") {
    return typeof answer.choice === "string" && own.call(question.criteria, answer.choice) &&
      answer.probabilities[answer.choice] >= settings.min_probability;
  }
  if (typeof answer.score !== "number" || !isFinite(answer.score) ||
    answer.score < 0 || answer.score > keys.length - 1 || answer.confidence < settings.min_confidence ||
    !hasKeys(answer.legend, keys)) return false;
  for (var i = 0; i < keys.length; i++) {
    if (answer.legend[keys[i]] !== question.criteria[i]) return false;
  }
  return true;
}

var decisionClient = {
  isEnabled: function () {
    return !!(config.decision && config.decision.enabled === true);
  },

  getSettings: function () {
    var decision = config.decision || {};
    return {
      enabled: decision.enabled === true,
      model: isDescription(decision.model) ? decision.model : "typesafe-ai/jev",
      min_confidence: isProbability(decision.min_confidence) ? decision.min_confidence : 0.5,
      min_probability: isProbability(decision.min_probability) ? decision.min_probability : 0.75
    };
  },

  decide: function (state, questions) {
    if (!this.isEnabled() || !config.serverUrl || !config.deviceSecret) return null;
    if (!isObject(state) || !isObject(questions)) return null;
    var ids = Object.keys(questions);
    if (ids.length === 0) return null;
    var keysById = {};
    var i;
    for (i = 0; i < ids.length; i++) {
      var keys = criterionKeys(questions[ids[i]]);
      if (keys === null) return null;
      keysById[ids[i]] = keys;
    }
    var settings = this.getSettings();
    var started = Date.now();
    try {
      var options = {
        headers: { "X-Device-Secret": config.deviceSecret },
        timeout: REQUEST_TIMEOUT
      };
      var proxyOptions = apiClient._getProxyOptions();
      for (var name in proxyOptions) {
        if (own.call(proxyOptions, name)) options[name] = proxyOptions[name];
      }
      // apiClient.post 会自动重试。决策采用一次请求，避免重复分类与超过执行预算。
      var response = http.postJson(config.serverUrl + "/api/device/decision-proxy", {
        state: state,
        questions: questions
      }, options);
      if (response && response.statusCode === 401 && apiClient._onAuthFailure) {
        apiClient._onAuthFailure();
      }
      if (!response || response.statusCode !== 200 || Date.now() - started > REQUEST_TIMEOUT) {
        logger.warn(TAG, "决策请求未成功，跳过当前内容");
        return null;
      }
      var result = JSON.parse(apiClient._readBody(response));
      if (Date.now() - started > REQUEST_TIMEOUT || !isObject(result) || !isDescription(result.model) ||
        !hasKeys(result.answers, ids)) return null;
      for (i = 0; i < ids.length; i++) {
        var id = ids[i];
        if (!validAnswer(result.answers[id], questions[id], keysById[id], settings)) {
          logger.warn(TAG, "决策结果不完整或不确定，跳过当前内容");
          return null;
        }
      }
      return result;
    } catch (e) {
      // 错误文本可能包含上游响应或连接信息，日志不记录正文。
      logger.warn(TAG, "决策请求或解析失败，跳过当前内容");
      return null;
    }
  }
};

module.exports = decisionClient;
