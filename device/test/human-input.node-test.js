const assert = require("assert");

const humanInput = require("../core/human-input");

function createHarness(randomValues) {
  const ops = [];
  let randomIndex = 0;
  const editText = {
    setText(value) {
      ops.push(["setText", value]);
    },
  };
  return {
    ops,
    deps: {
      findFocusedEditText() {
        ops.push(["findFocusedEditText"]);
        return editText;
      },
      input(value) {
        ops.push(["input", value]);
      },
      sleep(ms) {
        ops.push(["sleep", ms]);
      },
      random() {
        const value = randomValues[randomIndex % randomValues.length];
        randomIndex += 1;
        return value;
      },
    },
  };
}

{
  const harness = createHarness([0.02, 0.1, 0.8, 0.2, 0.9, 0.3]);
  const ok = humanInput.typeFocusedText("你好abc", harness.deps);

  assert.strictEqual(ok, true);
  assert.deepStrictEqual(harness.ops[0], ["findFocusedEditText"]);
  assert.deepStrictEqual(harness.ops[1], ["setText", ""]);
  assert.ok(harness.ops.some((op) => op[0] === "input" && op[1].length > 0));
  assert.ok(!harness.ops.some((op) => op[0] === "setText" && op[1] === "你好abc"));

  const typed = harness.ops
    .filter((op) => op[0] === "input")
    .slice(1)
    .map((op) => op[1])
    .join("");
  assert.strictEqual(typed, "你好abc");
}

{
  const harness = createHarness([0.4, 0.1, 0.1, 0.1]);
  humanInput.typeFocusedText(" 私信内容", harness.deps);
  const typed = harness.ops
    .filter((op) => op[0] === "input")
    .slice(1)
    .map((op) => op[1])
    .join("");

  assert.strictEqual(typed, "私信内容");
}

{
  const ops = [];
  let value = "placeholder>";
  const editText = {
    setText(next) {
      ops.push(["setText", next]);
      if (next !== "") value = next;
    },
    text() {
      return value;
    },
  };
  const ok = humanInput.typeFocusedText("dm-msg", {
    findFocusedEditText() {
      ops.push(["findFocusedEditText"]);
      return editText;
    },
    input(chunk) {
      ops.push(["input", chunk]);
      value += chunk;
    },
    sleep(ms) {
      ops.push(["sleep", ms]);
    },
    random() {
      return 0.1;
    },
  });

  assert.strictEqual(ok, true);
  assert.strictEqual(value, "dm-msg");
  assert.ok(ops.some((op) => op[0] === "setText" && op[1] === "dm-msg"));
}

{
  const harness = createHarness([0.1, 0.1, 0.1]);
  const ok = humanInput.typeFocusedText("dm-msg", Object.assign({}, harness.deps, {
    requireVerification: true,
  }));

  assert.strictEqual(ok, false);
}

console.log("human-input.node-test passed");
