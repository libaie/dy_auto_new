const assert = require("assert");
const path = require("path");

global.device = { width: 1080, height: 2340 };
global.sleep = () => {};
global.press = () => false;

function stub(relativePath, exports) {
  const filename = require.resolve(path.join("..", relativePath));
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports,
  };
}

global.id = () => ({
  findOne() { return null; },
});
global.className = () => ({
  find() { return []; },
});

let clickedElement = null;
const coordinateElement = { isCoordinate: true, x: 321, y: 654 };

stub("handlers/base-handler", {
  ensureAppActive() { return true; },
  safeClick() { return true; },
  safeInput() { return true; },
  submitViaKeyboard() { return true; },
});
stub("core/ui-operator", {
  findElements(actionName) {
    return actionName === "search_video_list" ? [coordinateElement] : [];
  },
  clickElement(el) {
    clickedElement = el;
    return true;
  },
  swipeUp() {
    throw new Error("should not scroll when coordinate result is clickable");
  },
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

const searchBase = require("../handlers/search-base");

assert.strictEqual(searchBase._clickSearchResult(0), true);
assert.strictEqual(clickedElement, coordinateElement);

console.log("search-result-coordinate.node-test passed");
