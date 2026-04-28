// device/main.js
var config = require("./config");
var apiClient = require("./core/api-client");
var selectorLoader = require("./core/selector-loader");
var taskExecutor = require("./core/task-executor");
var logger = require("./utils/logger");
var updateChecker = require("./core/update-checker");
var crashRecovery = require("./core/crash-recovery");
var antiDetect = require("./core/anti-detect");

var TAG = "MAIN";

/**
 * 主循环
 */
function main() {
  logger.info(TAG, "=== 抖音自动化助手 启动 ===");
  logger.info(TAG, "Device ID: " + config.deviceId);
  logger.info(TAG, "Server: " + config.serverUrl);
  logger.info(TAG, "Poll interval: " + config.pollInterval + "ms");

  // 检查脚本更新（启动时检查一次）
  try {
    var updated = updateChecker.checkAndUpdate();
    if (updated) {
      logger.info(TAG, "Script updated, restart to use new version");
    }
  } catch (e) {
    logger.warn(TAG, "Update check failed: " + e.message);
  }

  // 设备注册（首次启动或重启后）
  try {
    var deviceInfo = {
      device_id: config.deviceId,
      name: device.model + " (" + device.brand + ")",
      os_version: device.release,
      app_version: "1.0.0",
    };
    var regResult = apiClient.register(deviceInfo);
    if (regResult) {
      logger.info(TAG, "Device registered: " + JSON.stringify(regResult));
    } else {
      logger.warn(TAG, "Device registration failed, continuing anyway");
    }
  } catch (e) {
    logger.warn(TAG, "Registration error: " + e.message);
  }

  // 初始化选择器
  selectorLoader.init();

  // 启动心跳定时器
  var heartbeatTimer = setInterval(function () {
    try {
      apiClient.heartbeat();
    } catch (e) {
      logger.warn(TAG, "Heartbeat failed: " + e.message);
    }
  }, config.heartbeatInterval);

  // 主轮询循环
  logger.info(TAG, "Starting main poll loop...");

  while (true) {
    try {
      // 健康检查
      if (!crashRecovery.healthCheck()) {
        logger.warn(TAG, "Health check failed, skipping this cycle");
        sleep(config.pollInterval);
        continue;
      }

      // 轮询任务
      var response = apiClient.poll();

      if (response) {
        // 应用代理配置
        if (response.proxy) {
          apiClient.setProxy(response.proxy);
        }

        // 更新反检测配置（仅版本变化时）
        if (response.anti_detect_config_version &&
            response.anti_detect_config_version !== config.antiDetectVersion) {
          if (response.anti_detect_config) {
            antiDetect.updateFromServer(response.anti_detect_config);
            config.antiDetectVersion = response.anti_detect_config_version;
          }
        }

        // 检查选择器版本
        if (response.selectors_version) {
          selectorLoader.checkAndUpdate(response.selectors_version);
        }

        // 执行任务
        if (response.task) {
          logger.info(TAG, "Got task: " + response.task.id + " (" + response.task.type + ")");

          var result = taskExecutor.execute(response.task);

          // 上报结果
          var uiSnapshot = null;
          if (result.status === "failed") {
            // 失败时附带控件树快照，用于分析选择器问题
            try {
              var uiOperator = require("./core/ui-operator");
              uiSnapshot = uiOperator.captureUISnapshot();
            } catch (e) {
              logger.warn(TAG, "Failed to capture UI snapshot: " + e.message);
            }
          }

          apiClient.report(response.task.id, result.status, result.result, uiSnapshot);
          logger.info(TAG, "Task result reported: " + result.status);
        } else {
          logger.debug(TAG, "No pending tasks");
        }
      }
    } catch (e) {
      logger.error(TAG, "Main loop error: " + e.message);
    }

    // 等待下次轮询
    sleep(config.pollInterval);
  }
}

// 启动
main();
