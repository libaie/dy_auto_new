// 真人输入模拟模块，负责把文本输入拆成更接近人工操作的节奏。
function _noop() {}

function _defaultDeps() {
  return {
    random: Math.random,
    sleep: typeof sleep === "function" ? sleep : _noop,
    input: typeof input === "function" ? input : null,
    shell: typeof shell === "function" ? shell : null,
    findFocusedEditText: function () {
      if (typeof className !== "function") return null;
      var focused = className("EditText").focused(true).findOne(1000);
      if (focused) return focused;
      return className("EditText").findOne(1000);
    },
  };
}

function _mergeDeps(deps) {
  var merged = _defaultDeps();
  deps = deps || {};
  for (var k in deps) {
    if (deps.hasOwnProperty(k)) merged[k] = deps[k];
  }
  return merged;
}

function _cleanText(text) {
  return String(text == null ? "" : text).replace(/^\s+/, "").replace(/\s+$/, "");
}

function _sleep(deps, ms) {
  try { deps.sleep(ms); } catch (e) {}
}

function _random(deps) {
  var value;
  try { value = deps.random(); } catch (e) { value = Math.random(); }
  if (typeof value !== "number" || value < 0 || value >= 1) return Math.random();
  return value;
}

function _chunkSize(deps, remaining) {
  var size = _random(deps) < 0.4 ? 1 : (Math.floor(_random(deps) * 2) + 2);
  return Math.min(size, remaining);
}

function _clearEditText(editText) {
  if (!editText || typeof editText.setText !== "function") return false;
  // 清空输入框是受控输入的第一步，避免上一条私信或评论残留。
  editText.setText("");
  return true;
}

function _readEditText(editText) {
  if (!editText) return null;
  try {
    if (typeof editText.text === "function") return String(editText.text());
  } catch (e) {}
  try {
    if (typeof editText.getText === "function") return String(editText.getText());
  } catch (e2) {}
  return null;
}

function _forceEditText(editText, text) {
  if (!editText || typeof editText.setText !== "function") return false;
  try {
    // 兜底直写只作用于当前输入框，真人节奏仍由上层分块输入控制。
    editText.setText(text);
    return true;
  } catch (e) {
    return false;
  }
}

function typeFocusedText(text, deps) {
  deps = _mergeDeps(deps);
  var cleanText = _cleanText(text);
  if (!cleanText || typeof deps.input !== "function") return false;

  var editText = null;
  try { editText = deps.findFocusedEditText ? deps.findFocusedEditText() : null; } catch (e) {}
  if (!editText && deps.requireVerification) return false;
  _clearEditText(editText);
  _sleep(deps, 200);

  var dummyChars = "abcdefghijklmnopqrstuvwxyz";
  var dummy = dummyChars.charAt(Math.floor(_random(deps) * dummyChars.length));
  deps.input(dummy);
  _sleep(deps, Math.floor(_random(deps) * 150 + 100));

  if (!_clearEditText(editText) && typeof deps.shell === "function") {
    try { deps.shell("input keyevent 67", false); } catch (e2) {}
  }
  _sleep(deps, 100);

  var pos = 0;
  while (pos < cleanText.length) {
    var size = _chunkSize(deps, cleanText.length - pos);
    deps.input(cleanText.substring(pos, pos + size));
    pos += size;
    _sleep(deps, Math.floor(_random(deps) * 250 + 150));
  }

  var actualText = _readEditText(editText);
  if (actualText === null && deps.requireVerification) return false;
  if (actualText !== null && actualText !== cleanText) {
    if (!_forceEditText(editText, cleanText)) return false;
    _sleep(deps, 100);
    actualText = _readEditText(editText);
    if (actualText !== null && actualText !== cleanText) return false;
  }

  return true;
}

module.exports = {
  typeFocusedText: typeFocusedText,
  _cleanText: _cleanText,
};
