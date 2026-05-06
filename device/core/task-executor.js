// device/core/task-executor.js
var apiClient = require("./api-client");
var selectorLoader = require("./selector-loader");
var logger = require("../utils/logger");

var TAG = "任务执行";

// Handler 注册表
var handlers = {
  nurture: require("../handlers/nurture"),
  search_comment: require("../handlers/search-comment"),
  search_like: require("../handlers/search-like"),
  search_dm: require("../handlers/search-dm"),
  reply_comment: require("../handlers/reply-comment"),
};

var taskExecutor = {
  _currentTaskId: null,
  _cancelled: false,

  /**
   * 标记当前任务为已取消
   * @param {string} taskId
   */
  cancel: function (taskId) {
    if (this._currentTaskId === taskId) {
      this._cancelled = true;
      logger.info(TAG, "任务取消标记已设置: " + taskId);
    }
  },

  /**
   * 当前任务是否已被取消
   */
  isCancelled: function () {
    return this._cancelled;
  },

  execute: function (task) {
    logger.info(TAG, "执行任务: " + task.id + " 类型=" + task.type);

    var handler = handlers[task.type];
    if (!handler) {
      logger.error(TAG, "未找到任务类型处理器: " + task.type);
      return { status: "failed", result: { error: "Unknown task type: " + task.type } };
    }

    this._currentTaskId = task.id;
    this._cancelled = false;
    task.params.task_id = task.id;  // 注入任务 ID 供 handler 上报进度

    // 看门狗：任务最大执行时间 30 分钟，同时检查取消标记
    var TASK_TIMEOUT = 30 * 60 * 1000;
    var startTime = Date.now();
    var timedOut = false;
    var self = this;

    var watchdog = setInterval(function () {
      if (self._cancelled) {
        logger.info(TAG, "任务 " + task.id + " 已被取消");
        return;
      }
      if (Date.now() - startTime > TASK_TIMEOUT) {
        logger.error(TAG, "任务 " + task.id + " 执行超时（30分钟）");
        timedOut = true;
      }
    }, 10000);

    try {
      var crashRecovery = require("./crash-recovery");
      if (task.account_id) {
        crashRecovery.setAccountId(task.account_id);
      }

      var result = handler.execute(task.params);
      clearInterval(watchdog);

      this._currentTaskId = null;

      if (this._cancelled) {
        return { status: "cancelled", result: { error: "Task cancelled by server" } };
      }

      if (timedOut) {
        return { status: "failed", result: { error: "Task execution timed out (30 min)" } };
      }

      if (result.success) {
        logger.info(TAG, "任务 " + task.id + " 执行成功");
        return { status: "completed", result: result.result };
      } else {
        logger.warn(TAG, "任务 " + task.id + " 执行失败: " + result.error);
        return { status: "failed", result: { error: result.error } };
      }
    } catch (e) {
      clearInterval(watchdog);
      this._currentTaskId = null;
      logger.error(TAG, "任务 " + task.id + " 异常: " + e.message);
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
