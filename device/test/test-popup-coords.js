// device/test-popup-coords.js
// 手动操作到弹出框界面后运行此脚本
// 截图 + dump 所有元素坐标，用于确定裁剪区域

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 弹出框坐标分析 ===");

// 截图
if (!images.requestScreenCapture()) {
    log("ERROR", "截图权限被拒绝");
    exit();
}
sleep(1500);

var img = images.captureScreen();
var w = img.getWidth();
var h = img.getHeight();
log("INFO", "屏幕: " + w + "x" + h);

// 保存全屏截图
images.save(img, "/sdcard/dy_auto_popup_full.png");
log("INFO", "全屏截图已保存: /sdcard/dy_auto_popup_full.png");

// dump 所有文字元素及其坐标
log("INFO", "--- 文字元素 ---");
var allText = textMatches(".+").find();
for (var i = 0; i < allText.length; i++) {
    var b = allText[i].bounds();
    log("INFO", "  [" + i + "] \"" + allText[i].text() + "\" Rect(" + b.left + "," + b.top + "," + b.right + "," + b.bottom + ")");
}

// dump 可点击元素
log("INFO", "--- 可点击元素 ---");
var clickables = clickable(true).find();
for (var j = 0; j < clickables.length; j++) {
    var c = clickables[j];
    var cb = c.bounds();
    log("INFO", "  [" + j + "] class=" + c.className() + " text=\"" + c.text() + "\" Rect(" + cb.left + "," + cb.top + "," + cb.right + "," + cb.bottom + ")");
}

// dump desc 元素
log("INFO", "--- desc 元素 ---");
var descs = descMatches(".+").find();
for (var k = 0; k < descs.length; k++) {
    var db = descs[k].bounds();
    log("INFO", "  [" + k + "] desc=\"" + descs[k].desc() + "\" Rect(" + db.left + "," + db.top + "," + db.right + "," + db.bottom + ")");
}

img.recycle();
log("INFO", "=== 请根据上面的坐标，告诉我\"最新发布\"按钮的区域 ===");
log("INFO", "=== 我会用 images.clip() 裁出模板图片 ===");
