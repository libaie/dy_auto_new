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
var _lastRequestWas4xx = false;  // 兼容诊断标志；是否重试由具体状态码决定
var _flushingOfflineQueue = false;
var _sessionGeneration = 0;
var _activeTaskSession = null;

function _isCurrentSession(client, session) {
  return !!session && session.generation === _sessionGeneration &&
    session.serverUrl === config.serverUrl && session.deviceSecret === config.deviceSecret &&
    session.deviceId === config.deviceId && session.authFailure === client._onAuthFailure;
}

function _newRequestState(client, session) {
  // Status belongs to this request, including nested/concurrent heartbeat and
  // offline replay requests. A shared last-status flag cannot decide retries.
  return { session: session || client.captureSession(), status: 0 };
}

function _discardRetiredOfflineItems(client) {
  for (var i = offlineQueue.length - 1; i >= 0; i--) {
    if (!_isCurrentSession(client, offlineQueue[i].session)) {
      logger.warn(TAG, "离线项所属配对已失效，丢弃: " + offlineQueue[i].path);
      offlineQueue.splice(i, 1);
    }
  }
}

function _isPermanentClientError(status) {
  // Retry transient failures only within their original pairing session.
  return status >= 400 && status < 500 && status !== 401 && status !== 408 && status !== 429;
}

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
    _sessionGeneration++;
    _discardRetiredOfflineItems(this);
  },

  captureSession: function () {
    return {
      serverUrl: config.serverUrl, deviceSecret: config.deviceSecret,
      deviceId: config.deviceId, authFailure: this._onAuthFailure,
      generation: _sessionGeneration,
    };
  },

  isCurrentSession: function (session) {
    return _isCurrentSession(this, session);
  },

  // The executor owns this binding until its worker exits. Control traffic
  // uses fresh sessions; only task side effects inherit the attempt's origin.
  beginTaskSession: function (session) {
    _activeTaskSession = session || this.captureSession();
    return _activeTaskSession;
  },

  endTaskSession: function (session) {
    if (_activeTaskSession === session) _activeTaskSession = null;
  },

  _postTask: function (path, body, timeout, requestState) {
    return this.post(path, body, timeout, requestState || _newRequestState(this, _activeTaskSession));
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
    _lastRequestWas4xx = false;
    var requestState = opts.requestState || _newRequestState(this);
    requestState.status = 0;
    var body = opts.body || null;
    var timeout = opts.timeout || netConfig.requestTimeout;
    var parseJson = opts.parseJson !== false;
    var label = opts.label || method;
    var session = requestState.session;
    var deviceSecret = session.deviceSecret;
    var authFailure = session.authFailure;
    var self = this;
    function isCurrentSession() {
      return _isCurrentSession(self, session);
    }

    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      if (!isCurrentSession()) return null;
      try {
        var reqOpts = {
          headers: { "X-Device-Secret": deviceSecret },
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

        // A retired request must neither apply old side data nor invalidate a
        // replacement pairing, even when the server URL has not changed.
        if (!isCurrentSession()) return null;
        requestState.status = response.statusCode;
        if (response.statusCode === 200) {
          var result = parseJson ? JSON.parse(this._readBody(response)) : this._readBodyBytes(response);
          if (!isCurrentSession()) return null;
          this._markOnline();
          if (!isCurrentSession()) return null;
          _lastRequestWas4xx = false;
          return result;
        }

        if (response.statusCode === 401) {
          logger.error(TAG, label + " 认证失败(401)，设备可能已被删除");
          if (authFailure) {
            authFailure();
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

      if (!isCurrentSession()) return null;
      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "将在 " + Math.round(delay) + "ms 后重试...");
        sleep(delay);
      }
    }

    if (!isCurrentSession()) return null;
    this._markOffline();
    logger.error(TAG, label + " 所有重试均失败");
    return null;
  },

  /**
   * 带重试的 HTTP GET
   */
  get: function (path, params) {
    var requestState = _newRequestState(this);
    if (!requestState.session.serverUrl) {
      logger.error(TAG, "serverUrl 未设置，无法请求: " + path);
      return null;
    }
    var url = requestState.session.serverUrl + path;
    if (params) {
      var queryParts = [];
      for (var key in params) {
        queryParts.push(encodeURIComponent(key) + "=" + encodeURIComponent(params[key]));
      }
      url += "?" + queryParts.join("&");
    }
    return this._requestWithRetry("GET", url, { label: "GET " + path, requestState: requestState });
  },

  /**
   * 带重试的 HTTP POST
   */
  post: function (path, body, timeout, requestState) {
    requestState = requestState || _newRequestState(this);
    requestState.status = 0;
    _lastRequestWas4xx = false;
    if (!_isCurrentSession(this, requestState.session)) return null;
    if (!requestState.session.serverUrl) {
      logger.error(TAG, "serverUrl 未设置，无法请求: " + path);
      return null;
    }
    var url = requestState.session.serverUrl + path;
    return this._requestWithRetry("POST", url, { body: body, label: "POST " + path, timeout: timeout, requestState: requestState });
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
    }
    // Retry pending reports on subsequent healthy traffic as well as reconnection.
    if (offlineQueue.length > 0 && !_flushingOfflineQueue) this._flushOfflineQueue();
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
    if (_flushingOfflineQueue) return;
    _flushingOfflineQueue = true;
    try {
      var flushSession = this.captureSession();
      _discardRetiredOfflineItems(this);
      while (offlineQueue.length > 0 && _isCurrentSession(this, flushSession)) {
        var item = offlineQueue.shift();
        if (!_isCurrentSession(this, item.session)) continue;
        logger.info(TAG, "刷新离线项: " + item.path);
        var requestState = _newRequestState(this, item.session);
        var result = this.post(item.path, item.body, null, requestState);
        if (!_isCurrentSession(this, item.session)) continue;
        if (!result) {
          if (_isPermanentClientError(requestState.status)) {
            logger.error(TAG, "离线项永久失败(" + requestState.status + ")，跳过: " + item.path);
            continue;
          }
          item.retries = (item.retries || 0) + 1;
          offlineQueue.unshift(item);
          // Keep transient failures for the next healthy request, without a tight loop.
          break;
        }
      }
    } finally {
      _flushingOfflineQueue = false;
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
        var item = {
          action_name: t.action_name,
          filename: t.filename,
          data: android.util.Base64.encodeToString(t.data, 0),  // base64 for JSON
          resolution: resolution,
        };
        var fields = ["source_selector_id", "source_selector_version", "source_platform_version", "source_resolution_profile", "platform_version", "source_resolution", "source_density"];
        for (var i = 0; i < fields.length; i++) {
          if (t[fields[i]] !== undefined) item[fields[i]] = t[fields[i]];
        }
        return item;
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

  _pushToOfflineQueue: function (path, body, label, critical, session) {
    if (!_isCurrentSession(this, session)) return;
    _discardRetiredOfflineItems(this);
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
    offlineQueue.push({ path: path, body: body, retries: 0, critical: !!critical, session: session });
  },

  report: function (taskId, status, result, uiSnapshot, leaseId, session) {
    _lastRequestWas4xx = false;
    var requestState = _newRequestState(this, session || _activeTaskSession);
    var body = {
      task_id: taskId,
      status: status,
      result: result || {},
      ui_snapshot: uiSnapshot || null,
    };
    if (leaseId) body.lease_id = leaseId;
    var response = this._postTask("/api/device/report", body, null, requestState);
    if (!response && _isCurrentSession(this, requestState.session) && !_isPermanentClientError(requestState.status)) {
      logger.warn(TAG, "任务结果上报失败(status=" + status + ")，加入离线队列重试");
      this._pushToOfflineQueue("/api/device/report", body, "任务结果", true, requestState.session);
    }
    return response;
  },

  collectReport: function (payload) {
    _lastRequestWas4xx = false;
    var requestState = _newRequestState(this, _activeTaskSession);
    var response = this._postTask("/api/device/collect-report", payload, null, requestState);
    if (response && response.user_conflict === true) {
      logger.warn(TAG, "评论已保存，用户资料与其他用户的既有记录冲突，未覆盖");
    }
    if (!response && _isCurrentSession(this, requestState.session) && !_isPermanentClientError(requestState.status)) this._pushToOfflineQueue("/api/device/collect-report", payload, "采集数据", true, requestState.session);
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
    return this._postTask("/api/device/progress", body);
  },

  fetchSelectors: function (currentVersion, resolution) {
    var params = { version: currentVersion || 0 };
    if (resolution) params.resolution = resolution;
    return this.get("/api/device/selectors", params);
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
    return this._postTask("/api/device/comment-claim-reply", {
      author: author,
      text: text,
    });
  },

  releaseCommentReply: function (author, text) {
    return this._postTask("/api/device/comment-claim-release", {
      author: author,
      text: text,
    });
  },

  reportRiskControl: function (accountId, riskType, detail) {
    return this._postTask("/api/device/risk-report", {
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
    var body = {};
    for (var key in data) {
      if (Object.prototype.hasOwnProperty.call(data, key)) body[key] = data[key];
    }
    body.preserve_on_unknown = true;
    return this._postTask("/api/device/dm-claim-recipient", body);
  },

  reportDMSend: function (data) {
    return this._postTask("/api/device/dm-send-report", data);
  },

  releaseDMRecipient: function (data) {
    return this._postTask("/api/device/dm-release-recipient", data);
  },

  saveCommentAIReply: function (nickname, text, aiReply, taskId, intendedProvince, intendedCity, intendedAttraction) {
    var data = {
      nickname: nickname, text: text, ai_reply: aiReply, task_id: taskId || null,
    };
    if (intendedProvince != null) data.intended_province = intendedProvince;
    if (intendedCity != null) data.intended_city = intendedCity;
    if (intendedAttraction != null) data.intended_attraction = intendedAttraction;
    return this._postTask("/api/device/comment-ai-reply", data);
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
    return this._postTask("/api/device/user-profile", payload);
  },

  uploadUserAvatar: function (douyinId, imageBase64) {
    return this._postTask("/api/device/user-avatar", { douyin_id: douyinId, image_base64: imageBase64 });
  },

  /**
   * 增量统计上报——每完成一个子操作（回复/关注/私信）调用一次
   * 保证任务中途崩溃时已完成操作的统计数据不丢失
   * @param {string} accountId
   * @param {string} taskType — "reply_comment" | "follow" | "search_dm" | ...
   * @param {number} count — 操作次数，默认 1
   */
  incrementStats: function (accountId, taskType, targetId, count) {
    var requestState = _newRequestState(this, _activeTaskSession);
    var taskExecutor = getTaskExecutor();
    var tid = taskExecutor.getCurrentTaskId();
    if (!tid) return null;  // 无活跃任务，拒绝上报
    _lastRequestWas4xx = false;
    var body = {
      task_id: tid,
      lease_id: taskExecutor.getCurrentLeaseId() || null,
      account_id: accountId || taskExecutor.getCurrentAccountId(),
      task_type: taskType,
      target_id: targetId || "",
      op_index: taskExecutor.getNextOpIndex(),
      count: count || 1,
    };
    var resp = this._postTask("/api/device/stats/increment", body, null, requestState);
    if (!resp && _isCurrentSession(this, requestState.session) && !_isPermanentClientError(requestState.status)) {
      logger.warn(TAG, "增量统计上报失败: " + taskType + " #" + (body.op_index) + " target=" + (targetId || "") + " → 加入离线队列");
      this._pushToOfflineQueue("/api/device/stats/increment", body, "统计(" + taskType + ")", false, requestState.session);
    }
    return resp;
  },
};

module.exports = apiClient;
