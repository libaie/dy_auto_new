// device/core/task-executor.js
var apiClient = require("./api-client");
var selectorLoader = require("./selector-loader");
var logger = require("../utils/logger");
var taskCancellation = require("./task-cancellation");
var taskTimeout = require("./task-timeout");

var TAG = "任务执行";

// Handler 注册表
var handlers = {
  nurture: require("../handlers/nurture"),
  search_comment: require("../handlers/search-comment"),
  search_like: require("../handlers/search-like"),
  search_dm: require("../handlers/search-dm"),
  reply_comment: require("../handlers/reply-comment"),
  collect: require("../handlers/search-collect"),
};

var taskExecutor = {
  _currentTaskId: null,
  _currentLeaseId: null,
  _currentAccountId: null,
  _nextOpIndex: 0,

  /**
   * 标记当前任务为已取消
   * @param {string} taskId
   */
  cancel: function (taskId, leaseId) {
    if (this._currentTaskId === taskId &&
        (arguments.length < 2 || this._currentLeaseId === (leaseId || null))) {
      taskCancellation.cancel();
      logger.info(TAG, "任务取消标记已设置: " + taskId);
    }
  },

  /**
   * 当前任务是否已被取消
   */
  isCancelled: function () {
    return taskCancellation.isCancelled();
  },

  /**
   * 获取当前 task_id（供 apiClient 上报使用）
   */
  getCurrentTaskId: function () {
    return this._currentTaskId;
  },

  /**
   * 获取当前 lease_id（供 apiClient 上报使用）
   */
  getCurrentLeaseId: function () {
    return this._currentLeaseId;
  },

  /**
   * 获取下一个幂等操作序号（供 stats 上报使用）
   */
  getNextOpIndex: function () {
    return this._nextOpIndex++;
  },

  /**
   * 获取当前 account_id（供 stats 上报使用）
   */
  getCurrentAccountId: function () {
    return this._currentAccountId;
  },

  execute: function (task, cancellationToken) {
    logger.info(TAG, "执行任务: " + task.id + " 类型=" + task.type);

    var handler = handlers[task.type];
    if (!handler) {
      logger.error(TAG, "未找到任务类型处理器: " + task.type);
      return { status: "failed", result: { error: "Unknown task type: " + task.type } };
    }

    this._currentTaskId = task.id;
    this._currentLeaseId = task.lease_id || null;
    this._currentAccountId = task.account_id || null;
    this._nextOpIndex = 0;
    var execution = taskCancellation.reset(cancellationToken);
    var requestSession = apiClient.beginTaskSession(execution.apiSession);
    task.params.task_id = task.id;  // 注入任务 ID 供 handler 上报进度
    task.params.account_id = task.account_id;  // 注入账号 ID 供 handler 使用

    // 与 main.js 使用相同的任务期限，长养号任务包含配置时长和缓冲。
    var TASK_TIMEOUT = taskTimeout.getTaskTimeoutMs(task);
    var startTime = Date.now();
    var timedOut = false;
    var watchdog = setInterval(function () {
      if (execution.cancelled) {
        logger.info(TAG, "任务 " + task.id + " 已被取消");
        return;
      }
      if (Date.now() - startTime > TASK_TIMEOUT) {
        logger.error(TAG, "任务 " + task.id + " 执行超时（" + (TASK_TIMEOUT / 60000) + "分钟）");
        timedOut = true;
        execution.cancelled = true;
      }
    }, 10000);

    try {
      if (this.isCancelled() || !apiClient.isCurrentSession(requestSession)) {
        return { status: "cancelled", result: { error: "Task cancelled before execution" } };
      }
      var crashRecovery = require("./crash-recovery");
      if (task.account_id) {
        crashRecovery.setAccountId(task.account_id);
      }

      var result = handler.execute(task.params);

      if (timedOut || Date.now() - startTime > TASK_TIMEOUT) {
        return { status: "failed", result: { error: "Task execution timed out (" + (TASK_TIMEOUT / 60000) + " min)" } };
      }

      if (this.isCancelled()) {
        return { status: "cancelled", result: { error: "Task cancelled by server" } };
      }

      if (result.success) {
        logger.info(TAG, "任务 " + task.id + " 执行成功");
        return { status: "completed", result: result.result };
      } else {
        logger.warn(TAG, "任务 " + task.id + " 执行失败: " + result.error);
        return { status: "failed", result: { error: result.error } };
      }
    } catch (e) {
      if (this.isCancelled()) {
        return { status: "cancelled", result: { error: "Task cancelled by server" } };
      }
      logger.error(TAG, "任务 " + task.id + " 异常: " + e.message);
      return { status: "failed", result: { error: e.message } };
    } finally {
      clearInterval(watchdog);
      apiClient.endTaskSession(requestSession);
      this._currentTaskId = null;
      this._currentLeaseId = null;
      this._currentAccountId = null;
      this._nextOpIndex = 0;
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
