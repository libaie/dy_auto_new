const assert = require("assert");
const path = require("path");

global.device = { width: 1080, height: 2340 };
global.sleep = () => {};
global.back = () => {};

function stub(relativePath, exports) {
  const filename = require.resolve(path.join("..", relativePath));
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports,
  };
}

let swipeCount = 0;
let infoLogs = [];
const commentItem = { id: "old-comment" };

stub("handlers/base-handler", {
  ensureAppActive() { return true; },
  safeClick() { return true; },
  safeInput() { return true; },
  submitViaKeyboard() { return true; },
});
stub("core/ui-operator", {
  isOnPage() { return false; },
  findElement() { return null; },
  findElements(actionName) {
    return actionName === "comment_list" ? [commentItem] : [];
  },
  swipeUp() {
    swipeCount++;
  },
});
stub("core/ai-analyzer", {
  useTemplate() {},
  resolveDestination() { return null; },
  _localRelevanceCheck() { return null; },
  analyzeComment() {
    throw new Error("old comments should not reach AI analysis");
  },
});
stub("core/api-client", {
  reportProgress() {},
  collectReport() { return {}; },
  incrementStats() {},
});
stub("core/anti-detect", {
  maybePause() {},
});
stub("core/flow-context", {
  enter() {},
  reset() {},
});
stub("core/task-executor", {
  isCancelled() { return false; },
});
stub("handlers/comment-utils", {
  parseCommentItem() {
    return {
      nickname: "过期评论用户",
      text: "这是足够长的评论",
      time: "2天前",
      isAuthor: false,
    };
  },
  localPreFilter() { return true; },
  parseTime() {
    return new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
  },
  openComments() { return true; },
});
stub("utils/logger", {
  info(_tag, msg) { infoLogs.push(msg); },
  warn() {},
  error() {},
  debug() {},
});

const searchCollect = require("../handlers/search-collect");
const stats = { success_count: 0, fail_count: 0, details: [] };

assert.doesNotThrow(() => {
  searchCollect._processComments({ keyword: "德扑", count: 10, max_age_days: 1 }, stats, 0);
});

assert.strictEqual(stats.success_count, 0);
assert.strictEqual(swipeCount, 5);
assert.ok(infoLogs.some((line) => line.indexOf("连续 5 轮评论日期均超过 1 天") !== -1));

console.log("search-collect-old-comments.node-test passed");
