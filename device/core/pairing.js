// device/core/pairing.js
// 设备配对模块 — 管理配对请求、轮询审批结果、存储密钥

var logger = require("../utils/logger");

var TAG = "配对";
var STORAGE_KEY = "dy_auto";

/**
 * 读取响应体为字符串（兼容 AutoJS6 的 Java ResponseBody 对象）
 */
function readResponseBody(response) {
  var body = response.body;
  if (typeof body === "string") return body;
  try {
    return body.string();
  } catch (e) {
    return String(body);
  }
}

var pairing = {
  _pairingToken: null,
  _serverUrl: null,

  /**
   * 检查设备是否已完成配对（本地存储中有密钥）
   * @returns {boolean}
   */
  isConfigured: function () {
    var storage = storages.create(STORAGE_KEY);
    return !!storage.get("device_secret", "");
  },

  /**
   * 获取已保存的密钥
   * @returns {string}
   */
  getSavedSecret: function () {
    return storages.create(STORAGE_KEY).get("device_secret", "");
  },

  /**
   * 获取已保存的服务端地址
   * @returns {string}
   */
  getSavedServerUrl: function () {
    return storages.create(STORAGE_KEY).get("server_url", "");
  },

  /**
   * 保存配对信息到本地存储
   * @param {string} serverUrl
   * @param {string} secret
   */
  save: function (serverUrl, secret) {
    var storage = storages.create(STORAGE_KEY);
    storage.put("server_url", serverUrl);
    storage.put("device_secret", secret);
    logger.info(TAG, "配对信息已保存");
  },

  /**
   * 发起配对请求
   * @param {string} serverIp - 服务端 IP（不含端口，默认 8001）
   * @param {string} deviceId - 设备 ID
   * @param {string} deviceName - 设备型号
   * @param {string} osVersion - 系统版本
   * @param {string} appVersion - 应用版本
   * @param {Object} [extra] - 额外设备信息 { screen_resolution, sdk_version, available_memory, manufacturer, ... }
   * @returns {Object|null} { pairing_token, status } 或 null
   */
  request: function (serverIp, deviceId, deviceName, osVersion, appVersion, extra) {
    var port = "8001";
    var ip = serverIp;
    // 支持 ip:port 格式
    if (serverIp.indexOf(":") !== -1) {
      var parts = serverIp.split(":");
      ip = parts[0];
      port = parts[1];
    }
    var serverUrl = "http://" + ip + ":" + port;
    this._serverUrl = serverUrl;

    var url = serverUrl + "/api/device/pair-request";
    var body = {
      device_id: deviceId,
      device_name: deviceName,
      os_version: osVersion || "",
      app_version: appVersion || "",
    };
    // 合并额外设备信息
    if (extra) {
      for (var key in extra) {
        if (extra.hasOwnProperty(key)) {
          body[key] = extra[key];
        }
      }
    }

    try {
      logger.info(TAG, "发送配对请求: " + url);
      logger.info(TAG, "请求体: " + JSON.stringify(body));
      var response = http.postJson(url, body, {
        headers: {},
        timeout: 10000,
      });

      var responseBody = readResponseBody(response);

      logger.info(TAG, "响应状态: " + response.statusCode + ", 响应体: " + responseBody);

      if (response.statusCode === 200) {
        var data = JSON.parse(responseBody);
        this._pairingToken = data.pairing_token;
        logger.info(TAG, "配对请求已提交, 状态: " + data.status);

        // 如果已经批准（已配对设备重连），直接保存密钥
        if (data.status === "approved" && data.secret) {
          this.save(this._serverUrl, data.secret);
        }
        return data;
      }

      logger.error(TAG, "配对请求失败: HTTP " + response.statusCode + " body=" + responseBody);
      return null;
    } catch (e) {
      logger.error(TAG, "配对请求异常: " + e.message + "\n" + e.stack);
      return null;
    }
  },

  /**
   * 轮询审批结果
   * @returns {Object|null} { status, secret?, config? } 或 null
   */
  checkStatus: function () {
    if (!this._pairingToken || !this._serverUrl) {
      logger.error(TAG, "无配对令牌，无法查询状态");
      return null;
    }

    var url = this._serverUrl + "/api/device/pair-status?token=" + this._pairingToken;

    try {
      var response = http.get(url, { timeout: 10000 });

      var responseBody = readResponseBody(response);

      if (response.statusCode === 200) {
        var data = JSON.parse(responseBody);

        if (data.status === "approved" && data.secret) {
          logger.info(TAG, "配对已批准，保存密钥");
          this.save(this._serverUrl, data.secret);
        } else if (data.status === "rejected") {
          logger.warn(TAG, "配对已被拒绝");
        } else {
          logger.debug(TAG, "等待审批中...");
        }

        return data;
      }

      if (response.statusCode === 404) {
        logger.error(TAG, "配对令牌无效或已过期");
        return { status: "expired" };
      }

      logger.error(TAG, "查询配对状态失败: HTTP " + response.statusCode + " body=" + responseBody);
      return null;
    } catch (e) {
      logger.error(TAG, "查询配对状态异常: " + e.message);
      return null;
    }
  },

  /**
   * 通过 WebSocket 等待审批结果（阻塞直到收到结果或超时）
   * @param {Function} onStatusChange - 状态变化回调 onStatusChange(status, data)
   * @returns {Object|null} 审批结果或 null（超时/失败）
   */
  waitForApproval: function (onStatusChange) {
    if (!this._pairingToken || !this._serverUrl) {
      logger.error(TAG, "无配对令牌，无法等待审批");
      return null;
    }

    var wsUrl = this._serverUrl.replace("http://", "ws://") +
      "/api/device/ws/pair/" + this._pairingToken;
    var result = null;
    var done = false;
    var self = this;

    logger.info(TAG, "连接 WS: " + wsUrl);

    try {
      var OkHttpClient = Packages.okhttp3.OkHttpClient;
      var Request = Packages.okhttp3.Request;
      var WebSocketListener = Packages.okhttp3.WebSocketListener;

      var client = new OkHttpClient.Builder()
        .readTimeout(0, java.util.concurrent.TimeUnit.MILLISECONDS)
        .build();

      var request = new Request.Builder().url(wsUrl).build();

      var listener = new JavaAdapter(WebSocketListener, {
        // 设备业务函数：处理 onOpen 对应的抖音自动化动作、状态或安全边界。
        onOpen: function (ws, response) {
          logger.info(TAG, "WS 已连接，等待审批...");
        },
        onMessage: function (ws, text) {
          try {
            var data = JSON.parse(String(text));
            logger.info(TAG, "WS 收到消息: " + data.status);
            result = data;
            done = true;
            if (data.status === "approved" && data.secret) {
              self.save(self._serverUrl, data.secret);
            }
            if (onStatusChange) onStatusChange(data.status, data);
            ws.close(1000, "done");
          } catch (e) {
            logger.error(TAG, "WS 消息解析失败: " + e.message);
          }
        },
        onFailure: function (ws, t, response) {
          logger.error(TAG, "WS 连接失败: " + t.getMessage());
          done = true;
        },
        onClosing: function (ws, code, reason) {
          try { ws.close(1000, null); } catch (e) { /* already closed */ }
          done = true;
        },
      });

      client.newWebSocket(request, listener);

      // 阻塞等待结果，最长 5 分钟
      var startTime = Date.now();
      while (!done && Date.now() - startTime < 300000) {
        try {
          java.lang.Thread.sleep(500);
        } catch (sleepErr) {
          // Thread interrupted when WS closes — exit loop
          break;
        }
      }

      if (!done) {
        logger.warn(TAG, "WS 等待超时");
      }
    } catch (e) {
      logger.error(TAG, "WS 连接异常: " + e.message);
    }

    return result;
  },

  /**
   * 获取当前配对令牌（用于外部轮询）
   * @returns {string|null}
   */
  getPairingToken: function () {
    return this._pairingToken;
  },

  /**
   * 清除配对信息（用于重新配对）
   */
  clear: function () {
    var storage = storages.create(STORAGE_KEY);
    storage.remove("device_secret");
    storage.remove("server_url");
    this._pairingToken = null;
    this._serverUrl = null;
    logger.info(TAG, "配对信息已清除");
  },
};

module.exports = pairing;
