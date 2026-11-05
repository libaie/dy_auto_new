// device/core/task-timeout.js

var DEFAULT_TASK_TIMEOUT_MS = 10 * 60 * 1000;
var NURTURE_TIMEOUT_BUFFER_MS = 2 * 60 * 1000;

function _positiveNumber(value, fallback) {
  if (typeof value !== "number" && typeof value !== "string") return fallback;
  var n = Number(value);
  if (!isFinite(n) || n <= 0) return fallback;
  return n;
}

function getNurtureDurationMinutes(params) {
  params = params || {};
  return _positiveNumber(params.duration, params.sub_tasks instanceof Array ? 60 : 30);
}

function getTaskTimeoutMs(task) {
  task = task || {};
  var params = task.params || {};
  if (task.type === "nurture") {
    var durationMinutes = getNurtureDurationMinutes(params);
    return Math.max(DEFAULT_TASK_TIMEOUT_MS, durationMinutes * 60 * 1000 + NURTURE_TIMEOUT_BUFFER_MS);
  }
  return DEFAULT_TASK_TIMEOUT_MS;
}

module.exports = {
  DEFAULT_TASK_TIMEOUT_MS: DEFAULT_TASK_TIMEOUT_MS,
  NURTURE_TIMEOUT_BUFFER_MS: NURTURE_TIMEOUT_BUFFER_MS,
  getNurtureDurationMinutes: getNurtureDurationMinutes,
  getTaskTimeoutMs: getTaskTimeoutMs,
};
