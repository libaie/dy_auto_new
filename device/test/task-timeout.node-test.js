const assert = require("assert");

const taskTimeout = require("../core/task-timeout");

assert.strictEqual(
  taskTimeout.getTaskTimeoutMs({ type: "search_like", params: { count: 3 } }),
  10 * 60 * 1000
);

assert.strictEqual(
  taskTimeout.getTaskTimeoutMs({ type: "nurture", params: { duration: 30 } }),
  32 * 60 * 1000
);

assert.strictEqual(
  taskTimeout.getTaskTimeoutMs({ type: "nurture", params: {} }),
  32 * 60 * 1000
);

console.log("task-timeout.node-test passed");
