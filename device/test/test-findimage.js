// device/test-findimage.js
// findImage 找图点击

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

// 1. 截图权限
if (!requestScreenCapture(false)) {
    log("ERROR", "截图权限被拒绝");
    exit();
}
sleep(500);

// 2. 加载模板
var templatePath = "/sdcard/最新发布.png";
var templateImg = images.read(templatePath);
if (!templateImg) {
    log("ERROR", "模板加载失败: " + templatePath);
    log("INFO", "请确认文件存在，或用其他路径");
    // 列出可能的路径
    var paths = [
        "/sdcard/DCIM/Screenshots/IMG_20260429_110909.jpg",
        "/sdcard/DCIM/Screenshots/IMG_20260429_112800.jpg",
        "/sdcard/Pictures/最新发布.png"
    ];
    for (var i = 0; i < paths.length; i++) {
        var test = images.read(paths[i]);
        if (test) {
            log("INFO", "可用模板: " + paths[i] + " (" + test.getWidth() + "x" + test.getHeight() + ")");
            templateImg = test;
            templatePath = paths[i];
            break;
        }
    }
    if (!templateImg) exit();
}
log("INFO", "模板: " + templatePath + " " + templateImg.getWidth() + "x" + templateImg.getHeight());

// 3. 截屏
var screenImg = images.captureScreen();
log("INFO", "屏幕: " + screenImg.getWidth() + "x" + screenImg.getHeight());

// 4. findImage
log("INFO", "--- findImage ---");
var p = images.findImage(screenImg, templateImg, {
    threshold: 0.8
});

if (p) {
    var clickX = p.x + templateImg.getWidth() / 2;
    var clickY = p.y + templateImg.getHeight() / 2;
    log("INFO", "找到! 左上角: (" + p.x + "," + p.y + ") 点击中心: (" + clickX + "," + clickY + ")");
    click(clickX, clickY);
    log("INFO", "已点击");
} else {
    log("WARN", "threshold=0.8 未找到，降低阈值重试...");
    var p2 = images.findImage(screenImg, templateImg, { threshold: 0.5 });
    if (p2) {
        var cx = p2.x + templateImg.getWidth() / 2;
        var cy = p2.y + templateImg.getHeight() / 2;
        log("INFO", "0.5阈值找到! 点击: (" + cx + "," + cy + ")");
        click(cx, cy);
    } else {
        log("WARN", "0.5阈值也未找到");
        var p3 = images.findImage(screenImg, templateImg, { threshold: 0.3 });
        if (p3) {
            log("INFO", "0.3阈值找到: (" + p3.x + "," + p3.y + ")");
        } else {
            log("WARN", "完全未匹配");
        }
    }
}

templateImg.recycle();
screenImg.recycle();
log("INFO", "=== 完成 ===");
