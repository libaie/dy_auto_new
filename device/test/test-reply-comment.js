// device/test-reply-comment.js
// 测试评论回复 + 关注 + 私信流程
// 运行前确保抖音已打开且在搜索结果页

function log(level, msg) {
  var ts = new Date().toLocaleTimeString();
  console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 测试评论回复流程 ===");

// 模拟 handler 的依赖
var SearchBaseHandler = require("../handlers/search-base");
var ReplyCommentHandler = require("../handlers/reply-comment");

// 测试参数
var testParams = {
  keyword: "美食",
  content: "你好，很高兴认识你",
  count: 2,
  sort_by: "latest",
  max_age_days: 5,
};

log("INFO", "测试参数: " + JSON.stringify(testParams));
log("INFO", "请确保抖音已打开且在首页");

// 执行
var result = ReplyCommentHandler.execute(testParams);

log("INFO", "执行结果: " + JSON.stringify(result));
log("INFO", "=== 测试完成 ===");
