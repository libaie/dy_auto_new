var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "SELECTOR";

var selectorLoader = {
  _cache: {},       // action_name -> selector config
  _version: 0,      // 本地缓存版本号
  _initialized: false,

  /**
   * 初始化 — 从后端拉取全量选择器
   */
  init: function () {
    logger.info(TAG, "Loading selectors from server...");
    var response = apiClient.fetchSelectors(0);
    if (response && response.selectors) {
      this._applySelectors(response.selectors);
      this._version = response.version;
      this._initialized = true;
      logger.info(TAG, "Loaded " + Object.keys(this._cache).length + " selectors, version=" + this._version);
    } else {
      logger.warn(TAG, "Failed to load selectors, using empty cache");
      this._initialized = true;
    }
  },

  /**
   * 检查并增量更新选择器
   * @param {number} serverVersion - 服务端版本号
   */
  checkAndUpdate: function (serverVersion) {
    if (serverVersion > this._version) {
      logger.info(TAG, "Selectors outdated (local=" + this._version + ", server=" + serverVersion + "), updating...");
      var response = apiClient.fetchSelectors(this._version);
      if (response && response.changed && response.selectors) {
        this._applySelectors(response.selectors);
        this._version = response.version;
        logger.info(TAG, "Selectors updated to version " + this._version);
      }
    }
  },

  /**
   * 获取指定操作的选择器配置
   * @param {string} actionName - 操作名称 (如 "like_video")
   * @returns {Object|null} { strategies: [...] }
   */
  get: function (actionName) {
    return this._cache[actionName] || null;
  },

  /**
   * 应用选择器配置到缓存
   * @param {Array} selectors
   */
  _applySelectors: function (selectors) {
    for (var i = 0; i < selectors.length; i++) {
      var s = selectors[i];
      this._cache[s.action_name] = s;
    }
  },

  /**
   * 获取当前版本号
   */
  getVersion: function () {
    return this._version;
  },
};

module.exports = selectorLoader;
