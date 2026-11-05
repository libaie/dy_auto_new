var apiClient = require("./api-client");
var logger = require("../utils/logger");
var screenContext = require("./screen-context");

var TAG = "选择器";

function ensureDirPath(dir) {
  if (!dir) return false;
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "目录创建失败: " + dir + " - " + e.message);
    return false;
  }
}

// 使用 global 确保所有 require 路径拿到同一个实例（和 config 一样的模式）
var selectorLoader = global.__selectorLoader || {

  _cache: {},       // action_name -> selector config
  _allSelectors: [], // last authoritative candidates, before profile selection
  _retriedActions: {},  // action_name -> bool, 每个 action 独立重试
  _version: 0,      // 本地缓存版本号
  _initialized: false,
  _resolution: "",  // live physical display size; refreshed before each lookup
  _pendingGeometryRefresh: false,
  _geometryRequestAt: 0,

  _calibrationActions: function () {
    var missing = [];
    for (var action in this._cache) {
      if (!Object.prototype.hasOwnProperty.call(this._cache, action)) continue;
      var selector = this._cache[action];
      if (!selector || !selector.strategies || selector.purpose === "page_detect" || selector.purpose === "extract") continue;
      var hasImage = false, hasSemantic = false, covered = false;
      for (var i = 0; i < selector.strategies.length; i++) {
        var strategy = selector.strategies[i];
        if (strategy.type === "image") {
          hasImage = true;
          if (selector.resolution_profile === this._resolution && (!this._douyinVersion || selector.platform_version === this._douyinVersion)) {
            try { if (files.exists("/sdcard/dy_auto/templates/" + this._resolution + "/" + strategy.template)) covered = true; } catch (e) {}
          }
        } else if (strategy.type !== "coordinate" && strategy.type !== "package" && (strategy.conditions || ["text", "id", "desc", "className", "chain"].indexOf(strategy.type) !== -1)) {
          hasSemantic = true;
        }
      }
      if (hasImage && hasSemantic && !covered) missing.push(action);
    }
    return missing;
  },

  /**
   * 初始化 — 从后端拉取全量选择器（带重试）
   */
  init: function () {
    // 第一时间捕获设备分辨率，后续 syncTemplates 等依赖
    var geometry = screenContext.read();
    this._resolution = geometry ? geometry.width + "x" + geometry.height : device.width + "x" + device.height;
    var maxRetries = 3;
    for (var attempt = 1; attempt <= maxRetries; attempt++) {
      logger.info(TAG, "从服务端加载选择器 (尝试 " + attempt + "/" + maxRetries + ")...");
      try {
        var response = apiClient.fetchSelectors(0, this._resolution);
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
          // 逐动作、逐应用版本检查，其他动作已有模板不能代替本动作。
          var calibrationActions = this._calibrationActions();
          var needCalibration = calibrationActions.length > 0;
          // 检查关键选择器是否缺失
          var criticalActions = ["search_tab", "video_comment_btn", "comment_list", "follow_button"];
          var missing = [];
          for (var ci = 0; ci < criticalActions.length; ci++) {
            if (!this._cache[criticalActions[ci]]) missing.push(criticalActions[ci]);
          }
          if (missing.length > 0) logger.warn(TAG, "缺少选择器配置: " + missing.join(","));
          if (needCalibration) {
            var reason = "分辨率 " + this._resolution + " 缺少当前应用模板: " + calibrationActions.join(",");
            if (missing.length > 0) reason += (reason ? "; " : "") + "缺少选择器: " + missing.join(",");
            logger.warn(TAG, "触发自动标定: " + reason);
            try {
              var calibrator = require("./calibrator");
              calibrator.run({ unattended: true, actions: calibrationActions });
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
    this._refreshGeometry();
    if (serverVersion > this._version) {
      logger.info(TAG, "选择器已过期 (本地=" + this._version + ", 服务端=" + serverVersion + "), 更新中...");
      var response = apiClient.fetchSelectors(this._version, this._resolution);
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
    this._refreshGeometry();
    var selector = this._cache[actionName];
    if (selector) return selector;

    // 未找到 — 每个 action 独立重试一次（可能是初始化时网络异常）
    if (this._initialized && !this._pendingGeometryRefresh && !this._retriedActions[actionName]) {
      this._retriedActions[actionName] = true;
      logger.warn(TAG, "选择器 '" + actionName + "' 未找到，尝试重新加载...");
      try {
        var response = apiClient.fetchSelectors(0, this._resolution);
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

  /** Re-select immediately after rotation/display change, even if config revision
   * is unchanged. A failed network refresh keeps only compatible cached profiles
   * and retries at most once per 10 seconds, rather than once per selector. */
  _refreshGeometry: function () {
    if (this._refreshingGeometry) return;
    var geometry = screenContext.read();
    if (!geometry) return;
    var resolution = geometry.width + "x" + geometry.height;
    var changed = resolution !== this._resolution;
    if (!changed && !this._pendingGeometryRefresh) return;
    if (changed) {
      this._resolution = resolution;
      this._retriedActions = {};
      if (this._allSelectors.length) this._applySelectors(this._allSelectors);
      this._pendingGeometryRefresh = this._initialized;
    }
    if (!this._initialized || (!changed && Date.now() - this._geometryRequestAt < 10000)) return;
    this._geometryRequestAt = Date.now();
    this._refreshingGeometry = true;
    try {
      var response = apiClient.fetchSelectors(0, resolution);
      if (typeof response === "string") response = JSON.parse(response);
      if (response && Array.isArray(response.selectors)) {
        this._applySelectors(response.selectors);
        this._version = response.version;
        this._pendingGeometryRefresh = this._resolution !== resolution;
        this.syncTemplates();
      } else {
        this._pendingGeometryRefresh = true;
      }
    } catch (e) {
      this._pendingGeometryRefresh = true;
      logger.warn(TAG, "分辨率配置刷新失败: " + resolution + " - " + e.message);
    } finally {
      this._refreshingGeometry = false;
    }
  },

  /**
   * 应用选择器配置到缓存
   * 同名 action 择优保留：精确匹配当前抖音版本 > default > 其他版本
   * 这样 _cache 每个 action 只存一条，不会膨胀
   * @param {Array} selectors
   */
  _applySelectors: function (selectors) {
    this._allSelectors = selectors.slice();
    var douyinVersion = this._douyinVersion;
    if (douyinVersion === undefined) {
      try {
        douyinVersion = context.getPackageManager()
          .getPackageInfo("com.ss.android.ugc.aweme", 0).versionName;
      } catch (e) { douyinVersion = ""; }
      this._douyinVersion = douyinVersion;
    }

    // Capture device resolution
    var geometry = screenContext.read();
    var devRes = geometry ? geometry.width + "x" + geometry.height : this._resolution;
    if (!devRes) {
      devRes = device.width + "x" + device.height;
    }
    this._resolution = devRes;
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
      if (!v1 || !v2 || v1 === "default" || v2 === "default") return 999999999;
      var p1 = String(v1).split("."), p2 = String(v2).split(".");
      var maxLen = Math.max(p1.length, p2.length);
      var dist = 0;
      for (var i = 0; i < maxLen; i++) {
        dist = dist * 1000 + Math.abs((+p1[i] || 0) - (+p2[i] || 0));
      }
      return dist;
    }

    function _versionCompare(v1, v2) {
      var p1 = String(v1 || "").split(".");
      var p2 = String(v2 || "").split(".");
      var maxLen = Math.max(p1.length, p2.length);
      for (var i = 0; i < maxLen; i++) {
        var a = +p1[i] || 0;
        var b = +p2[i] || 0;
        if (a !== b) return a > b ? 1 : -1;
      }
      return 0;
    }

    function _prefersNotFutureVersion(v1, v2, target) {
      var v1Future = _versionCompare(v1, target) > 0;
      var v2Future = _versionCompare(v2, target) > 0;
      if (v1Future !== v2Future) return !v1Future;
      return false;
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

      // Same platform priority: actual Douyin version proximity wins first.
      // Example: device 38.7.0 should choose selector 38.6.0 over 38.5.0.
      if (p === 2) {
        var sVer = s.platform_version || "";
        var exVer = existing.platform_version || "";
        var sDist = _versionDist(sVer, douyinVersion);
        var exDist = _versionDist(exVer, douyinVersion);
        if (sDist !== exDist) return sDist < exDist;
        if (_prefersNotFutureVersion(sVer, exVer, douyinVersion)) return true;
        if (_prefersNotFutureVersion(exVer, sVer, douyinVersion)) return false;
      }

      // Exact/default platform tie, or equal version distance: prefer resolution fit.
      var rs = _resProfileScore(s);
      var ers = _resProfileScore(existing);
      if (rs !== ers) return rs > ers;
      return false;
    }

    // Rebuild cache from full authoritative list.
    // Server is the single source of truth — old cache is only consulted
    // for _isBetter to disambiguate duplicates within the server response.
    // Old entries are NEVER carried forward into newCache.
    var oldCache = this._cache;
    var newCache = {};
    for (var i = 0; i < selectors.length; i++) {
      var s = selectors[i];
      if (_resProfileScore(s) === 0) continue;
      var fromNew = newCache[s.action_name];
      var fromOld = oldCache[s.action_name];
      if (fromNew) {
        // Duplicate in server response — keep the better match
        if (_isBetter(s, fromNew)) newCache[s.action_name] = s;
      } else if (fromOld) {
        // Server returned a replacement for a previously-cached selector.
        // Old cache helps disambiguate only; server is authoritative.
        if (_isBetter(fromOld, s)) {
          // Server's selector is authoritative — log the downgrade but use it.
          // The old entry was a better platform/resolution match, but the
          // server content (strategies, templates) is the source of truth.
          logger.info(TAG, "selector " + s.action_name +
            " replaced by server (old platform=" + (fromOld.platform_version || "default") +
            "→new platform=" + (s.platform_version || "default") +
            ", old resol=" + (fromOld.resolution_profile || "default") +
            "→new resol=" + (s.resolution_profile || "default") + ")");
        }
        newCache[s.action_name] = s;
      } else {
        // First occurrence of this action_name
        newCache[s.action_name] = s;
      }
    }
    this._cache = newCache;
    if (this._cache.sort_latest) {
      logger.info(TAG, "sort_latest选择器: 平台=" + (this._cache.sort_latest.platform_version || "default") +
        ", 分辨率=" + (this._cache.sort_latest.resolution_profile || "default") +
        ", 策略=" + JSON.stringify(this._cache.sort_latest.strategies || []));
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
      ensureDirPath(baseDir);

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
        ensureDirPath(resDir);
        var resFiles = byResolution[res];
        var failed = 0;

        // Download missing templates for this resolution
        for (var fn in resFiles) {
          if (!resFiles.hasOwnProperty(fn)) continue;
          var tpl = resFiles[fn];
          var localPath = resDir + fn;
          if (!files.exists(localPath)) {
            var data = apiClient.downloadTemplate(fn, res);
            if (data) {
              files.writeBytes(localPath, data);
              downloaded++;
              logger.info(TAG, "模板已下载: " + res + "/" + fn + " (" + data.length + " bytes)");
            } else {
              failed++;
              logger.warn(TAG, "模板下载失败: " + fn);
            }
          }
        }

        if (failed > 0) {
          logger.warn(TAG, "模板下载未完成，跳过清理旧模板: " + res + " failed=" + failed);
          continue;
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

      // Clean resolution directories that are no longer in the server manifest.
      // The loop above only visits resolutions the server returned; a previously-
      // synced resolution (e.g. 1080x2340) that the server no longer lists would
      // otherwise persist and be used by _findByImage before the default fallback.
      try {
        if (files.isDir(baseDir)) {
          var allResDirs = files.listDir(baseDir);
          for (var di = 0; di < allResDirs.length; di++) {
            var dn = allResDirs[di];
            if (dn === "default" || byResolution[dn]) continue;
            var staleDir = baseDir + dn;
            if (!files.isDir(staleDir)) continue;
            var staleFiles = files.listDir(staleDir);
            for (var sf = 0; sf < staleFiles.length; sf++) {
              try {
                files.remove(staleDir + "/" + staleFiles[sf]);
                cleaned++;
                logger.info(TAG, "清理过期分辨率模板: " + dn + "/" + staleFiles[sf]);
              } catch (e2) {}
            }
            try { files.remove(staleDir); } catch (e3) {}
          }
        }
      } catch (e4) {
        logger.warn(TAG, "清理过期分辨率目录失败: " + e4.message);
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
