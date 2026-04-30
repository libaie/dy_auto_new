// device/setup-templates.js
// 设置排序模板图片
// 运行前先手动打开排序弹出框

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 设置排序模板 ===");

// 创建目录
var dir = "/sdcard/dy_auto/templates";
try {
    files.createWithDirs(dir + "/");
    log("INFO", "目录已创建: " + dir);
} catch (e) {
    log("WARN", "目录创建: " + e.message);
}

// 截图权限
if (!requestScreenCapture(false)) {
    log("ERROR", "截图权限被拒绝");
    exit();
}
sleep(500);

// 截图
var screen = images.captureScreen();
log("INFO", "屏幕: " + screen.getWidth() + "x" + screen.getHeight());

// 用 OCR 找到排序选项位置，然后裁剪
var ocrResult = ocr.recognizeText(screen);
log("INFO", "OCR 识别 " + ocrResult.length + " 条");

// 找到各排序选项的索引
var options = {
    "综合排序": "sort_default.png",
    "最新发布": "sort_latest.png",
    "最多点赞": "sort_most_liked.png"
};

// 从 OCR 结果中找到排序选项的位置
var sortItems = [];
for (var i = 0; i < ocrResult.length; i++) {
    var text = ocrResult[i];
    if (text.indexOf("综合排序") !== -1 || text.indexOf("最新发布") !== -1 || text.indexOf("最多点赞") !== -1) {
        sortItems.push({ text: text, index: i });
        log("INFO", "  排序项[" + i + "]: \"" + text + "\"");
    }
}

if (sortItems.length === 0) {
    log("ERROR", "未找到排序选项，请确认弹出框已打开");
    screen.recycle();
    exit();
}

// 估算每个排序选项的 y 坐标并裁剪
// 排序选项从上到下排列，间隔约 50px
// 基于测试数据: 综合排序在 y≈340, 最新发布 y≈390, 最多点赞 y≈440
var baseY = 310;  // 排序区域起始 y
var itemHeight = 50;
var itemWidth = 250;
var startX = 80;  // 左边距

for (var j = 0; j < sortItems.length; j++) {
    var item = sortItems[j];
    var itemName = "";
    if (item.text.indexOf("综合排序") !== -1) itemName = "sort_default.png";
    else if (item.text.indexOf("最新发布") !== -1) itemName = "sort_latest.png";
    else if (item.text.indexOf("最多点赞") !== -1) itemName = "sort_most_liked.png";

    if (!itemName) continue;

    var cropY = baseY + j * itemHeight;
    var cropH = itemHeight - 5;

    try {
        var cropped = images.clip(screen, startX, cropY, itemWidth, cropH);
        var savePath = dir + "/" + itemName;
        images.save(cropped, savePath);
        log("INFO", "已保存: " + savePath + " (" + cropped.getWidth() + "x" + cropped.getHeight() + ")");
        cropped.recycle();
    } catch (e) {
        log("ERROR", "裁剪失败 " + itemName + ": " + e.message);
    }
}

screen.recycle();
log("INFO", "=== 模板设置完成 ===");
log("INFO", "模板目录: " + dir);
