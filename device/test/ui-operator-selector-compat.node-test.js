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

function bounds(left, top, right, bottom) {
  return {
    left,
    top,
    right,
    bottom,
    centerX() { return Math.round((left + right) / 2); },
    centerY() { return Math.round((top + bottom) / 2); },
  };
}

function makeElement(props) {
  return {
    text() { return props.text || ""; },
    desc() { return props.desc || ""; },
    id() { return props.id || ""; },
    className() { return props.className || "android.widget.TextView"; },
    bounds() { return props.bounds; },
  };
}

function finder(elements) {
  return {
    find() { return elements; },
  };
}

const videoDesc = makeElement({
  id: "com.ss.android.ugc.aweme:id/desc",
  bounds: bounds(400, 950, 600, 1050),
});
const authorBadge = makeElement({
  text: "作者",
  bounds: bounds(20, 20, 100, 70),
});

global.text = () => finder([]);
global.textContains = (value) => finder(value === "作者" ? [authorBadge] : []);
global.id = (value) => finder(value === "com.ss.android.ugc.aweme:id/desc" ? [videoDesc] : []);
global.idContains = () => finder([]);
global.desc = () => finder([]);
global.descContains = () => finder([]);
global.className = () => finder([]);
global.classNameContains = () => finder([]);

stub("core/selector-loader", {
  get(actionName) {
    if (actionName === "search_video_list") {
      return {
        strategies: [
          {
            type: "id",
            value: "com.ss.android.ugc.aweme:id/desc",
            priority: 1,
            y_percent: -200,
          },
        ],
      };
    }
    if (actionName === "comment_is_author") {
      return {
        strategies: [
          {
            type: "textContains",
            value: "作者",
            priority: 1,
          },
        ],
      };
    }
    return null;
  },
});
stub("core/api-client", {});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});

const uiOperator = require("../core/ui-operator");

{
  now = 0;
  const elements = uiOperator.findElements("search_video_list", 10);
  assert.strictEqual(elements.length, 1);
  assert.strictEqual(elements[0].isCoordinate, true);
  assert.strictEqual(elements[0].x, 500);
  assert.strictEqual(elements[0].y, 800);
}

{
  now = 0;
  const el = uiOperator.findElement("comment_is_author", 10);
  assert.strictEqual(el, authorBadge);
}

Date.now = originalNow;
console.log("ui-operator-selector-compat.node-test passed");
