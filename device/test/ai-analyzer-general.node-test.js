const assert = require("assert");
const path = require("path");

global.__config = { serverUrl: "http://127.0.0.1:8001", deviceSecret: "secret" };

function stub(relativePath, exports) {
  const filename = require.resolve(path.join("..", relativePath));
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports,
  };
}

stub("core/api-client", {});
stub("utils/logger", {
  info() {},
  warn() {},
  error() {},
  debug() {},
});

const aiAnalyzer = require("../core/ai-analyzer");

aiAnalyzer.useTemplate(null, "general");

assert.strictEqual(aiAnalyzer.getIndustry(), "general");
assert.strictEqual(
  aiAnalyzer._localRelevanceCheck("电竞游戏德扑上分"),
  null,
  "general collect should not reject game-related comments with health excludes",
);

const prompt = aiAnalyzer._buildAnalysisPrompt("德扑", "测试用户", "有局吗");
assert.ok(prompt.includes("通用话题线索"));
assert.ok(prompt.includes("搜索关键词是【德扑】"));
assert.ok(prompt.includes('"intent": "topic_consult"'));
assert.ok(!prompt.includes('"intent": "health_consult"'));

console.log("ai-analyzer-general.node-test passed");
