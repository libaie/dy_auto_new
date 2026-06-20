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
let findListCount = 0;
const commentItem = { id: "comment-1" };

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
    if (actionName !== "comment_list") return [];
    findListCount++;
    return [commentItem];
  },
  swipeUp() {
    swipeCount++;
  },
});
stub("core/ai-analyzer", {
  useTemplate() {},
  resolveDestination() { return null; },
  _localRelevanceCheck() { return null; },
  analyzeComment() { return { score: 0, reply: "skip" }; },
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
      nickname: "毛毛小阿姨",
      text: "有局吗",
      time: "刚刚",
      isAuthor: false,
    };
  },
  localPreFilter() { return true; },
  parseTime() { return new Date(); },
  openComments() { return true; },
});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});

const searchCollect = require("../handlers/search-collect");
const stats = { success_count: 0, fail_count: 0, details: [] };

searchCollect._processComments({ keyword: "德扑", count: 10, max_age_days: -1 }, stats, 0);

assert.strictEqual(stats.success_count, 0);
assert.strictEqual(swipeCount, 1, "duplicate-only comment screen should stop after one confirming swipe");
assert.strictEqual(findListCount, 2, "should inspect the repeated screen once, not five extra rounds");

console.log("search-collect-duplicate-screen.node-test passed");
