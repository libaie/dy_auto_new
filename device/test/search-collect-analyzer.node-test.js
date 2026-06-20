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

const analyzerCalls = [];

stub("handlers/base-handler", {
  ensureAppActive() { return true; },
  safeClick() { return true; },
  safeInput() { return true; },
  submitViaKeyboard() { return true; },
});
stub("core/ui-operator", {
  isOnPage() { return false; },
  findElement() { return null; },
  findElements() { return []; },
});
stub("core/ai-analyzer", {
  useTemplate(id, fallbackIndustry) {
    analyzerCalls.push(["useTemplate", id, fallbackIndustry]);
  },
  resolveDestination() { return null; },
});
stub("core/api-client", {
  reportProgress() {},
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
  preCheckCommentCount() { return { count: 0, rawDesc: "" }; },
  openComments() { return false; },
});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});

const searchCollect = require("../handlers/search-collect");

analyzerCalls.length = 0;
searchCollect._prepareAnalyzer({});
assert.deepStrictEqual(analyzerCalls, [["useTemplate", undefined, "general"]]);

analyzerCalls.length = 0;
searchCollect._prepareAnalyzer({ prompt_template_id: "prompt-1" });
assert.deepStrictEqual(analyzerCalls, [["useTemplate", "prompt-1", "general"]]);

console.log("search-collect-analyzer.node-test passed");
