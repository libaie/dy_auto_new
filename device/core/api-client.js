var config = require("../config");
var logger = require("../utils/logger");

var TAG = "API";

var apiClient = {
  /**
   * 发送 HTTP GET 请求
   * @param {string} path - API 路径 (如 "/api/device/poll")
   * @param {Object} params - 查询参数
   * @returns {Object|null} 响应 JSON 或 null
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

    try {
      var response = http.get(url, {
        headers: { "X-Device-Secret": config.deviceSecret },
        timeout: 10000,
      });

      if (response.statusCode === 200) {
        return JSON.parse(response.body);
      } else {
        logger.error(TAG, "GET " + path + " failed: " + response.statusCode + " " + response.body);
        return null;
      }
    } catch (e) {
      logger.error(TAG, "GET " + path + " error: " + e.message);
      return null;
    }
  },

  /**
   * 发送 HTTP POST 请求
   * @param {string} path - API 路径
   * @param {Object} body - 请求体
   * @returns {Object|null} 响应 JSON 或 null
   */
  post: function (path, body) {
    var url = config.serverUrl + path;

    try {
      var response = http.post(url, {
        headers: {
          "Content-Type": "application/json",
          "X-Device-Secret": config.deviceSecret,
        },
        body: JSON.stringify(body),
        timeout: 10000,
      });

      if (response.statusCode === 200) {
        return JSON.parse(response.body);
      } else {
        logger.error(TAG, "POST " + path + " failed: " + response.statusCode + " " + response.body);
        return null;
      }
    } catch (e) {
      logger.error(TAG, "POST " + path + " error: " + e.message);
      return null;
    }
  },

  /**
   * 轮询任务
   * @returns {Object|null} poll response
   */
  poll: function () {
    return this.get("/api/device/poll", { device_id: config.deviceId });
  },

  /**
   * 上报任务结果
   * @param {string} taskId
   * @param {string} status - "completed" | "failed"
   * @param {Object} result
   * @param {Object} uiSnapshot
   * @returns {Object|null}
   */
  report: function (taskId, status, result, uiSnapshot) {
    return this.post("/api/device/report", {
      task_id: taskId,
      status: status,
      result: result || {},
      ui_snapshot: uiSnapshot || null,
    });
  },

  /**
   * 发送心跳
   */
  heartbeat: function () {
    this.post("/api/device/heartbeat?device_id=" + config.deviceId, {});
  },

  /**
   * 获取选择器配置
   * @param {number} currentVersion - 本地缓存版本号
   * @returns {Object|null}
   */
  fetchSelectors: function (currentVersion) {
    return this.get("/api/device/selectors", {
      version: currentVersion || 0,
    });
  },
};

module.exports = apiClient;
