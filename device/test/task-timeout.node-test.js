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

assert.strictEqual(
  taskTimeout.getTaskTimeoutMs({ type: "nurture", params: { sub_tasks: [{ type: "browse", count: 1 }] } }),
  62 * 60 * 1000
);

for (const duration of [0, -1, "invalid", true, false, [5], {}]) {
  assert.strictEqual(
    taskTimeout.getTaskTimeoutMs({ type: "nurture", params: { duration, sub_tasks: [] } }),
    62 * 60 * 1000
  );
}

console.log("task-timeout.node-test passed");
