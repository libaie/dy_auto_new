var config = require("../config");

var LOG_LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };

var logger = {
  _level: LOG_LEVELS[config.logLevel] || 0,

  _log: function (level, tag, msg) {
    if (LOG_LEVELS[level] >= this._level) {
      var timestamp = new Date().toISOString();
      var prefix = "[" + timestamp + "] [" + level.toUpperCase() + "] [" + tag + "]";
      console.log(prefix + " " + msg);
    }
  },

  debug: function (tag, msg) { this._log("debug", tag, msg); },
  info: function (tag, msg) { this._log("info", tag, msg); },
  warn: function (tag, msg) { this._log("warn", tag, msg); },
  error: function (tag, msg) { this._log("error", tag, msg); },
};

module.exports = logger;
