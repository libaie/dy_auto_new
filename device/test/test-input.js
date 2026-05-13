// device/test-input.js
// 测试各种文字输入方式

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 输入方式测试 ===");

// 确保在抖音
if (currentPackage() !== "com.ss.android.ugc.aweme") {
    app.launchApp("抖音");
    sleep(5000);
}

// 点搜索
var btn = text("搜索").findOnce() || desc("搜索").findOnce();
if (btn) btn.click();
sleep(2000);

var eb = className("EditText").findOnce();
if (!eb) { log("ERROR", "没找到输入框"); exit(); }
log("INFO", "原始文字: \"" + eb.text() + "\"");

// 方法1: setText
log("INFO", "--- 方法1: setText(\"美食\") ---");
eb.click();
sleep(300);
eb.setText("美食");
sleep(500);
log("INFO", "setText结果: \"" + eb.text() + "\"");

// 方法2: 剪贴板 + 粘贴
log("INFO", "--- 方法2: 剪贴板粘贴 ---");
eb.click();
sleep(200);
// 全选旧文字
eb.setSelection(0, eb.text().length);
sleep(200);
// 设置剪贴板
setClip("美食");
sleep(200);
// 粘贴
paste();
sleep(500);
var eb2 = className("EditText").findOnce();
log("INFO", "粘贴结果: \"" + (eb2 ? eb2.text() : "null") + "\"");

// 方法3: ADB shell input
log("INFO", "--- 方法3: shell input ---");
try {
    // 先清空
    eb.click();
    sleep(200);
    eb.setSelection(0, eb.text().length);
    sleep(100);
    shell("input keyevent 67", false);  // KeyCode_DEL
    sleep(200);
    // 输入文字
    shell("input text meishi", false);  // 拼音输入
    sleep(1000);
    var eb3 = className("EditText").findOnce();
    log("INFO", "shell结果: \"" + (eb3 ? eb3.text() : "null") + "\"");
} catch (e) {
    log("ERROR", "shell失败: " + e.message);
}

// 检查联想列表
log("INFO", "--- 联想列表 ---");
var rv = id("recycler_view").findOne(3000);
if (rv) {
    var ch = rv.children();
    log("INFO", "子项: " + ch.length);
    for (var i = 0; i < Math.min(ch.length, 10); i++) {
        var txt = ch[i].findOne(textMatches(".+"));
        log("INFO", "  [" + i + "] " + (txt ? "\"" + txt.text() + "\"" : "(空)"));
    }
}

log("INFO", "=== 测试完成 ===");
