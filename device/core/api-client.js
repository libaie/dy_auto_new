// 使用 global.__config 确保与 main.js 共享同一 config 对象
// 避免 require("./config") vs require("../config") 路径不一致导致多实例
var config = global.__config || require("../config");
var logger = require("../utils/logger");

var TAG = "网络";
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
  _onAuthFailure: null,

  /**
   * 设置认证失败回调（401 时触发）
   */
  setAuthFailureHandler: function (callback) {
    this._onAuthFailure = callback;
  },

  /**
   * 应用代理配置到 HTTP 请求
   * @param {Object} proxyConfig - { type, host, port, username, password }
   */
  setProxy: function (proxyConfig) {
    if (!proxyConfig || !proxyConfig.host) {
      logger.info(TAG, "未配置代理");
      config.proxy = null;
      return;
    }

    config.proxy = proxyConfig;
    logger.info(TAG, "代理已配置: " + proxyConfig.type + "://" +
      proxyConfig.host + ":" + proxyConfig.port + " (认证=" + (proxyConfig.username ? "是" : "否") + ")");
  },

  /**
   * 获取当前代理配置的 HTTP 选项
   * @returns {Object} 适合 http.get/http.post 的选项
   */
  _getProxyOptions: function () {
    if (!config.proxy) return {};

    var proxy = config.proxy;
    var proxyUrl = proxy.type + "://" + proxy.host + ":" + proxy.port;
    if (proxy.username) {
      var encUser = encodeURIComponent(proxy.username);
      var encPass = encodeURIComponent(proxy.password || "");
      proxyUrl = proxy.type + "://" + encUser + ":" + encPass +
        "@" + proxy.host + ":" + proxy.port;
    }
    return { proxy: proxyUrl };
  },

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
  /**
   * 读取响应体为字符串（兼容 AutoJS6 的 Java ResponseBody 对象）
   */
  _readBody: function (response) {
    var body = response.body;
    if (typeof body === "string") return body;
    try {
      return body.string();
    } catch (e) {
      return String(body);
    }
  },

  /**
   * 读取响应体为字节数组（用于二进制下载）
   */
  _readBodyBytes: function (response) {
    var body = response.body;
    if (body instanceof Array) return body;
    try {
      return body.bytes();
    } catch (e) {
      try {
        return body.string();
      } catch (e2) {
        return String(body);
      }
    }
  },

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
        // 合并代理配置
        var proxyOpts = this._getProxyOptions();
        for (var pk in proxyOpts) {
          reqOpts[pk] = proxyOpts[pk];
        }

        var response;
        if (method === "POST") {
          response = http.postJson(url, body, reqOpts);
        } else {
          response = http.get(url, reqOpts);
        }

        if (response.statusCode === 200) {
          this._markOnline();
          if (parseJson) {
            return JSON.parse(this._readBody(response));
          }
          return this._readBodyBytes(response);
        }

        if (response.statusCode === 401) {
          logger.error(TAG, label + " 认证失败(401)，设备可能已被删除");
          if (this._onAuthFailure) {
            this._onAuthFailure();
          }
          return null;
        }

        if (response.statusCode >= 400 && response.statusCode < 500) {
          logger.error(TAG, label + " 客户端错误: " + response.statusCode);
          return null;
        }

        logger.warn(TAG, label + " 服务端错误: " + response.statusCode +
          " (第 " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + " 次尝试)");
      } catch (e) {
        logger.warn(TAG, label + " 网络错误: " + e.message +
          " (第 " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + " 次尝试)");
      }

      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "将在 " + Math.round(delay) + "ms 后重试...");
        sleep(delay);
      }
    }

    this._markOffline();
    logger.error(TAG, label + " 所有重试均失败");
    return null;
  },

  /**
   * 带重试的 HTTP GET
   */
  get: function (path, params) {
    if (!config.serverUrl) {
      logger.error(TAG, "serverUrl 未设置，无法请求: " + path);
      return null;
    }
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
    if (!config.serverUrl) {
      logger.error(TAG, "serverUrl 未设置，无法请求: " + path);
      return null;
    }
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
      logger.info(TAG, "网络已恢复，刷新离线队列 (" +
        offlineQueue.length + " 条)");
      isOnline = true;
      this._flushOfflineQueue();
    }
  },

  /**
   * 标记网络离线
   */
  _markOffline: function () {
    if (isOnline) {
      logger.warn(TAG, "网络已离线");
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
      logger.info(TAG, "刷新离线项: " + item.path);
      var result = this.post(item.path, item.body);
      if (!result) {
        item.retries = (item.retries || 0) + 1;
        if (item.retries >= MAX_FLUSH_RETRIES) {
          logger.error(TAG, "离线项 " + MAX_FLUSH_RETRIES + " 次重试后丢弃: " + item.path);
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

  fetchTemplateList: function () {
    return this.get("/api/device/templates");
  },

  downloadTemplate: function (filename) {
    var url = config.serverUrl + "/api/device/templates/" + encodeURIComponent(filename);
    return this._downloadWithRetry(url);
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
        logger.warn(TAG, "离线队列已满，丢弃最旧项");
        offlineQueue.shift();
      }
      logger.info(TAG, "任务结果加入离线队列: " + taskId);
      offlineQueue.push({ path: "/api/device/report", body: body, retries: 0 });
    }
    return response;
  },

  heartbeat: function () {
    return this.post("/api/device/heartbeat", { device_id: config.deviceId });
  },

  reportProgress: function (taskId, step, detail, progress) {
    return this.post("/api/device/progress", {
      task_id: taskId,
      step: step || "",
      detail: detail || "",
      progress: progress || 0,
    });
  },

  fetchSelectors: function (currentVersion) {
    return this.get("/api/device/selectors", { version: currentVersion || 0 });
  },

  fetchPromptTemplates: function (currentVersion) {
    return this.get("/api/device/prompt-templates", { version: currentVersion || 0 });
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
      var zipPath = scriptDir + "/device-script.zip";
      files.writeBytes(zipPath, body);
      // 验证文件确实写入成功
      if (!files.exists(zipPath)) {
        logger.error(TAG, "下载完成但文件不存在: " + zipPath);
        return false;
      }
      logger.info(TAG, "脚本已下载: " + zipPath + " (" + body.length + " bytes)");
      return true;
    }
    logger.error(TAG, "脚本下载所有重试均失败");
    return false;
  },

  register: function (deviceInfo) {
    return this.post("/api/device/register", deviceInfo);
  },

  /**
   * 上报风控检测结果
   * @param {string} accountId - 账号 ID
   * @param {string} riskType - 风控类型 (captcha, risk_control, verify)
   * @param {Object} detail - 风控详情
   */
  claimCommentReply: function (author, text) {
    return this.post("/api/device/comment-claim-reply", {
      author: author,
      text: text,
    });
  },

  reportRiskControl: function (accountId, riskType, detail) {
    return this.post("/api/device/risk-report", {
      account_id: accountId,
      risk_type: riskType,
      detail: detail || {},
      device_id: config.deviceId,
      timestamp: new Date().toISOString(),
    });
  },

  isOnline: function () {
    return isOnline;
  },

  getOfflineQueueSize: function () {
    return offlineQueue.length;
  },
};

module.exports = apiClient;
