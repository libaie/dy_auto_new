const assert = require("assert");
const path = require("path");

global.device = { width: 1080, height: 2340 };
global.sleep = () => {};
global.back = () => {};
global.press = () => true;

function stub(relativePath, exports) {
  const filename = require.resolve(path.join("..", relativePath));
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports,
  };
}

let collectOptions = null;

stub("handlers/base-handler", {
  ensureAppActive() { return true; },
  safeClick() { return true; },
  safeInput() { return true; },
  submitViaKeyboard() { return true; },
});
stub("core/ui-operator", {
  isOnPage() { return false; },
  waitForPage() { return true; },
  findElement() { return null; },
  findElements() { return []; },
});
stub("core/ai-analyzer", {
  useTemplate() {},
  resolveDestination() { return null; },
});
stub("core/api-client", {
  reportProgress() {},
  uploadUserAvatar() {},
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
  _cropCircularAvatar() { return ""; },
  collectProfileData(options) {
    collectOptions = options;
    return { nickname: options.fallbackNickname, douyin_id: "" };
  },
});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});

const avatarEl = {
  isImage: false,
  isCoordinate: false,
  clickable() { return false; },
  bounds() {
    return {
      centerX() { return 300; },
      centerY() { return 400; },
    };
  },
};

const searchCollect = require("../handlers/search-collect");
searchCollect._findChildBySelector = function (_item, actionName) {
  return actionName === "comment_author_avatar" ? avatarEl : null;
};

const data = searchCollect._collectUserData({}, { nickname: "犇馆强子" });

assert.deepStrictEqual(data, { nickname: "犇馆强子", douyin_id: "" });
assert.ok(collectOptions);
assert.strictEqual(collectOptions.fallbackNickname, "犇馆强子");

console.log("search-collect-user-fallback.node-test passed");
