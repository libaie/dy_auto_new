const assert = require("assert");
const path = require("path");

const originalNow = Date.now;
let now = 0;
Date.now = () => now;
global.sleep = (ms) => { now += Number(ms || 0); };

function stub(relativePath, exports) {
  const filename = require.resolve(path.join("..", relativePath));
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports,
  };
}

const statCalls = [];

stub("handlers/base-handler", {
  ensureAppActive() { return true; },
  safeClick() { return true; },
  safeInput() { return true; },
  submitViaKeyboard() { return true; },
  _extractVideoText() { return "health text"; },
});
stub("core/ui-operator", {
  isOnPage() { return true; },
  findElement() { return null; },
  clickElement() { return true; },
});
stub("core/anti-detect", {
  humanSwipeUp() { now += 1000; },
  wrapAction(_name, fn) { return fn(); },
});
stub("core/ai-analyzer", {
  useTemplate() {},
  checkHealthRelevance() { return true; },
  generateVideoComment() { return "comment"; },
  _callAI() { return '{"related": true}'; },
});
stub("handlers/comment-utils", {
  preCheckCommentCount() { return { count: 1, rawDesc: "1" }; },
});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});
stub("core/flow-context", {
  enter() {},
});
stub("core/task-executor", {
  isCancelled() { return false; },
  getCurrentTaskId() { return "task-1"; },
  getCurrentAccountId() { return "acc-1"; },
  getNextOpIndex() { return statCalls.length + 1; },
});
stub("core/api-client", {
  incrementStats(accountId, taskType, targetId, count) {
    statCalls.push([accountId, taskType, targetId, count]);
    return true;
  },
});

const nurture = require("../handlers/nurture");
nurture._ensureOnFeed = function () {};

{
  now = 0;
  statCalls.length = 0;
  nurture._likeCurrentVideo = function () { return false; };

  const result = nurture._executeV2({
    account_id: "acc-1",
    duration: 0.01,
    completion_mode: "all",
    sub_tasks: [{ type: "like", count: 1 }],
  });

  assert.strictEqual(result.result.like.done, 0);
  assert.strictEqual(result.result.success_count, 0);
  assert.deepStrictEqual(statCalls, []);
}

{
  now = 0;
  statCalls.length = 0;
  nurture._likeCurrentVideo = function () { return true; };

  const result = nurture._executeV2({
    account_id: "acc-1",
    duration: 0.01,
    completion_mode: "all",
    sub_tasks: [{ type: "like", count: 1 }],
  });

  assert.strictEqual(result.result.like.done, 1);
  assert.strictEqual(result.result.success_count, 1);
  assert.deepStrictEqual(statCalls, [["acc-1", "nurture", "", 1]]);
}

Date.now = originalNow;
console.log("nurture.node-test passed");
