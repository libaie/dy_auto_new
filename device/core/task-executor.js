// device/core/task-executor.js
var apiClient = require("./api-client");
var selectorLoader = require("./selector-loader");
var logger = require("../utils/logger");

var TAG = "EXECUTOR";

// Handler 注册表
var handlers = {
  nurture: require("../handlers/nurture"),
};

var taskExecutor = {
  execute: function (task) {
    logger.info(TAG, "Executing task: " + task.id + " type=" + task.type);

    var handler = handlers[task.type];
    if (!handler) {
      logger.error(TAG, "No handler for task type: " + task.type);
      return { status: "failed", result: { error: "Unknown task type: " + task.type } };
    }

    // 看门狗：任务最大执行时间 30 分钟
    var TASK_TIMEOUT = 30 * 60 * 1000;
    var startTime = Date.now();
    var timedOut = false;

    var watchdog = setInterval(function () {
      if (Date.now() - startTime > TASK_TIMEOUT) {
        logger.error(TAG, "Task " + task.id + " timed out after 30 minutes");
        timedOut = true;
      }
    }, 10000);

    try {
      var result = handler.execute(task.params);
      clearInterval(watchdog);

      if (timedOut) {
        return { status: "failed", result: { error: "Task execution timed out (30 min)" } };
      }

      if (result.success) {
        logger.info(TAG, "Task " + task.id + " completed successfully");
        return { status: "completed", result: result.result };
      } else {
        logger.warn(TAG, "Task " + task.id + " failed: " + result.error);
        return { status: "failed", result: { error: result.error } };
      }
    } catch (e) {
      clearInterval(watchdog);
      logger.error(TAG, "Task " + task.id + " threw exception: " + e.message);
      return { status: "failed", result: { error: e.message } };
    }
  },

  /**
   * 注册新的 handler
   * @param {string} type
   * @param {Object} handler
   */
  registerHandler: function (type, handler) {
    handlers[type] = handler;
  },
};

module.exports = taskExecutor;
