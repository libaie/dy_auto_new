// device/spike/02-test-match-accuracy.js
// Spike Task 2: 模板匹配精度实验
// 目标: 验证 images.findImage() + 灰度 + 多尺度的命中率
//
// 前置条件: 先运行 01-test-capture.js 采集截图，并手动裁剪模板到 templates/ 目录
//
// 使用方法:
//   1. 确保 /sdcard/dy_auto/spike/ 下有截图
//   2. 确保 /sdcard/dy_auto/spike/templates/ 下有模板图片
//   3. 运行此脚本

var SPIKE_DIR = "/sdcard/dy_auto/spike/";
var TEMPLATE_DIR = SPIKE_DIR + "templates/";
var RESULT_PATH = SPIKE_DIR + "match_results.json";

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

// ============================================================
// 核心匹配函数
// ============================================================

function testMatch(templatePath, screenPath, options) {
    options = options || {};
    var template = images.read(templatePath);
    var screen = images.read(screenPath);

    if (!template) {
        return { error: "模板文件不存在: " + templatePath };
    }
    if (!screen) {
        return { error: "截图文件不存在: " + screenPath };
    }

    log("INFO", "模板: " + template.getWidth() + "x" + template.getHeight());
    log("INFO", "截图: " + screen.getWidth() + "x" + screen.getHeight());

    // 灰度转换
    var grayScreen = images.grayscale(screen);
    var grayTemplate = images.grayscale(template);

    var threshold = options.threshold || 0.8;
    var scales = options.scales || [0.9, 1.0, 1.1];
    var region = options.region || null;

    var results = [];

    for (var i = 0; i < scales.length; i++) {
        var scale = scales[i];
        var scaled = scale === 1.0
            ? grayTemplate
            : images.scale(grayTemplate, scale, scale);

        var startTime = Date.now();
        var matchResult;
        try {
            matchResult = images.findImage(grayScreen, scaled, {
                threshold: threshold,
                region: region
            });
        } catch (e) {
            results.push({
                scale: scale,
                found: false,
                error: e.message,
                elapsed: Date.now() - startTime
            });
            if (scaled !== grayTemplate) scaled.recycle();
            continue;
        }
        var elapsed = Date.now() - startTime;

        var found = !!matchResult;
        var x = null, y = null, confidence = null;

        if (found) {
            // findImage 返回的是模板左上角坐标
            // 计算中心点（点击坐标）
            var tw = Math.round(template.getWidth() * scale);
            var th = Math.round(template.getHeight() * scale);
            x = matchResult.x + tw / 2;
            y = matchResult.y + th / 2;
            confidence = matchResult.similarity || matchResult.confidence || null;
        }

        results.push({
            scale: scale,
            found: found,
            x: x,
            y: y,
            rawX: found ? matchResult.x : null,
            rawY: found ? matchResult.y : null,
            confidence: confidence,
            elapsed: elapsed
        });

        if (found) {
            log("INFO", "  命中! scale=" + scale +
                " pos=(" + matchResult.x + "," + matchResult.y + ")" +
                " center=(" + Math.round(x) + "," + Math.round(y) + ")" +
                " confidence=" + confidence +
                " " + elapsed + "ms");
        } else {
            log("INFO", "  未命中 scale=" + scale + " " + elapsed + "ms");
        }

        if (scaled !== grayTemplate) scaled.recycle();
    }

    // 清理
    template.recycle();
    screen.recycle();
    grayScreen.recycle();
    grayTemplate.recycle();

    return {
        templateSize: { w: template.getWidth(), h: template.getHeight() },
        screenSize: { w: screen.getWidth(), h: screen.getHeight() },
        threshold: threshold,
        scales: scales,
        results: results,
        bestMatch: results.reduce(function (best, r) {
            if (!r.found) return best;
            if (!best || (r.confidence || 0) > (best.confidence || 0)) return r;
            return best;
        }, null)
    };
}

// ============================================================
// 测试矩阵
// ============================================================

var testMatrix = [
    {
        name: "T1: 点赞按钮",
        template: "like_off.png",
        screen: "page_video_detail.png",
        threshold: 0.8,
        expected: true
    },
    {
        name: "T2: 关注按钮",
        template: "follow_btn.png",
        screen: "page_video_detail.png",
        threshold: 0.8,
        expected: true
    },
    {
        name: "T3: 搜索输入框",
        template: "search_input.png",
        screen: "page_search.png",
        threshold: 0.8,
        expected: true
    },
    {
        name: "T4: 最新发布选项",
        template: "sort_latest.png",
        screen: "page_sort_popup.png",
        threshold: 0.85,
        expected: true
    },
    {
        name: "T5: 视频 tab",
        template: "tab_video.png",
        screen: "page_search_result.png",
        threshold: 0.8,
        expected: true
    }
];

// ============================================================
// 额外测试: 不同阈值
// ============================================================

var thresholdTests = [0.7, 0.75, 0.8, 0.85, 0.9];

// ============================================================
// 主流程
// ============================================================

log("INFO", "=== Spike Task 2: 模板匹配精度测试 ===");

var allResults = [];

// 运行测试矩阵
for (var i = 0; i < testMatrix.length; i++) {
    var test = testMatrix[i];
    log("INFO", "--- " + test.name + " ---");

    var templatePath = TEMPLATE_DIR + test.template;
    var screenPath = SPIKE_DIR + test.screen;

    var result = testMatch(templatePath, screenPath, {
        threshold: test.threshold
    });

    result.testName = test.name;
    result.template = test.template;
    result.screen = test.screen;
    result.expected = test.expected;
    result.pass = result.bestMatch ? result.bestMatch.found === test.expected : false;

    allResults.push(result);

    log("INFO", "结果: " + (result.pass ? "PASS" : "FAIL") +
        (result.bestMatch ? " (confidence=" + result.bestMatch.confidence + ")" : " (无匹配)"));
    log("INFO", "");
}

// 阈值敏感性测试 (用 T1 的模板)
log("INFO", "--- 阈值敏感性测试 (T1: 点赞按钮) ---");
var thresholdResults = [];
for (var t = 0; t < thresholdTests.length; t++) {
    var th = thresholdTests[t];
    log("INFO", "阈值: " + th);
    var thResult = testMatch(
        TEMPLATE_DIR + "like_off.png",
        SPIKE_DIR + "page_video_detail.png",
        { threshold: th }
    );
    thresholdResults.push({
        threshold: th,
        found: thResult.bestMatch ? thResult.bestMatch.found : false,
        confidence: thResult.bestMatch ? thResult.bestMatch.confidence : null,
        elapsed: thResult.bestMatch ? thResult.bestMatch.elapsed : null
    });
}

// 保存结果
var summary = {
    timestamp: new Date().toISOString(),
    device: device.model,
    resolution: device.width + "x" + device.height,
    testResults: allResults.map(function (r) {
        return {
            name: r.testName,
            pass: r.pass,
            bestMatch: r.bestMatch,
            allScales: r.results
        };
    }),
    thresholdTests: thresholdResults
};

files.write(RESULT_PATH, JSON.stringify(summary, null, 2));
log("INFO", "结果已保存: " + RESULT_PATH);

// 打印汇总表
log("INFO", "");
log("INFO", "=== 测试结果汇总 ===");
log("INFO", "测试名称              | 预期 | 结果 | 置信度   | 耗时");
log("INFO", "----------------------|------|------|---------|------");
for (var j = 0; j < allResults.length; j++) {
    var r = allResults[j];
    var status = r.pass ? "PASS" : "FAIL";
    var conf = r.bestMatch ? (r.bestMatch.confidence || "N/A") : "N/A";
    var time = r.bestMatch ? (r.bestMatch.elapsed + "ms") : "N/A";
    log("INFO", padRight(r.testName, 22) + " | " +
        (r.expected ? "命中" : "未命中") + "  | " +
        status + " | " +
        padRight(String(conf), 7) + " | " + time);
}

log("INFO", "");
log("INFO", "=== 阈值敏感性 ===");
for (var k = 0; k < thresholdResults.length; k++) {
    var tr = thresholdResults[k];
    log("INFO", "threshold=" + tr.threshold +
        " → " + (tr.found ? "命中" : "未命中") +
        " confidence=" + (tr.confidence || "N/A") +
        " " + (tr.elapsed || "N/A") + "ms");
}

log("INFO", "");
log("INFO", "=== 完成 ===");

function padRight(str, len) {
    while (str.length < len) str += " ";
    return str;
}
