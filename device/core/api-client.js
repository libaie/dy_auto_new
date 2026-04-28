var config = require("../config");
var logger = require("../utils/logger");

var TAG = "API";
var netConfig = config.network || {
  requestTimeout: 10000,
  maxRetries: 3,
  retryBaseDelay: 2000,
  retryMaxDelay: 30000,
  offlineQueueMax: 100,
};

// 离线队列 — 网络失败时缓存待上报数据
var offlineQueue = [];
var isOnline = true;

var apiClient = {
  /**
   * 计算重试延迟（指数退避 + 抖动）
   */
  _retryDelay: function (attempt) {
    var base = netConfig.retryBaseDelay * Math.pow(2, attempt);
    var jitter = Math.random() * base * 0.3;
    return Math.min(base + jitter, netConfig.retryMaxDelay);
  },

  /**
   * 带重试的 HTTP GET
   */
  get: function (path, params) {
    var url = config.serverUrl + path;
    if (params) {
      var queryParts = [];
      for (var key in params) {
        queryParts.push(encodeURIComponent(key) + "=" + encodeURIComponent(params[key]));
      }
      url += "?" + queryParts.join("&");
    }

    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var response = http.get(url, {
          headers: { "X-Device-Secret": config.deviceSecret },
          timeout: netConfig.requestTimeout,
        });

        if (response.statusCode === 200) {
          this._markOnline();
          return JSON.parse(response.body);
        }

        if (response.statusCode >= 400 && response.statusCode < 500) {
          logger.error(TAG, "GET " + path + " client error: " + response.statusCode);
          return null;
        }

        logger.warn(TAG, "GET " + path + " server error: " + response.statusCode +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      } catch (e) {
        logger.warn(TAG, "GET " + path + " network error: " + e.message +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      }

      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "Retrying in " + Math.round(delay) + "ms...");
        sleep(delay);
      }
    }

    this._markOffline();
    logger.error(TAG, "GET " + path + " failed after all retries");
    return null;
  },

  /**
   * 带重试的 HTTP POST
   */
  post: function (path, body) {
    var url = config.serverUrl + path;

    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var response = http.post(url, {
          headers: {
            "Content-Type": "application/json",
            "X-Device-Secret": config.deviceSecret,
          },
          body: JSON.stringify(body),
          timeout: netConfig.requestTimeout,
        });

        if (response.statusCode === 200) {
          this._markOnline();
          return JSON.parse(response.body);
        }

        if (response.statusCode >= 400 && response.statusCode < 500) {
          logger.error(TAG, "POST " + path + " client error: " + response.statusCode);
          return null;
        }

        logger.warn(TAG, "POST " + path + " server error: " + response.statusCode +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      } catch (e) {
        logger.warn(TAG, "POST " + path + " network error: " + e.message +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      }

      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "Retrying in " + Math.round(delay) + "ms...");
        sleep(delay);
      }
    }

    this._markOffline();
    logger.error(TAG, "POST " + path + " failed after all retries");
    return null;
  },

  /**
   * 带重试的二进制下载
   */
  _downloadWithRetry: function (url) {
    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var response = http.get(url, {
          headers: { "X-Device-Secret": config.deviceSecret },
          timeout: 60000,
        });
        if (response.statusCode === 200) {
          this._markOnline();
          return response.body;
        }
        logger.warn(TAG, "Download server error: " + response.statusCode +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      } catch (e) {
        logger.warn(TAG, "Download network error: " + e.message +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      }
      if (attempt < netConfig.maxRetries) {
        sleep(this._retryDelay(attempt));
      }
    }
    this._markOffline();
    return null;
  },

  /**
   * 标记网络恢复，刷新离线队列
   */
  _markOnline: function () {
    if (!isOnline) {
      logger.info(TAG, "Network recovered, flushing offline queue (" +
        offlineQueue.length + " items)");
      isOnline = true;
      this._flushOfflineQueue();
    }
  },

  /**
   * 标记网络离线
   */
  _markOffline: function () {
    if (isOnline) {
      logger.warn(TAG, "Network appears offline");
      isOnline = false;
    }
  },

  /**
   * 刷新离线队列
   */
  _flushOfflineQueue: function () {
    while (offlineQueue.length > 0) {
      var item = offlineQueue.shift();
      logger.info(TAG, "Flushing offline item: " + item.path);
      var result = this.post(item.path, item.body);
      if (!result) {
        offlineQueue.unshift(item);
        break;
      }
    }
  },

  // --- 业务方法 ---

  poll: function () {
    return this.get("/api/device/poll", { device_id: config.deviceId });
  },

  report: function (taskId, status, result, uiSnapshot) {
    var body = {
      task_id: taskId,
      status: status,
      result: result || {},
      ui_snapshot: uiSnapshot || null,
    };
    var response = this.post("/api/device/report", body);
    if (!response && !isOnline) {
      if (offlineQueue.length >= netConfig.offlineQueueMax) {
        logger.warn(TAG, "Offline queue full, dropping oldest item");
        offlineQueue.shift();
      }
      logger.info(TAG, "Queuing report for offline flush: " + taskId);
      offlineQueue.push({ path: "/api/device/report", body: body });
    }
    return response;
  },

  heartbeat: function () {
    return this.post("/api/device/heartbeat", { device_id: config.deviceId });
  },

  fetchSelectors: function (currentVersion) {
    return this.get("/api/device/selectors", { version: currentVersion || 0 });
  },

  getScriptVersion: function () {
    var result = this.get("/api/device/script-version");
    return result ? result.version : null;
  },

  downloadScript: function () {
    var url = config.serverUrl + "/api/device/script-download";
    var body = this._downloadWithRetry(url);
    if (body) {
      var scriptDir = files.cwd() + "/update";
      files.ensureDir(scriptDir);
      files.writeBytes(scriptDir + "/device-script.zip", body);
      return true;
    }
    logger.error(TAG, "Script download failed after all retries");
    return false;
  },

  register: function (deviceInfo) {
    return this.post("/api/device/register", deviceInfo);
  },

  isOnline: function () {
    return isOnline;
  },

  getOfflineQueueSize: function () {
    return offlineQueue.length;
  },
};

module.exports = apiClient;
