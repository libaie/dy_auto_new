// device/test-douyin.js
// 测试启动抖音并读取首页 UI

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 抖音启动测试 ===");

// 1. 启动抖音
log("INFO", "正在启动抖音...");
app.launchApp("抖音");
sleep(5000);

// 2. 检查是否在抖音
var pkg = currentPackage();
log("INFO", "当前包名: " + pkg);
if (pkg !== "com.ss.android.ugc.aweme") {
    log("WARN", "不在抖音，尝试 launchPackage...");
    app.launchPackage("com.ss.android.ugc.aweme");
    sleep(5000);
    pkg = currentPackage();
    log("INFO", "当前包名: " + pkg);
}

// 3. 读取屏幕文字
log("INFO", "--- 首页文字采样 ---");
var textNodes = textMatches(".+").find();
log("INFO", "文字控件数量: " + textNodes.length);
for (var i = 0; i < Math.min(textNodes.length, 25); i++) {
    log("INFO", "  [" + i + "] \"" + textNodes[i].text() + "\"");
}

// 4. 查找底部导航栏
log("INFO", "--- 底部导航栏 ---");
var tabs = ["首页", "朋友", "+", "消息", "我"];
for (var j = 0; j < tabs.length; j++) {
    var el = text(tabs[j]).findOnce();
    if (el) {
        log("INFO", "  找到: \"" + tabs[j] + "\" bounds=" + el.bounds());
    } else {
        log("INFO", "  未找到: \"" + tabs[j] + "\"");
    }
}

// 5. 查找搜索入口
log("INFO", "--- 搜索入口 ---");
var searchEl = desc("搜索").findOnce() || text("搜索").findOnce();
if (searchEl) {
    log("INFO", "找到搜索按钮: bounds=" + searchEl.bounds());
} else {
    log("INFO", "未找到搜索按钮（可能需要查看 desc 属性）");
    // 列出所有 desc 非空的控件
    var descs = descMatches(".+").find();
    log("INFO", "desc 控件数量: " + descs.length);
    for (var k = 0; k < Math.min(descs.length, 15); k++) {
        log("INFO", "  desc[" + k + "]=\"" + descs[k].desc() + "\"");
    }
}

log("INFO", "=== 测试完成 ===");
