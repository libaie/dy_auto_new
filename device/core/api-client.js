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

function getTaskExecutor() {
  return require("./task-executor");
}

// 离线队列 — 网络失败时缓存待上报数据
var offlineQueue = [];
var isOnline = true;
var _lastRequestWas4xx = false;  // 4xx = 客户端错误，不应重试

function _ensureDirPath(dir) {
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

var apiClient = {
  _onAuthFailure: null,
  _lastRequestWas4xx: function () { return _lastRequestWas4xx; },

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
          _lastRequestWas4xx = true;
          var respBody = "";
          try { respBody = this._readBody(response); } catch (e2) {}
          logger.error(TAG, label + " 客户端错误: " + response.statusCode +
            (respBody ? " body=" + respBody.substring(0, 200) : ""));
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
  post: function (path, body, timeout) {
    if (!config.serverUrl) {
      logger.error(TAG, "serverUrl 未设置，无法请求: " + path);
      return null;
    }
    var url = config.serverUrl + path;
    return this._requestWithRetry("POST", url, { body: body, label: "POST " + path, timeout: timeout });
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

  fetchDMSequences: function () {
    return this.get("/api/dm-sequences/device/sync");
  },

  fetchTemplateList: function (resolution) {
    var path = "/api/device/templates";
    if (resolution) path += "?resolution=" + encodeURIComponent(resolution);
    return this.get(path);
  },

  uploadCalibration: function (templates, resolution) {
    var body = {
      templates: templates.map(function (t) {
        return {
          action_name: t.action_name,
          filename: t.filename,
          data: android.util.Base64.encodeToString(t.data, 0),  // base64 for JSON
          resolution: resolution,
        };
      }),
      resolution: resolution,
    };
    return this.post("/api/device/calibrate", body);
  },

  downloadTemplate: function (filename, resolution) {
    var url = config.serverUrl + "/api/device/templates/" + encodeURIComponent(filename);
    if (resolution) url += "?resolution=" + encodeURIComponent(resolution);
    return this._downloadWithRetry(url);
  },

  _pushToOfflineQueue: function (path, body, label, critical) {
    if (offlineQueue.length >= netConfig.offlineQueueMax) {
      // Prefer evicting non-critical items (stats) over critical (task reports, collect)
      var evicted = false;
      for (var i = 0; i < offlineQueue.length; i++) {
        if (!offlineQueue[i].critical) {
          logger.warn(TAG, "离线队列已满，驱逐非关键项: " + offlineQueue[i].path);
          offlineQueue.splice(i, 1);
          evicted = true;
          break;
        }
      }
      if (!evicted) {
        logger.warn(TAG, "离线队列已满且全为关键项，拒绝入队: " + label);
        return;
      }
    }
    logger.info(TAG, label + "加入离线队列");
    offlineQueue.push({ path: path, body: body, retries: 0, critical: !!critical });
  },

  report: function (taskId, status, result, uiSnapshot, leaseId) {
    _lastRequestWas4xx = false;
    var body = {
      task_id: taskId,
      status: status,
      result: result || {},
      ui_snapshot: uiSnapshot || null,
    };
    if (leaseId) body.lease_id = leaseId;
    var response = this.post("/api/device/report", body);
    if (!response && !_lastRequestWas4xx) {
      logger.warn(TAG, "任务结果上报失败(status=" + status + ")，加入离线队列重试");
      this._pushToOfflineQueue("/api/device/report", body, "任务结果", true);
    }
    return response;
  },

  collectReport: function (payload) {
    _lastRequestWas4xx = false;
    var response = this.post("/api/device/collect-report", payload);
    if (!response && !_lastRequestWas4xx) this._pushToOfflineQueue("/api/device/collect-report", payload, "采集数据", true);
    return response;
  },

  heartbeat: function () {
    return this.post("/api/device/heartbeat", { device_id: config.deviceId });
  },

  reportProgress: function (taskId, step, detail, progress) {
    var body = {
      task_id: taskId,
      step: step || "",
      detail: detail || "",
      progress: progress || 0,
    };
    var taskExecutor = getTaskExecutor();
    var leaseId = taskExecutor.getCurrentLeaseId();
    if (leaseId) body.lease_id = leaseId;
    return this.post("/api/device/progress", body);
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
    if (!body) {
      logger.error(TAG, "脚本下载所有重试均失败");
      return false;
    }
    logger.info(TAG, "脚本下载成功, size=" + body.length);
    // 用 Java FileOutputStream 直接写，绕过 AutoJS files API 的 byte array bug
    var baseDir = null;
    try { baseDir = context.getFilesDir().getAbsolutePath(); } catch (e) {}
    if (!baseDir) { try { baseDir = context.getExternalFilesDir(null).getAbsolutePath(); } catch (e2) {} }
    if (!baseDir) { baseDir = files.cwd(); }
    var updateDir = baseDir + "/update";
    var zipPath = updateDir + "/device-script.zip";
    var wrote = false;
    for (var attempt = 0; attempt < 3; attempt++) {
      var fos = null;
      try {
        if (!_ensureDirPath(updateDir)) { sleep(300); continue; }
        fos = new java.io.FileOutputStream(zipPath);
        fos.write(body);
        fos.close();
        fos = null;
        if (files.exists(zipPath)) { wrote = true; break; }
        sleep(200);
      } catch (e) {
        logger.warn(TAG, "写入更新包失败(尝试" + (attempt + 1) + "/3): " + e.message);
        sleep(500);
      } finally {
        try { if (fos) fos.close(); } catch (e2) {}
      }
    }
    if (!wrote) {
      logger.error(TAG, "无法写入更新包到: " + zipPath);
      return false;
    }
    logger.info(TAG, "脚本已下载: " + zipPath + " (" + body.length + " bytes)");
    return true;
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

  releaseCommentReply: function (author, text) {
    return this.post("/api/device/comment-claim-release", {
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

  // --- DM conversation ---

  claimDMRecipient: function (data) {
    return this.post("/api/device/dm-claim-recipient", data);
  },

  reportDMSend: function (data) {
    return this.post("/api/device/dm-send-report", data);
  },

  releaseDMRecipient: function (data) {
    return this.post("/api/device/dm-release-recipient", data);
  },

  saveCommentAIReply: function (nickname, text, aiReply, taskId, intendedProvince, intendedCity, intendedAttraction) {
    var data = {
      nickname: nickname, text: text, ai_reply: aiReply, task_id: taskId || null,
    };
    if (intendedProvince != null) data.intended_province = intendedProvince;
    if (intendedCity != null) data.intended_city = intendedCity;
    if (intendedAttraction != null) data.intended_attraction = intendedAttraction;
    return this.post("/api/device/comment-ai-reply", data);
  },

  saveUserProfile: function (data) {
    var payload = {
      nickname: data.nickname,
      douyin_id: data.douyin_id || "",
      fans_count: data.fans_count || "",
      likes_count: data.likes_count || "",
      follow_count: data.follow_count || "",
      works_count: data.works_count || "",
      gender: data.gender || "",
      age: data.age || "",
      ip_location: data.ip_location || "",
      is_private: data.is_private || "",
      keyword: data._keyword || "",
      task_id: data._taskId || "",
    };
    if (data._intended_province) payload.intended_province = data._intended_province;
    if (data._intended_city) payload.intended_city = data._intended_city;
    if (data._intended_attraction) payload.intended_attraction = data._intended_attraction;
    return this.post("/api/device/user-profile", payload);
  },

  uploadUserAvatar: function (douyinId, imageBase64) {
    return this.post("/api/device/user-avatar", { douyin_id: douyinId, image_base64: imageBase64 });
  },

  /**
   * 增量统计上报——每完成一个子操作（回复/关注/私信）调用一次
   * 保证任务中途崩溃时已完成操作的统计数据不丢失
   * @param {string} accountId
   * @param {string} taskType — "reply_comment" | "follow" | "search_dm" | ...
   * @param {number} count — 操作次数，默认 1
   */
  incrementStats: function (accountId, taskType, targetId, count) {
    var taskExecutor = getTaskExecutor();
    var tid = taskExecutor.getCurrentTaskId();
    if (!tid) return null;  // 无活跃任务，拒绝上报
    _lastRequestWas4xx = false;
    var body = {
      task_id: tid,
      account_id: accountId || taskExecutor.getCurrentAccountId(),
      task_type: taskType,
      target_id: targetId || "",
      op_index: taskExecutor.getNextOpIndex(),
      count: count || 1,
    };
    var resp = this.post("/api/device/stats/increment", body);
    if (!resp && !_lastRequestWas4xx) {
      logger.warn(TAG, "增量统计上报失败: " + taskType + " #" + (body.op_index) + " target=" + (targetId || "") + " → 加入离线队列");
      this._pushToOfflineQueue("/api/device/stats/increment", body, "统计(" + taskType + ")", false);
    }
    return resp;
  },
};

module.exports = apiClient;
