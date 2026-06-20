const assert = require("assert");
const path = require("path");

const originalNow = Date.now;
let now = 0;
Date.now = () => now;

global.sleep = (ms) => { now += Number(ms || 0); };
global.device = { width: 1080, height: 2340 };

function stub(relativePath, exports) {
  const filename = require.resolve(path.join("..", relativePath));
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports,
  };
}

function finder() {
  return {
    find() { return []; },
  };
}

global.text = () => finder();
global.textContains = () => finder();
global.id = () => finder();
global.idContains = () => finder();
global.desc = () => finder();
global.descContains = () => finder();
global.className = () => finder();
global.classNameContains = () => finder();

stub("core/selector-loader", {
  get(actionName) {
    if (actionName !== "comment_list") return null;
    return {
      strategies: [
        { type: "text", value: "never-found", priority: 1 },
      ],
    };
  },
});
stub("core/api-client", {});

let warnCount = 0;
stub("utils/logger", {
  info() {},
  warn() { warnCount++; },
  error() {},
  debug() {},
});

const uiOperator = require("../core/ui-operator");

now = 0;
warnCount = 0;
assert.deepStrictEqual(uiOperator.findElements("comment_list", 10, true), []);
assert.strictEqual(warnCount, 0);

now = 0;
warnCount = 0;
assert.deepStrictEqual(uiOperator.findElements("comment_list", 10), []);
assert.strictEqual(warnCount, 1);

Date.now = originalNow;
console.log("ui-operator-find-elements-quiet.node-test passed");
