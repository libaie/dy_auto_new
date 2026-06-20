const assert = require("assert");
const fs = require("fs");
const path = require("path");

const searchBase = fs.readFileSync(path.join(__dirname, "../handlers/search-base.js"), "utf8");
const commentBase = fs.readFileSync(path.join(__dirname, "../handlers/comment-base.js"), "utf8");

for (const [name, source] of [
  ["search-base", searchBase],
  ["comment-base", commentBase],
]) {
  assert.ok(
    source.includes('uiOperator.findElement("sort_latest", 800, true)'),
    `${name} should quiet sort_latest residual popup detection`,
  );
  assert.ok(
    source.includes('uiOperator.findElement("sort_most_liked", 800, true)'),
    `${name} should quiet sort_most_liked residual popup detection`,
  );
}

assert.ok(
  searchBase.includes("uiOperator.findElement(actionName, 2000, true)"),
  "sort popup close verification should quiet the selected sort lookup",
);
assert.ok(
  searchBase.includes("uiOperator.findElement(actionName, 1000, true)"),
  "sort popup second close verification should quiet the selected sort lookup",
);
assert.ok(
  !searchBase.includes('this.safeClick("off_video", 1);'),
  "clicking a search result must not immediately close the opened video",
);

console.log("search-sort-popup.node-test passed");
