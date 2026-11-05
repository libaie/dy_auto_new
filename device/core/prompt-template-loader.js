// device/core/prompt-template-loader.js
// 提示词模板同步加载器 — 照 selector-loader.js 模式
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "模板";

var promptTemplateLoader = global.__promptTemplateLoader || {

  _cache: {},       // id -> template object { id, name, industry, content }
  _version: 0,
  _initialized: false,
  _defaultId: null,  // 默认模板 ID（首个加载的模板）

  /**
   * 初始化 — 从服务端拉取全量模板
   */
  init: function () {
    var maxRetries = 3;
    for (var attempt = 1; attempt <= maxRetries; attempt++) {
      logger.info(TAG, "从服务端加载提示词模板 (尝试 " + attempt + "/" + maxRetries + ")...");
      try {
        var response = apiClient.fetchPromptTemplates(0);
        if (typeof response === "string") {
          try { response = JSON.parse(response); } catch (e) { /* ignore */ }
        }
        if (response && response.templates) {
          this._applyTemplates(response.templates);
          this._version = response.version;
          this._initialized = true;
          logger.info(TAG, "已加载 " + Object.keys(this._cache).length + " 个模板, 版本=" + this._version);
          return;
        }
        logger.warn(TAG, "服务端返回空模板列表 (尝试 " + attempt + ")");
      } catch (e) {
        logger.warn(TAG, "加载模板异常 (尝试 " + attempt + "): " + e.message);
      }
      if (attempt < maxRetries) sleep(2000);
    }
    logger.warn(TAG, "模板加载全部失败，将使用本地默认配置");
    this._initialized = true;
  },

  /**
   * 增量更新
   */
  checkAndUpdate: function (serverVersion) {
    if (serverVersion > this._version) {
      logger.info(TAG, "模板已过期 (本地=" + this._version + ", 服务端=" + serverVersion + "), 更新中...");
      var response = apiClient.fetchPromptTemplates(this._version);
      if (response && response.changed && response.templates) {
        this._applyTemplates(response.templates);
        this._version = response.version;
        logger.info(TAG, "模板已更新至版本 " + this._version);
      }
    }
  },

  /**
   * 获取指定模板
   * @param {string} [id] — 模板 ID，不传则返回默认模板
   * @returns {Object|null} { id, name, industry, content }
   */
  get: function (id) {
    if (id) return Object.prototype.hasOwnProperty.call(this._cache, id) ? this._cache[id] : null;
    // 查找默认模板
    if (this._defaultId && this._cache[this._defaultId]) return this._cache[this._defaultId];
    // 取第一个可用模板
    var keys = Object.keys(this._cache);
    if (keys.length > 0) {
      this._defaultId = keys[0];
      return this._cache[keys[0]];
    }
    return null;
  },

  /**
   * 按行业获取模板列表
   * @param {string} industry — "health" / "travel"
   * @returns {Array}
   */
  listByIndustry: function (industry) {
    var result = [];
    var keys = Object.keys(this._cache);
    for (var i = 0; i < keys.length; i++) {
      var t = this._cache[keys[i]];
      if (t.industry === industry) result.push(t);
    }
    return result;
  },

  _applyTemplates: function (templates) {
    // The service returns a complete snapshot, including removals/disables.
    var nextCache = {};
    var firstId = null;
    for (var i = 0; i < templates.length; i++) {
      var t = templates[i];
      nextCache[t.id] = t;
      if (!firstId) firstId = t.id;
    }
    this._defaultId = this._defaultId && nextCache[this._defaultId] ? this._defaultId : firstId;
    this._cache = nextCache;
    logger.debug(TAG, "已应用模板，当前缓存 " + Object.keys(this._cache).length + " 个");
  },

  getVersion: function () {
    return this._version;
  },
};

global.__promptTemplateLoader = promptTemplateLoader;
module.exports = promptTemplateLoader;
