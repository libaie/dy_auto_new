var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "选择器";

// 使用 global 确保所有 require 路径拿到同一个实例（和 config 一样的模式）
var selectorLoader = global.__selectorLoader || {

  _cache: {},       // action_name -> selector config
  _retriedActions: {},  // action_name -> bool, 每个 action 独立重试
  _version: 0,      // 本地缓存版本号
  _initialized: false,

  /**
   * 初始化 — 从后端拉取全量选择器（带重试）
   */
  init: function () {
    var maxRetries = 3;
    for (var attempt = 1; attempt <= maxRetries; attempt++) {
      logger.info(TAG, "从服务端加载选择器 (尝试 " + attempt + "/" + maxRetries + ")...");
      try {
        var response = apiClient.fetchSelectors(0);
        // 如果返回的是字符串，先解析成对象
        if (typeof response === 'string') {
            try {
                response = JSON.parse(response);
            } catch (parseErr) {
                logger.error(TAG, "JSON解析失败: " + parseErr.message);
            }
        } 
        if (response && response.selectors) {
          this._applySelectors(response.selectors);
          this._version = response.version;
          this._initialized = true;
          logger.info(TAG, "已加载 " + Object.keys(this._cache).length + " 个选择器, 版本=" + this._version);
          this.syncTemplates();
          return;
        }
        logger.warn(TAG, "服务端返回空选择器 (尝试 " + attempt + ")");
      } catch (e) {
        logger.warn(TAG, "加载选择器异常 (尝试 " + attempt + "): " + e.message);
      }
      if (attempt < maxRetries) sleep(2000);
    }
    logger.error(TAG, "选择器加载全部失败，任务可能无法执行");
    this._initialized = true;
  },

  /**
   * 检查并增量更新选择器
   * @param {number} serverVersion - 服务端版本号
   */
  checkAndUpdate: function (serverVersion) {
    if (serverVersion > this._version) {
      logger.info(TAG, "选择器已过期 (本地=" + this._version + ", 服务端=" + serverVersion + "), 更新中...");
      var response = apiClient.fetchSelectors(this._version);
      if (response && response.changed && response.selectors) {
        this._applySelectors(response.selectors);
        this._version = response.version;
        logger.info(TAG, "选择器已更新至版本 " + this._version);
        this.syncTemplates();
      }
    }
  },

  /**
   * 获取指定操作的选择器配置
   * @param {string} actionName - 操作名称 (如 "like_button")
   * @returns {Object|null} { strategies: [...] }
   */
  get: function (actionName) {
    var selector = this._cache[actionName];
    if (selector) return selector;

    // 未找到 — 每个 action 独立重试一次（可能是初始化时网络异常）
    if (this._initialized && !this._retriedActions[actionName]) {
      this._retriedActions[actionName] = true;
      logger.warn(TAG, "选择器 '" + actionName + "' 未找到，尝试重新加载...");
      try {
        var response = apiClient.fetchSelectors(0);
        if (typeof response === 'string') {
          response = JSON.parse(response);
        }
        if (response && response.selectors) {
          this._applySelectors(response.selectors);
          this._version = response.version;
          logger.info(TAG, "重新加载完成，当前 " + Object.keys(this._cache).length + " 个选择器");
          return this._cache[actionName] || null;
        }
      } catch (e) {
        logger.warn(TAG, "重新加载失败: " + e.message);
      }
    }

    logger.error(TAG, "未找到选择器配置: " + actionName + " (已缓存 " + Object.keys(this._cache).length + " 个)");
    return null;
  },

  /**
   * 应用选择器配置到缓存
   * 同名 action 择优保留：精确匹配当前抖音版本 > default > 其他版本
   * 这样 _cache 每个 action 只存一条，不会膨胀
   * @param {Array} selectors
   */
  _applySelectors: function (selectors) {
    var douyinVersion = this._douyinVersion;
    if (douyinVersion === undefined) {
      try {
        douyinVersion = context.getPackageManager()
          .getPackageInfo("com.ss.android.ugc.aweme", 0).versionName;
      } catch (e) { douyinVersion = ""; }
      this._douyinVersion = douyinVersion;
    }

    function _priority(platformVer) {
      // exact match: 3, specific version (e.g. "38.6.0"): 2, default/empty: 1
      if (platformVer === douyinVersion) return 3;
      if (!platformVer || platformVer === "default") return 1;
      return 2;
    }

    // Semantic version distance (lower = closer)
    function _versionDist(v1, v2) {
      if (!v1 || !v2 || v1 === "default" || v2 === "default") return 9999;
      var p1 = String(v1).split("."), p2 = String(v2).split(".");
      var maxLen = Math.max(p1.length, p2.length);
      var dist = 0;
      for (var i = 0; i < maxLen; i++) {
        dist = dist * 1000 + Math.abs((+p1[i] || 0) - (+p2[i] || 0));
      }
      return dist;
    }

    for (var i = 0; i < selectors.length; i++) {
      var s = selectors[i];
      var existing = this._cache[s.action_name];
      var p = _priority(s.platform_version);
      if (!existing || p > _priority(existing.platform_version)) {
        this._cache[s.action_name] = s;
      } else if (existing && p === _priority(existing.platform_version)) {
        // Same priority → pick closest version to device
        var sVer = s.platform_version || "";
        var exVer = existing.platform_version || "";
        if (_versionDist(sVer, douyinVersion) < _versionDist(exVer, douyinVersion)) {
          this._cache[s.action_name] = s;
        }
      }
    }
    logger.info(TAG, "已应用选择器配置，_cache " + Object.keys(this._cache).length + " 个选择器 (抖音 " + douyinVersion + ")");
  },

  /**
   * 同步模板图片 — 从服务端下载缺失的模板，清理多余的
   */
  syncTemplates: function () {
    try {
      var response = apiClient.fetchTemplateList();
      if (!response || !response.templates) {
        logger.warn(TAG, "获取模板列表失败");
        return;
      }

      var remoteList = response.templates;
      var localDir = "/sdcard/dy_auto/templates/";
      files.ensureDir(localDir);

      // 构建远程文件名集合
      var remoteNames = {};
      for (var i = 0; i < remoteList.length; i++) {
        remoteNames[remoteList[i].filename] = remoteList[i];
      }

      // 下载缺失的模板
      var downloaded = 0;
      for (var j = 0; j < remoteList.length; j++) {
        var t = remoteList[j];
        var localPath = localDir + t.filename;
        if (!files.exists(localPath)) {
          var data = apiClient.downloadTemplate(t.filename);
          if (data) {
            files.writeBytes(localPath, data);
            downloaded++;
            logger.info(TAG, "模板已下载: " + t.filename + " (" + data.length + " bytes)");
          } else {
            logger.warn(TAG, "模板下载失败: " + t.filename);
          }
        }
      }

      // 清理本地多余模板
      var cleaned = 0;
      if (files.isDir(localDir)) {
        var localFiles = files.listDir(localDir);
        for (var k = 0; k < localFiles.length; k++) {
          if (!remoteNames[localFiles[k]]) {
            try {
              files.remove(localDir + localFiles[k]);
              cleaned++;
              logger.info(TAG, "清理过期模板: " + localFiles[k]);
            } catch (e) {
              logger.warn(TAG, "清理模板失败: " + localFiles[k] + " - " + e.message);
            }
          }
        }
      }

      if (downloaded > 0 || cleaned > 0) {
        logger.info(TAG, "模板同步完成: 下载 " + downloaded + ", 清理 " + cleaned);
      }
    } catch (e) {
      logger.warn(TAG, "模板同步失败: " + e.message);
    }
  },

  /**
   * 获取当前版本号
   */
  getVersion: function () {
    return this._version;
  },
};

global.__selectorLoader = selectorLoader;
module.exports = selectorLoader;
