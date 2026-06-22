// 任务超时控制模块，负责限制单个设备任务的最长执行时间。
var DEFAULT_TASK_TIMEOUT_MS = 10 * 60 * 1000;
var NURTURE_TIMEOUT_BUFFER_MS = 2 * 60 * 1000;

// 入参：value、fallback 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 _positiveNumber 对应业务流程的处理结果。
function _positiveNumber(value, fallback) {
  var n = Number(value);
  if (!isFinite(n) || n <= 0) return fallback;
  return n;
}

// 设备业务函数：处理 getTaskTimeoutMs 对应的抖音自动化动作、状态或安全边界。
// 入参：task 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getTaskTimeoutMs 对应业务流程的处理结果。
function getTaskTimeoutMs(task) {
  task = task || {};
  var params = task.params || {};
  if (task.type === "nurture") {
    var durationMinutes = _positiveNumber(params.duration, 30);
    return Math.max(DEFAULT_TASK_TIMEOUT_MS, durationMinutes * 60 * 1000 + NURTURE_TIMEOUT_BUFFER_MS);
  }
  return DEFAULT_TASK_TIMEOUT_MS;
}

module.exports = {
  DEFAULT_TASK_TIMEOUT_MS: DEFAULT_TASK_TIMEOUT_MS,
  NURTURE_TIMEOUT_BUFFER_MS: NURTURE_TIMEOUT_BUFFER_MS,
  getTaskTimeoutMs: getTaskTimeoutMs,
};
