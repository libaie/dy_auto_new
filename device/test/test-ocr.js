// device/test-ocr.js
// 测试 OCR 识别能力，定位屏幕文字坐标

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== OCR 测试 ===");

// 截图
log("INFO", "--- 截图 ---");
try {
    if (!images.requestScreenCapture()) {
        log("ERROR", "截图权限被拒绝，请在手机上授权");
        exit();
    }
    sleep(1500);
    var img = images.captureScreen();
    log("INFO", "截图成功: " + img.getWidth() + "x" + img.getHeight());
} catch (e) {
    log("ERROR", "截图失败: " + e.message);
    exit();
}

// 列出 images 所有方法
log("INFO", "--- images 可用方法 ---");
for (var key in images) {
    if (typeof images[key] === "function") {
        log("INFO", "  images." + key + "()");
    }
}

// 尝试各种 OCR
log("INFO", "--- 尝试 OCR ---");

// 方式1: paddleOcr
if (typeof images.paddleOcr === "function") {
    log("INFO", "尝试 images.paddleOcr...");
    try {
        var r1 = images.paddleOcr(img);
        log("INFO", "paddleOcr结果: " + JSON.stringify(r1).substring(0, 500));
    } catch (e) {
        log("ERROR", "paddleOcr失败: " + e.message);
    }
}

// 方式2: mlKitOcr
if (typeof images.mlKitOcr === "function") {
    log("INFO", "尝试 images.mlKitOcr...");
    try {
        var r2 = images.mlKitOcr(img);
        log("INFO", "mlKitOcr结果: " + JSON.stringify(r2).substring(0, 500));
    } catch (e) {
        log("ERROR", "mlKitOcr失败: " + e.message);
    }
}

// 方式3: 全局 ocr 函数
if (typeof ocr === "function") {
    log("INFO", "尝试全局 ocr()...");
    try {
        var r3 = ocr(img);
        log("INFO", "ocr结果: " + JSON.stringify(r3).substring(0, 500));
    } catch (e) {
        log("ERROR", "ocr失败: " + e.message);
    }
}

// 方式4: textDetection / recognizeText
if (typeof images.textDetection === "function") {
    log("INFO", "尝试 images.textDetection...");
    try {
        var r4 = images.textDetection(img);
        log("INFO", "textDetection结果: " + JSON.stringify(r4).substring(0, 500));
    } catch (e) {
        log("ERROR", "textDetection失败: " + e.message);
    }
}

if (typeof images.recognizeText === "function") {
    log("INFO", "尝试 images.recognizeText...");
    try {
        var r5 = images.recognizeText(img);
        log("INFO", "recognizeText结果: " + JSON.stringify(r5).substring(0, 500));
    } catch (e) {
        log("ERROR", "recognizeText失败: " + e.message);
    }
}

img.recycle();
log("INFO", "=== OCR 测试完成 ===");
