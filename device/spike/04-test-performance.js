// device/spike/04-test-performance.js
// Spike Task 4: 性能基准测试
// 目标: 建立性能预算，确定是否需要优化
//
// 前置条件: 运行 01-test-capture.js 采集截图 + 模板
//
// 使用方法:
//   1. 确保 /sdcard/dy_auto/spike/ 下有截图和模板
//   2. 运行此脚本

var SPIKE_DIR = "/sdcard/dy_auto/spike/";
var TEMPLATE_DIR = SPIKE_DIR + "templates/";
var RESULT_PATH = SPIKE_DIR + "perf_results.json";

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

function benchmark(name, fn, iterations) {
    iterations = iterations || 3;
    var times = [];
    var result;

    for (var i = 0; i < iterations; i++) {
        var start = Date.now();
        result = fn();
        times.push(Date.now() - start);
    }

    var avg = Math.round(times.reduce(function (a, b) { return a + b; }, 0) / times.length);
    var min = Math.min.apply(null, times);
    var max = Math.max.apply(null, times);

    log("INFO", name + ": avg=" + avg + "ms min=" + min + "ms max=" + max + "ms (n=" + iterations + ")");

    return {
        name: name,
        avg: avg,
        min: min,
        max: max,
        iterations: iterations,
        times: times
    };
}

// ============================================================
// 主流程
// ============================================================

log("INFO", "=== Spike Task 4: 性能基准测试 ===");

var allResults = [];

// 先截图一次用于测试
if (!images.requestScreenCapture()) {
    log("ERROR", "截图权限被拒绝");
    exit();
}
sleep(2000);

// ============================================================
// 测试 1: images.captureScreen() 截图速度
// ============================================================
log("INFO", "--- 测试 1: 截图速度 ---");
var r1 = benchmark("captureScreen", function () {
    var img = images.captureScreen();
    if (img) img.recycle();
    return true;
}, 5);
allResults.push(r1);

// ============================================================
// 测试 2: images.read() 模板加载
// ============================================================
log("INFO", "--- 测试 2: 模板加载速度 ---");
var templateFiles = [
    "like_off.png",
    "follow_btn.png",
    "search_input.png",
    "sort_latest.png",
    "tab_video.png"
];

for (var t = 0; t < templateFiles.length; t++) {
    var tPath = TEMPLATE_DIR + templateFiles[t];
    if (!files.exists(tPath)) {
        log("WARN", "模板不存在: " + tPath + ", 跳过");
        continue;
    }
    var r = benchmark("images.read(" + templateFiles[t] + ")", function () {
        var img = images.read(tPath);
        if (img) img.recycle();
        return true;
    }, 5);
    allResults.push(r);
}

// ============================================================
// 测试 3: 灰度转换
// ============================================================
log("INFO", "--- 测试 3: 灰度转换 ---");
var screen = images.captureScreen();
if (screen) {
    var r3 = benchmark("grayscale(fullscreen " + screen.getWidth() + "x" + screen.getHeight() + ")", function () {
        var gray = images.grayscale(screen);
        if (gray) gray.recycle();
        return true;
    }, 5);
    allResults.push(r3);

    // ============================================================
    // 测试 4: images.scale() 缩放
    // ============================================================
    log("INFO", "--- 测试 4: 模板缩放 ---");
    var template = images.read(TEMPLATE_DIR + templateFiles[0]);
    if (template) {
        var grayTemplate = images.grayscale(template);

        var scales = [0.8, 0.9, 1.0, 1.1, 1.2];
        for (var s = 0; s < scales.length; s++) {
            var sc = scales[s];
            var r4 = benchmark("scale(" + sc + ")", function () {
                var scaled = images.scale(grayTemplate, sc, sc);
                if (scaled) scaled.recycle();
                return true;
            }, 5);
            allResults.push(r4);
        }

        // ============================================================
        // 测试 5: findImage 全屏匹配 (单尺度)
        // ============================================================
        log("INFO", "--- 测试 5: findImage 全屏匹配 ---");
        var grayScreen = images.grayscale(screen);

        var r5 = benchmark("findImage(fullscreen, threshold=0.8)", function () {
            var result = images.findImage(grayScreen, grayTemplate, {
                threshold: 0.8
            });
            return !!result;
        }, 3);
        allResults.push(r5);

        // ============================================================
        // 测试 6: findImage 限定区域匹配
        // ============================================================
        log("INFO", "--- 测试 6: findImage 限定区域匹配 ---");

        // 底部 30% 区域
        var regionBottom = {
            x: 0,
            y: Math.round(screen.getHeight() * 0.7),
            width: screen.getWidth(),
            height: Math.round(screen.getHeight() * 0.3)
        };

        var r6 = benchmark("findImage(bottom30%, threshold=0.8)", function () {
            var result = images.findImage(grayScreen, grayTemplate, {
                threshold: 0.8,
                region: regionBottom
            });
            return !!result;
        }, 3);
        allResults.push(r6);

        // 右侧 30% 区域
        var regionRight = {
            x: Math.round(screen.getWidth() * 0.7),
            y: 0,
            width: Math.round(screen.getWidth() * 0.3),
            height: screen.getHeight()
        };

        var r6b = benchmark("findImage(right30%, threshold=0.8)", function () {
            var result = images.findImage(grayScreen, grayTemplate, {
                threshold: 0.8,
                region: regionRight
            });
            return !!result;
        }, 3);
        allResults.push(r6b);

        // ============================================================
        // 测试 7: 多尺度匹配 (3 级)
        // ============================================================
        log("INFO", "--- 测试 7: 多尺度匹配 (3 级) ---");

        var r7 = benchmark("findImage(3-scale [0.9,1.0,1.1], fullscreen)", function () {
            var scales3 = [0.9, 1.0, 1.1];
            var found = false;
            for (var si = 0; si < scales3.length; si++) {
                var scaled = scales3[si] === 1.0
                    ? grayTemplate
                    : images.scale(grayTemplate, scales3[si], scales3[si]);
                var result = images.findImage(grayScreen, scaled, { threshold: 0.8 });
                if (scaled !== grayTemplate) scaled.recycle();
                if (result) { found = true; break; }
            }
            return found;
        }, 3);
        allResults.push(r7);

        // ============================================================
        // 测试 8: 多尺度匹配 (2 级)
        // ============================================================
        log("INFO", "--- 测试 8: 多尺度匹配 (2 级) ---");

        var r8 = benchmark("findImage(2-scale [0.95,1.0], fullscreen)", function () {
            var scales2 = [0.95, 1.0];
            var found = false;
            for (var si = 0; si < scales2.length; si++) {
                var scaled = scales2[si] === 1.0
                    ? grayTemplate
                    : images.scale(grayTemplate, scales2[si], scales2[si]);
                var result = images.findImage(grayScreen, scaled, { threshold: 0.8 });
                if (scaled !== grayTemplate) scaled.recycle();
                if (result) { found = true; break; }
            }
            return found;
        }, 3);
        allResults.push(r8);

        // ============================================================
        // 测试 9: findImage 不同阈值
        // ============================================================
        log("INFO", "--- 测试 9: 不同阈值性能 ---");

        var thresholds = [0.6, 0.7, 0.8, 0.85, 0.9];
        for (var th = 0; th < thresholds.length; th++) {
            var t_val = thresholds[th];
            var r9 = benchmark("findImage(threshold=" + t_val + ")", function () {
                var result = images.findImage(grayScreen, grayTemplate, { threshold: t_val });
                return !!result;
            }, 3);
            allResults.push(r9);
        }

        grayTemplate.recycle();
    } else {
        log("WARN", "模板加载失败，跳过部分测试");
    }

    grayScreen.recycle();
    screen.recycle();
} else {
    log("ERROR", "截图失败，无法进行性能测试");
}

// ============================================================
// 测试 10: OCR 性能
// ============================================================
log("INFO", "--- 测试 10: OCR 性能 ---");

var ocrScreen = images.captureScreen();
if (ocrScreen) {
    if (typeof images.paddleOcr === "function") {
        var r10 = benchmark("paddleOcr(fullscreen)", function () {
            try {
                var r = images.paddleOcr(ocrScreen);
                return r;
            } catch (e) {
                return null;
            }
        }, 3);
        allResults.push(r10);
    }

    if (typeof images.mlKitOcr === "function") {
        var r10b = benchmark("mlKitOcr(fullscreen)", function () {
            try {
                var r = images.mlKitOcr(ocrScreen);
                return r;
            } catch (e) {
                return null;
            }
        }, 3);
        allResults.push(r10b);
    }

    ocrScreen.recycle();
}

// 保存结果
var summary = {
    timestamp: new Date().toISOString(),
    device: device.model,
    resolution: device.width + "x" + device.height,
    results: allResults
};

files.write(RESULT_PATH, JSON.stringify(summary, null, 2));
log("INFO", "");
log("INFO", "结果已保存: " + RESULT_PATH);

// 打印性能汇总
log("INFO", "");
log("INFO", "=== 性能基准汇总 ===");
log("INFO", "测试项                                    | 平均耗时 | 最小   | 最大   | 目标    | 达标");
log("INFO", "------------------------------------------|---------|-------|-------|--------|----");
for (var ri = 0; ri < allResults.length; ri++) {
    var r = allResults[ri];
    var target = getTarget(r.name);
    var pass = target ? (r.avg <= target) : null;
    var passStr = pass === null ? "N/A" : (pass ? "YES" : "NO");
    log("INFO", padRight(r.name, 40) + " | " +
        padRight(r.avg + "ms", 7) + " | " +
        padRight(r.min + "ms", 5) + " | " +
        padRight(r.max + "ms", 5) + " | " +
        padRight(target ? target + "ms" : "N/A", 6) + " | " + passStr);
}

log("INFO", "");
log("INFO", "=== 完成 ===");

function getTarget(name) {
    if (name.indexOf("captureScreen") !== -1) return 200;
    if (name.indexOf("images.read") !== -1) return 30;
    if (name.indexOf("grayscale") !== -1) return 50;
    if (name.indexOf("scale") !== -1) return 20;
    if (name.indexOf("fullscreen") !== -1 && name.indexOf("findImage") !== -1 && name.indexOf("scale") === -1) return 500;
    if (name.indexOf("bottom30") !== -1) return 200;
    if (name.indexOf("right30") !== -1) return 200;
    if (name.indexOf("3-scale") !== -1) return 1200;
    if (name.indexOf("2-scale") !== -1) return 800;
    if (name.indexOf("paddleOcr") !== -1) return 2000;
    if (name.indexOf("mlKitOcr") !== -1) return 2000;
    return null;
}

function padRight(str, len) {
    while (str.length < len) str += " ";
    return str;
}
