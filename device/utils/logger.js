// 设备日志工具，统一输出任务、设备动作和错误诊断信息。
var config = global.__config || require("../config");

var LOG_LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
var LOG_LEVEL_NAMES = { debug: "调试", info: "信息", warn: "警告", error: "错误" };

var logger = {
  _level: LOG_LEVELS[config.logLevel] || 0,
  _history: [],       // 日志历史（供悬浮窗显示）
  _maxHistory: 200,   // 最大历史条数
  _listeners: [],     // 日志更新监听器

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

  debug: function (tag, msg) { this._log("debug", tag, msg); },
  info: function (tag, msg) { this._log("info", tag, msg); },
  warn: function (tag, msg) { this._log("warn", tag, msg); },
  error: function (tag, msg) { this._log("error", tag, msg); },

  /**
   * 获取日志历史
   * @param {number} count - 获取最近 N 条
   * @returns {Array}
   */
  getHistory: function (count) {
    count = count || 50;
    return this._history.slice(-count);
  },

  /**
   * 添加日志监听器
   * @param {Function} callback - function(level, tag, msg)
   */
  addListener: function (callback) {
    this._listeners.push(callback);
  },

  /**
   * 移除日志监听器
   * @param {Function} callback
   */
  removeListener: function (callback) {
    var idx = this._listeners.indexOf(callback);
    if (idx !== -1) {
      this._listeners.splice(idx, 1);
    }
  },

  /**
   * 清空日志历史
   */
  clearHistory: function () {
    this._history = [];
  },
};

module.exports = logger;
