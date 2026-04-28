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
   * 通用重试请求
   * @param {string} method - "GET" 或 "POST"
   * @param {string} url - 完整 URL
   * @param {Object} opts - { body, timeout, parseJson, label }
   * @returns {*} 解析后的 JSON 或原始 body，失败返回 null
   */
  _requestWithRetry: function (method, url, opts) {
    var body = opts.body || null;
    var timeout = opts.timeout || netConfig.requestTimeout;
    var parseJson = opts.parseJson !== false;
    var label = opts.label || method;

    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var reqOpts = {
          headers: { "X-Device-Secret": config.deviceSecret },
          timeout: timeout,
        };
        if (method === "POST") {
          reqOpts.headers["Content-Type"] = "application/json";
          reqOpts.body = JSON.stringify(body);
        }

        var response = method === "POST" ? http.post(url, reqOpts) : http.get(url, reqOpts);

        if (response.statusCode === 200) {
          this._markOnline();
          return parseJson ? JSON.parse(response.body) : response.body;
        }

        if (response.statusCode >= 400 && response.statusCode < 500) {
          logger.error(TAG, label + " client error: " + response.statusCode);
          return null;
        }

        logger.warn(TAG, label + " server error: " + response.statusCode +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      } catch (e) {
        logger.warn(TAG, label + " network error: " + e.message +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      }

      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "Retrying in " + Math.round(delay) + "ms...");
        sleep(delay);
      }
    }

    this._markOffline();
    logger.error(TAG, label + " failed after all retries");
    return null;
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
    return this._requestWithRetry("GET", url, { label: "GET " + path });
  },

  /**
   * 带重试的 HTTP POST
   */
  post: function (path, body) {
    var url = config.serverUrl + path;
    return this._requestWithRetry("POST", url, { body: body, label: "POST " + path });
  },

  /**
   * 带重试的二进制下载
   */
  _downloadWithRetry: function (url) {
    return this._requestWithRetry("GET", url, {
      timeout: 60000,
      parseJson: false,
      label: "Download",
    });
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
    var MAX_FLUSH_RETRIES = 3;
    while (offlineQueue.length > 0) {
      var item = offlineQueue.shift();
      logger.info(TAG, "Flushing offline item: " + item.path);
      var result = this.post(item.path, item.body);
      if (!result) {
        item.retries = (item.retries || 0) + 1;
        if (item.retries >= MAX_FLUSH_RETRIES) {
          logger.error(TAG, "Dropping offline item after " + MAX_FLUSH_RETRIES + " retries: " + item.path);
        } else {
          offlineQueue.unshift(item);
        }
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
      offlineQueue.push({ path: "/api/device/report", body: body, retries: 0 });
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
