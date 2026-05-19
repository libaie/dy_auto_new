var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "选择器";

// 使用 global 确保所有 require 路径拿到同一个实例（和 config 一样的模式）
var selectorLoader = global.__selectorLoader || {

  _cache: {},       // action_name -> selector config
  _retriedActions: {},  // action_name -> bool, 每个 action 独立重试
  _version: 0,      // 本地缓存版本号
  _initialized: false,
  _resolution: "",  // 当前设备分辨率，init 时捕获

  /**
   * 初始化 — 从后端拉取全量选择器（带重试）
   */
  init: function () {
    // 第一时间捕获设备分辨率，后续 syncTemplates 等依赖
    this._resolution = device.width + "x" + device.height;
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
          // 检查是否需要为新分辨率设备标定 image 模板
          var needCalibration = false;
          var hasImageSelector = false;
          var hasExactMatch = false;
          for (var actionName in this._cache) {
            var sel = this._cache[actionName];
            if (!sel || !sel.strategies) continue;
            for (var si = 0; si < sel.strategies.length; si++) {
              if (sel.strategies[si].type === "image") {
                hasImageSelector = true;
                break;
              }
            }
            var rp = sel.resolution_profile || "default";
            if (rp === this._resolution) { hasExactMatch = true; }
          }
          // 已有本地模板文件则跳过（避免重复标定）
          var localTplDir = "/sdcard/dy_auto/templates/" + this._resolution + "/";
          var hasLocalTemplates = false;
          try {
            hasLocalTemplates = files.isDir(localTplDir) && files.listDir(localTplDir).length > 0;
          } catch (e) {}
          needCalibration = hasImageSelector && !hasExactMatch && !hasLocalTemplates;
          // 检查关键选择器是否缺失
          var criticalActions = ["search_tab", "video_comment_btn", "comment_list", "follow_button"];
          var missing = [];
          for (var ci = 0; ci < criticalActions.length; ci++) {
            if (!this._cache[criticalActions[ci]]) missing.push(criticalActions[ci]);
          }
          if (needCalibration || missing.length > 0) {
            var reason = needCalibration ? "新分辨率 " + this._resolution + " 缺少 image 模板" : "";
            if (missing.length > 0) reason += (reason ? "; " : "") + "缺少选择器: " + missing.join(",");
            logger.warn(TAG, "触发自动标定: " + reason);
            try {
              var calibrator = require("./calibrator");
              calibrator.run();
            } catch (e) {
              logger.warn(TAG, "自动标定失败: " + e.message);
            }
          }
          return;
        }
        logger.warn(TAG, "服务端返回空选择器 (尝试 " + attempt + ")");
      } catch (e) {
        logger.warn(TAG, "加载选择器异常 (尝试 " + attempt + "): " + e.message);
      }
      if (attempt < maxRetries) sleep(2000);
    }
    logger.error(TAG, "选择器加载全部失败，任务可能无法执行");
    // 如果选择器数量异常少（< 10），可能是新分辨率设备无匹配 profile
    if (Object.keys(this._cache).length < 10) {
      logger.warn(TAG, "选择器数量异常 (" + Object.keys(this._cache).length + ")，可能需要标定");
    }
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

    // Capture device resolution
    var devRes = this._resolution;
    if (!devRes) {
      devRes = device.width + "x" + device.height;
      this._resolution = devRes;
    }
    var devAR = _aspectTag(devRes);

    function _priority(platformVer) {
      // exact match: 3, specific version (e.g. "38.6.0"): 2, default/empty: 1
      if (platformVer === douyinVersion) return 3;
      if (!platformVer || platformVer === "default") return 1;
      return 2;
    }

    function _resProfileScore(sel) {
      var rp = sel.resolution_profile || "default";
      if (!rp || rp === "default") return 1;
      if (rp === devRes) return 3;
      if (_aspectTag(rp) === devAR) return 2;
      return 0;
    }

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

    function _aspectTag(resolution) {
      if (!resolution) return "unknown";
      var parts = resolution.split("x");
      var w = parseInt(parts[0]) || 0;
      var h = parseInt(parts[1]) || 0;
      if (w === 0 || h === 0) return "unknown";
      var a = w, b = h;
      while (b) { var t = b; b = a % b; a = t; }
      return (w / a) + ":" + (h / a);
    }

    function _isBetter(s, existing) {
      var p = _priority(s.platform_version);
      var ep = _priority(existing.platform_version);
      if (p !== ep) return p > ep;
      // Same platform priority: resolution_profile breaks tie
      var rs = _resProfileScore(s);
      var ers = _resProfileScore(existing);
      if (rs !== ers) return rs > ers;
      // Same resolution profile: version distance breaks tie
      var sVer = s.platform_version || "";
      var exVer = existing.platform_version || "";
      return _versionDist(sVer, douyinVersion) < _versionDist(exVer, douyinVersion);
    }

    for (var i = 0; i < selectors.length; i++) {
      var s = selectors[i];
      var existing = this._cache[s.action_name];
      if (!existing || _isBetter(s, existing)) {
        this._cache[s.action_name] = s;
      }
    }
    logger.info(TAG, "已应用选择器配置，_cache " + Object.keys(this._cache).length + " 个选择器 (抖音 " + douyinVersion + ", 分辨率 " + devRes + ")");
  },

  /**
   * 同步模板图片 — 从服务端下载缺失的模板，清理多余的
   */
  syncTemplates: function () {
    try {
      var response = apiClient.fetchTemplateList(this._resolution);
      if (!response || !response.templates) {
        logger.warn(TAG, "获取模板列表失败");
        return;
      }

      var remoteList = response.templates;
      var baseDir = "/sdcard/dy_auto/templates/";
      files.ensureDir(baseDir);

      // Group remote templates by resolution
      var byResolution = {};
      for (var i = 0; i < remoteList.length; i++) {
        var t = remoteList[i];
        var res = t.resolution || "default";
        if (!byResolution[res]) byResolution[res] = {};
        byResolution[res][t.filename] = t;
      }

      // Sync each resolution group
      var downloaded = 0;
      var cleaned = 0;
      for (var res in byResolution) {
        if (!byResolution.hasOwnProperty(res)) continue;
        var resDir = baseDir + res + "/";
        files.ensureDir(resDir);
        var resFiles = byResolution[res];

        // Download missing templates for this resolution
        for (var fn in resFiles) {
          if (!resFiles.hasOwnProperty(fn)) continue;
          var tpl = resFiles[fn];
          var localPath = resDir + fn;
          if (!files.exists(localPath)) {
            var data = apiClient.downloadTemplate(fn);
            if (data) {
              files.writeBytes(localPath, data);
              downloaded++;
              logger.info(TAG, "模板已下载: " + res + "/" + fn + " (" + data.length + " bytes)");
            } else {
              logger.warn(TAG, "模板下载失败: " + fn);
            }
          }
        }

        // Clean stale local templates for this resolution
        if (files.isDir(resDir)) {
          var localFiles = files.listDir(resDir);
          for (var k = 0; k < localFiles.length; k++) {
            if (!resFiles[localFiles[k]]) {
              try {
                files.remove(resDir + localFiles[k]);
                cleaned++;
                logger.info(TAG, "清理过期模板: " + res + "/" + localFiles[k]);
              } catch (e) {
                logger.warn(TAG, "清理模板失败: " + localFiles[k] + " - " + e.message);
              }
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
