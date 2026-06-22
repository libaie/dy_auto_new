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
  collect: require("../handlers/search-collect"),
};

var taskExecutor = {
  _currentTaskId: null,
  _currentLeaseId: null,
  _currentAccountId: null,
  _nextOpIndex: 0,
  _cancelled: false,

  /**
   * 标记当前任务为已取消
   * @param {string} taskId
   */
  // 入参：taskId 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 cancel 对应业务流程的处理结果。
  cancel: function (taskId) {
    if (this._currentTaskId === taskId) {
      this._cancelled = true;
      logger.info(TAG, "任务取消标记已设置: " + taskId);
    }
  },

  /**
   * 当前任务是否已被取消
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 isCancelled 对应业务流程的处理结果。
  isCancelled: function () {
    return this._cancelled;
  },

  /**
   * 获取当前 task_id（供 apiClient 上报使用）
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 getCurrentTaskId 对应业务流程的处理结果。
  getCurrentTaskId: function () {
    return this._currentTaskId;
  },

  /**
   * 获取当前 lease_id（供 apiClient 上报使用）
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 getCurrentLeaseId 对应业务流程的处理结果。
  getCurrentLeaseId: function () {
    return this._currentLeaseId;
  },

  /**
   * 获取下一个幂等操作序号（供 stats 上报使用）
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 getNextOpIndex 对应业务流程的处理结果。
  getNextOpIndex: function () {
    return this._nextOpIndex++;
  },

  /**
   * 获取当前 account_id（供 stats 上报使用）
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 getCurrentAccountId 对应业务流程的处理结果。
  getCurrentAccountId: function () {
    return this._currentAccountId;
  },

  // 设备业务函数：处理 execute 对应的抖音自动化动作、状态或安全边界。
  // 入参：task 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 execute 对应业务流程的处理结果。
  execute: function (task) {
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
    this._cancelled = false;
    task.params.task_id = task.id;  // 注入任务 ID 供 handler 上报进度
    task.params.account_id = task.account_id;  // 注入账号 ID 供 handler 使用

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
      this._currentLeaseId = null;
      this._currentAccountId = null;
      this._nextOpIndex = 0;

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
      this._currentLeaseId = null;
      this._currentAccountId = null;
      this._nextOpIndex = 0;
      logger.error(TAG, "任务 " + task.id + " 异常: " + e.message);
      return { status: "failed", result: { error: e.message } };
    }
  },

  /**
   * 注册新的 handler
   * @param {string} type
   * @param {Object} handler
   */
  // 入参：type、handler 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 registerHandler 对应业务流程的处理结果。
  registerHandler: function (type, handler) {
    handlers[type] = handler;
  },
};

module.exports = taskExecutor;
