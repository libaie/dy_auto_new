// device/test-search.js
// 测试抖音搜索流程 - 完整版

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 搜索流程测试 ===");

// 确保在抖音首页
if (currentPackage() !== "com.ss.android.ugc.aweme") {
    log("INFO", "不在抖音，正在启动...");
    app.launchApp("抖音");
    sleep(5000);
}

// 1. 点击搜索
log("INFO", "--- 1. 点击搜索 ---");
var searchBtn = text("搜索").findOnce() || desc("搜索").findOnce();
if (searchBtn) {
    log("INFO", "找到搜索按钮: bounds=" + searchBtn.bounds());
    searchBtn.click();
    sleep(2000);
} else {
    log("ERROR", "未找到搜索按钮");
    exit();
}

// 2. 清空输入框
log("INFO", "--- 2. 清空输入框 ---");
var editBox = className("EditText").findOnce();
if (editBox) {
    log("INFO", "输入框当前文字: \"" + editBox.text() + "\"");
    editBox.click();
    sleep(500);
    editBox.setText("");
    sleep(300);
    log("INFO", "清空后: \"" + editBox.text() + "\"");
    input("美食");
    sleep(1000);
    log("INFO", "输入后: \"" + editBox.text() + "\"");
} else {
    log("ERROR", "未找到输入框");
    exit();
}

// 4. 在联想列表中点击关键词
log("INFO", "--- 4. 点击联想词 ---");
var keyword = "美食";
try {
    var recyclerView = id("recycler_view").findOne(5000);
    if (recyclerView) {
        var children = recyclerView.children();
        log("INFO", "联想列表子项数量: " + children.length);
        var found = false;
        for (var i = 0; i < children.length; i++) {
            var target = children[i].findOne(text(keyword));
            if (target) {
                log("INFO", "找到联想词: \"" + target.text() + "\" bounds=" + target.bounds());
                target.click();
                found = true;
                break;
            }
        }
        if (!found) {
            log("WARN", "未找到包含 \"" + keyword + "\" 的联想词，点击第一项");
            if (children.length > 0) {
                children[0].click();
            }
        }
        sleep(3000);
    } else {
        log("WARN", "未找到 recycler_view");
    }
} catch (e) {
    log("ERROR", "点击联想词失败: " + e.message);
}

// 5. 点击"视频" tab（通过选择器系统）
log("INFO", "--- 5. 点击视频 tab ---");
log("INFO", "视频 tab 需通过选择器配置");
var clicked = false;

// 6. 点击排序按钮（通过选择器系统）
log("INFO", "--- 6. 点击排序按钮 ---");
log("INFO", "排序按钮需通过选择器配置");

// 7. 弹出框处理
// 排序选项 — 实际使用时从任务参数获取
var sortOption = "最新发布";  // 可选: "最新发布", "最多点赞"

log("INFO", "--- 7. 弹出框 UI ---");
sleep(1000);

// 先 dump 弹出框内容
var allText = textMatches(".+").find();
log("INFO", "弹出框文字控件数量: " + allText.length);
for (var k = 0; k < Math.min(allText.length, 20); k++) {
    log("INFO", "  [" + k + "] \"" + allText[k].text() + "\" bounds=" + allText[k].bounds());
}

// 点击排序选项
log("INFO", "--- 8. 点击排序选项: " + sortOption + " ---");
try {
    var sortItem = text(sortOption).findOne(3000);
    if (sortItem) {
        log("INFO", "找到排序选项: \"" + sortItem.text() + "\" bounds=" + sortItem.bounds());
        sortItem.click();
        sleep(2000);
        log("INFO", "已点击排序选项");
    } else {
        log("WARN", "未找到排序选项 \"" + sortOption + "\"");
        // 尝试点击可点击元素
        var clickables = clickable(true).find();
        log("INFO", "可点击控件数量: " + clickables.length);
        for (var j = 0; j < Math.min(clickables.length, 10); j++) {
            var c = clickables[j];
            log("INFO", "  [" + j + "] text=\"" + c.text() + "\" desc=\"" + c.desc() + "\" bounds=" + c.bounds());
        }
    }
} catch (e) {
    log("ERROR", "点击排序选项失败: " + e.message);
}

// 9. 读取最终结果
log("INFO", "--- 9. 最终结果页 ---");
sleep(2000);
var finalTexts = textMatches(".+").find();
log("INFO", "结果控件数量: " + finalTexts.length);
for (var m = 0; m < Math.min(finalTexts.length, 25); m++) {
    log("INFO", "  [" + m + "] \"" + finalTexts[m].text() + "\"");
}

log("INFO", "=== 搜索流程测试完成 ===");
