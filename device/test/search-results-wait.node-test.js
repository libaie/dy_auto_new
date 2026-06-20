const assert = require("assert");
const path = require("path");

let now = 0;
global.sleep = (ms) => { now += Number(ms || 0); };
global.device = { width: 1080, height: 2340 };
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

stub("handlers/base-handler", {
  ensureAppActive() { return true; },
  safeClick() { return true; },
  safeInput() { return true; },
  submitViaKeyboard() { return true; },
});
stub("core/ui-operator", {
  isOnPage(actionName) {
    return actionName === "is_search_view";
  },
  waitForElement() { return null; },
  waitForPage() { return false; },
  findElement() { return null; },
  findElements() { return []; },
  swipeUp() {},
});
stub("core/anti-detect", {
  wrapAction(_name, fn) { return fn(); },
  maybePause() {},
});
stub("core/ai-analyzer", {
  useTemplate() {},
  resolveDestination() { return null; },
});
stub("core/flow-context", {
  enter() {},
  reset() {},
});
stub("core/task-executor", {
  isCancelled() { return false; },
});
stub("core/api-client", {
  reportProgress() {},
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

function prepareSearchHandler(handler, events) {
  handler._openSearch = function () {
    events.push("openSearch");
    return true;
  };
  handler._inputKeyword = function () {
    events.push("inputKeyword");
    return true;
  };
  handler._clickSuggestion = function () {
    events.push("clickSuggestion");
    return true;
  };
  handler._clickVideoTab = function () {
    events.push("clickVideoTab");
    return true;
  };
  handler._clickSearchResult = function () {
    events.push("clickSearchResult");
    return true;
  };
}

{
  now = 0;
  const events = [];
  const searchBase = require("../handlers/search-base");
  prepareSearchHandler(searchBase, events);

  const result = searchBase.execute({ keyword: "杭州旅游", count: 1 });

  assert.strictEqual(result.success, false);
  assert.match(result.error, /搜索结果页/);
  assert.ok(!events.includes("clickVideoTab"));
  assert.ok(!events.includes("clickSearchResult"));
}

{
  now = 0;
  const events = [];
  const searchCollect = require("../handlers/search-collect");
  prepareSearchHandler(searchCollect, events);

  const result = searchCollect.execute({ keyword: "杭州旅游", video_count: 1, count: 1 });

  assert.strictEqual(result.success, false);
  assert.match(result.error, /搜索结果页/);
  assert.ok(!events.includes("clickVideoTab"));
  assert.ok(!events.includes("clickSearchResult"));
}

console.log("search-results-wait.node-test passed");
