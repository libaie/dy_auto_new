// device/test-capture-popup.js
// 步骤1: 打开搜索 → 点视频tab → 点排序 → 截图保存弹出框
// 截图保存到 /sdcard/dy_auto_popup.png，后续用于裁剪模板

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 弹出框截图 ===");

// 确保在抖音
if (currentPackage() !== "com.ss.android.ugc.aweme") {
    app.launchApp("抖音");
    sleep(5000);
}

// 搜索
log("INFO", "点击搜索...");
var btn = text("搜索").findOnce() || desc("搜索").findOnce();
if (btn) btn.click();
sleep(2000);

// 输入 — 剪贴板粘贴触发联想
var editBox = className("EditText").findOnce();
if (editBox) {
    editBox.click();
    sleep(300);
    // 全选旧文字并删除
    editBox.setSelection(0, editBox.text().length);
    sleep(100);
    setClip("");
    paste();
    sleep(200);
    // 粘贴关键词
    setClip("美食");
    sleep(200);
    paste();
    sleep(1000);
    log("INFO", "粘贴后: \"" + editBox.text() + "\"");
}

// 点击联想词
log("INFO", "--- 点击联想词 ---");
var rv = id("recycler_view").findOne(3000);
if (rv) {
    var ch = rv.children();
    log("INFO", "联想词数量: " + ch.length);
    var found = false;
    for (var i = 0; i < ch.length; i++) {
        var t = ch[i].findOne(text("美食"));
        if (t) {
            log("INFO", "点击联想词: \"" + t.text() + "\"");
            t.parent().parent().click();
            found = true;
            break;
        }
    }
    if (!found && ch.length > 0) {
        var first = ch[0].findOne(textMatches(".+"));
        log("INFO", "未找到精确匹配，点击第一项: \"" + (first ? first.text() : "?") + "\"");
        ch[0].click();
    }
    sleep(3000);
} else {
    log("WARN", "未找到联想列表 recycler_view");
}
sleep(2000);

// 点击联想词
var rv = id("recycler_view").findOne(3000);
if (rv) {
    var children = rv.children();
    for (var i = 0; i < children.length; i++) {
        var t = children[i].findOne(text("美食"));
        if (t) { t.click(); break; }
    }
}
sleep(3000);

// 点击视频 tab
log("INFO", "点击视频 tab...");
try {
    var vt = id("text1").className("android.widget.Button").text("视频").findOne(5000);
    if (vt) vt.parent().parent().click();
    sleep(2000);
} catch (e) { log("WARN", "视频 tab: " + e.message); }

// 点击排序按钮
log("INFO", "点击排序按钮...");
try {
    var sb = id("ivu").findOne(3000);
    if (sb) sb.click();
    sleep(1500);
} catch (e) { log("WARN", "排序按钮: " + e.message); }

// 截图
log("INFO", "截图中...");
try {
    if (!images.requestScreenCapture()) {
        log("ERROR", "截图权限被拒绝");
        exit();
    }
    sleep(1000);
    var img = images.captureScreen();
    var path = "/sdcard/dy_auto_popup.png";
    images.save(img, path);
    log("INFO", "截图已保存: " + path);
    log("INFO", "分辨率: " + img.getWidth() + "x" + img.getHeight());
    img.recycle();
} catch (e) {
    log("ERROR", "截图失败: " + e.message);
}

log("INFO", "=== 完成，请查看 /sdcard/dy_auto_popup.png ===");
log("INFO", "=== 下一步: 裁剪出\"最新发布\"按钮区域作为模板 ===");
