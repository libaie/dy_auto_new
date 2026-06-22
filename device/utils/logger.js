// 设备日志工具，统一输出任务、设备动作和错误诊断信息。
var config = global.__config || require("../config");

var LOG_LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
var LOG_LEVEL_NAMES = { debug: "调试", info: "信息", warn: "警告", error: "错误" };

var logger = {
  _level: LOG_LEVELS[config.logLevel] || 0,
  _history: [],       // 日志历史（供悬浮窗显示）
  _maxHistory: 200,   // 最大历史条数
  _listeners: [],     // 日志更新监听器

  // 入参：level、tag、msg 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 _log 对应业务流程的处理结果。
  _log: function (level, tag, msg) {
    if (LOG_LEVELS[level] >= this._level) {
      var now = new Date();
      var timestamp = now.toLocaleTimeString();
      var levelName = LOG_LEVEL_NAMES[level] || level;
      var prefix = "[" + timestamp + "] [" + levelName + "] [" + tag + "]";
      var fullMsg = prefix + " " + msg;

      console.log(fullMsg);

      // 保存到历史
      this._history.push({
        time: timestamp,
        level: level,
        levelName: levelName,
        tag: tag,
        message: msg,
        full: fullMsg,
      });

      // 限制历史长度
      if (this._history.length > this._maxHistory) {
        this._history.shift();
      }

      // 通知监听器
      for (var i = 0; i < this._listeners.length; i++) {
        try {
          this._listeners[i](level, tag, msg);
        } catch (e) {
          // 忽略监听器错误
        }
      }
    }
  },

  // 设备业务函数：处理 debug 对应的抖音自动化动作、状态或安全边界。
  // 入参：tag、msg 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 debug 对应业务流程的处理结果。
  debug: function (tag, msg) { this._log("debug", tag, msg); },
  // 设备业务函数：处理 info 对应的抖音自动化动作、状态或安全边界。
  // 入参：tag、msg 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 info 对应业务流程的处理结果。
  info: function (tag, msg) { this._log("info", tag, msg); },
  // 设备业务函数：处理 warn 对应的抖音自动化动作、状态或安全边界。
  // 入参：tag、msg 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 warn 对应业务流程的处理结果。
  warn: function (tag, msg) { this._log("warn", tag, msg); },
  // 设备业务函数：处理 error 对应的抖音自动化动作、状态或安全边界。
  // 入参：tag、msg 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 error 对应业务流程的处理结果。
  error: function (tag, msg) { this._log("error", tag, msg); },

  /**
   * 获取日志历史
   * @param {number} count - 获取最近 N 条
   * @returns {Array}
   */
  // 入参：count 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 getHistory 对应业务流程的处理结果。
  getHistory: function (count) {
    count = count || 50;
    return this._history.slice(-count);
  },

  /**
   * 添加日志监听器
   * @param {Function} callback - function(level, tag, msg)
   */
  // 入参：callback 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 addListener 对应业务流程的处理结果。
  addListener: function (callback) {
    this._listeners.push(callback);
  },

  /**
   * 移除日志监听器
   * @param {Function} callback
   */
  // 入参：callback 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 removeListener 对应业务流程的处理结果。
  removeListener: function (callback) {
    var idx = this._listeners.indexOf(callback);
    if (idx !== -1) {
      this._listeners.splice(idx, 1);
    }
  },

  /**
   * 清空日志历史
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 clearHistory 对应业务流程的处理结果。
  clearHistory: function () {
    this._history = [];
  },
};

module.exports = logger;
