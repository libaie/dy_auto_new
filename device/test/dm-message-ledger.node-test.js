const assert = require("assert");
const path = require("path");

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

const reportPayloads = [];
let claimPayload = null;

stub("handlers/base-handler", {
  ensureAppActive() { return true; },
  safeClick() { return true; },
  safeInput() { return true; },
});
stub("core/ui-operator", {
  isOnPage() { return true; },
  findElement(action) {
    return action === "dm_send" ? { id: "send" } : null;
  },
  clickElement() { return true; },
});
stub("core/anti-detect", {
  _skipDisabled: false,
});
stub("core/ai-analyzer", {
  useTemplate() {},
});
stub("core/flow-context", {
  enter() {},
});
stub("core/task-executor", {
  isCancelled() { return false; },
});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});
stub("core/crash-recovery", {
  ensureAppRunning() {},
});
stub("handlers/comment-utils", {
  collectProfileData() {
    return { nickname: "作者A", douyin_id: "douyin-1" };
  },
});
stub("core/api-client", {
  claimDMRecipient(payload) {
    claimPayload = payload;
    return { claimed: true, conversation_id: "conversation-1" };
  },
  reportDMSend(payload) {
    reportPayloads.push(payload);
    return { ok: true };
  },
  incrementStats() {},
  releaseDMRecipient() {},
});

const searchBase = require("../handlers/search-base");

const stats = { details: [] };
const results = searchBase._sendMessageSequence([
  { order: 1, content: "第一条 {{keyword}}", delay_ms: 0 },
  { order: 2, content: "第二条", delay_ms: 0 },
], stats, "目的地");

assert.ok(Array.isArray(results));
assert.deepStrictEqual(results.map((item) => item.status), ["sent", "sent"]);
assert.deepStrictEqual(results.map((item) => item.order), [1, 2]);
assert.deepStrictEqual(results.map((item) => item.content), ["第一条 目的地", "第二条"]);

const searchDM = require("../handlers/search-dm");
searchDM._params = {
  task_id: "task-1",
  account_id: "account-1",
  keyword: "目的地",
  dm_sequence_id: "seq-1",
  dm_messages: [
    { order: 1, content: "你好 {{keyword}}", delay_ms: 0 },
    { order: 2, content: "再聊", delay_ms: 0 },
  ],
};

reportPayloads.length = 0;
claimPayload = null;
assert.strictEqual(searchDM._interactWithVideo(null, { details: [] }), true);

assert.deepStrictEqual(claimPayload, {
  account_id: "account-1",
  recipient_douyin_id: "douyin-1",
  recipient_nickname: "作者A",
});
assert.strictEqual(reportPayloads.length, 2);
assert.deepStrictEqual(reportPayloads.map((item) => item.message_order), [1, 2]);
assert.deepStrictEqual(reportPayloads.map((item) => item.message_key), [
  "task-1:seq-1:1",
  "task-1:seq-1:2",
]);
assert.deepStrictEqual(reportPayloads.map((item) => item.status), ["sent", "sent"]);

const previousSafeInput = searchBase.safeInput;
searchBase.safeInput = () => false;
const failedResults = searchBase._sendMessageSequence([
  { order: 1, content: "失败一", delay_ms: 0 },
  { order: 2, content: "失败二", delay_ms: 0 },
], { details: [] }, "目的地");
searchBase.safeInput = previousSafeInput;
assert.deepStrictEqual(failedResults.map((item) => item.status), ["failed", "failed"]);
assert.deepStrictEqual(failedResults.map((item) => item.error_message), ["输入失败", "输入失败"]);
const fs = require("fs");
const replyCommentSource = fs.readFileSync(path.join(__dirname, "..", "handlers", "reply-comment.js"), "utf8");
assert.ok(replyCommentSource.indexOf("_reportDMSendResults") >= 0);
assert.strictEqual(replyCommentSource.indexOf("join(\" | \")"), -1);
assert.strictEqual(replyCommentSource.indexOf("join(' | ')") , -1);

console.log("dm-message-ledger.node-test passed");
