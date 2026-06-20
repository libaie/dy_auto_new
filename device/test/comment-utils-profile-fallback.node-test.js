const assert = require("assert");
const path = require("path");

function stub(relativePath, exports) {
  const filename = require.resolve(path.join("..", relativePath));
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports,
  };
}

stub("core/ui-operator", {
  findElement() { return null; },
});
stub("core/selector-loader", {
  get() { return null; },
});
stub("core/selector-resolver", {});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});

const commentUtils = require("../handlers/comment-utils");

const data = commentUtils.collectProfileData({ fallbackNickname: "犇馆强子" });

assert.ok(data, "profile data should not be null when comment nickname is available");
assert.strictEqual(data.nickname, "犇馆强子");
assert.strictEqual(data.douyin_id, "");

console.log("comment-utils-profile-fallback.node-test passed");
