// device/spike/05-summarize.js
// Spike Task 5: 结果汇总
// 目标: 汇总所有测试结果，生成决策报告
//
// 前置条件: 运行过 02/03/04 脚本
//
// 使用方法:
//   1. 运行此脚本
//   2. 查看 /sdcard/dy_auto/spike/spike_report.json

var SPIKE_DIR = "/sdcard/dy_auto/spike/";
var REPORT_PATH = SPIKE_DIR + "spike_report.json";

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

function readJSON(path) {
    try {
        var content = files.read(path);
        return JSON.parse(content);
    } catch (e) {
        log("WARN", "无法读取: " + path + " (" + e.message + ")");
        return null;
    }
}

// ============================================================
// 读取各项测试结果
// ============================================================

log("INFO", "=== Spike Task 5: 结果汇总 ===");

var matchResults = readJSON(SPIKE_DIR + "match_results.json");
var ocrResults = readJSON(SPIKE_DIR + "ocr_results.json");
var perfResults = readJSON(SPIKE_DIR + "perf_results.json");

// ============================================================
// 分析匹配精度
// ============================================================

var matchAnalysis = {
    available: !!matchResults,
    totalTests: 0,
    passed: 0,
    failed: 0,
    hitRate: 0,
    avgConfidence: 0,
    avgElapsed: 0,
    thresholdSensitivity: []
};

if (matchResults && matchResults.testResults) {
    var tests = matchResults.testResults;
    matchAnalysis.totalTests = tests.length;
    var confSum = 0, confCount = 0, timeSum = 0, timeCount = 0;

    for (var i = 0; i < tests.length; i++) {
        if (tests[i].pass) matchAnalysis.passed++;
        else matchAnalysis.failed++;

        if (tests[i].bestMatch) {
            if (tests[i].bestMatch.confidence) {
                confSum += tests[i].bestMatch.confidence;
                confCount++;
            }
            if (tests[i].bestMatch.elapsed) {
                timeSum += tests[i].bestMatch.elapsed;
                timeCount++;
            }
        }
    }

    matchAnalysis.hitRate = matchAnalysis.totalTests > 0
        ? Math.round(matchAnalysis.passed / matchAnalysis.totalTests * 100)
        : 0;
    matchAnalysis.avgConfidence = confCount > 0
        ? Math.round(confSum / confCount * 100) / 100
        : 0;
    matchAnalysis.avgElapsed = timeCount > 0
        ? Math.round(timeSum / timeCount)
        : 0;

    matchAnalysis.thresholdSensitivity = matchResults.thresholdTests || [];
}

// ============================================================
// 分析 OCR 效果
// ============================================================

var ocrAnalysis = {
    available: !!ocrResults,
    method: "none",
    avgElapsed: 0,
    avgKeywordHitRate: 0,
    details: []
};

if (ocrResults && ocrResults.results) {
    var ocrR = ocrResults.results;
    var ocrTimeSum = 0, ocrTimeCount = 0;
    var hitSum = 0, hitCount = 0;

    for (var j = 0; j < ocrR.length; j++) {
        if (ocrR[j].method && ocrR[j].method !== "none") {
            ocrAnalysis.method = ocrR[j].method;
        }
        if (ocrR[j].elapsed) {
            ocrTimeSum += ocrR[j].elapsed;
            ocrTimeCount++;
        }
        if (ocrR[j].totalCount > 0) {
            hitSum += ocrR[j].matchedCount / ocrR[j].totalCount;
            hitCount++;
        }
        ocrAnalysis.details.push({
            name: ocrR[j].name,
            matched: ocrR[j].matchedCount,
            total: ocrR[j].totalCount,
            elapsed: ocrR[j].elapsed
        });
    }

    ocrAnalysis.avgElapsed = ocrTimeCount > 0 ? Math.round(ocrTimeSum / ocrTimeCount) : 0;
    ocrAnalysis.avgKeywordHitRate = hitCount > 0 ? Math.round(hitSum / hitCount * 100) : 0;
}

// ============================================================
// 分析性能
// ============================================================

var perfAnalysis = {
    available: !!perfResults,
    summary: {}
};

if (perfResults && perfResults.results) {
    var pR = perfResults.results;
    for (var k = 0; k < pR.length; k++) {
        perfAnalysis.summary[pR[k].name] = {
            avg: pR[k].avg,
            min: pR[k].min,
            max: pR[k].max
        };
    }
}

// ============================================================
// 决策矩阵
// ============================================================

log("INFO", "--- 决策分析 ---");

var decision = {
    path: "unknown",
    reason: "",
    recommendations: []
};

if (matchAnalysis.available) {
    var hitRateOk = matchAnalysis.hitRate >= 85;
    var speedOk = matchAnalysis.avgElapsed < 800;

    if (hitRateOk && speedOk) {
        decision.path = "A";
        decision.reason = "模板匹配命中率 " + matchAnalysis.hitRate + "% > 85%, 平均耗时 " +
            matchAnalysis.avgElapsed + "ms < 800ms";
        decision.recommendations.push("按原方案推进模板匹配");
        decision.recommendations.push("集成到 UI 操作层");
        decision.recommendations.push("建设模板管理后端");
    } else if (hitRateOk && !speedOk) {
        decision.path = "A-";
        decision.reason = "命中率达标 (" + matchAnalysis.hitRate + "%) 但速度不达标 (" +
            matchAnalysis.avgElapsed + "ms)";
        decision.recommendations.push("减少尺度数量到 2 级");
        decision.recommendations.push("限定搜索区域");
        decision.recommendations.push("考虑分辨率映射减少缩放");
    } else if (!hitRateOk && ocrAnalysis.available && ocrAnalysis.avgKeywordHitRate >= 80) {
        decision.path = "B";
        decision.reason = "模板匹配命中率低 (" + matchAnalysis.hitRate + "%), OCR 效果好 (" +
            ocrAnalysis.avgKeywordHitRate + "%)";
        decision.recommendations.push("OCR 优先 + 模板匹配兜底");
        decision.recommendations.push("对无文字图标元素用模板匹配");
        decision.recommendations.push("考虑 LLM-vision 作为最终降级");
    } else {
        decision.path = "C";
        decision.reason = "模板匹配命中率低 (" + matchAnalysis.hitRate + "%), OCR 也不理想 (" +
            ocrAnalysis.avgKeywordHitRate + "%)";
        decision.recommendations.push("重新设计方案");
        decision.recommendations.push("调研 accessibility 树启发式");
        decision.recommendations.push("考虑 LLM-vision 定位器");
    }
}

// 暗色模式检查
if (matchAnalysis.available && matchAnalysis.thresholdSensitivity.length > 0) {
    var lowThresholdHits = matchAnalysis.thresholdSensitivity.filter(function (t) {
        return t.threshold <= 0.75 && t.found;
    });
    if (lowThresholdHits.length > 0) {
        decision.recommendations.push("注意: 低阈值 (<=0.75) 才能命中，可能需要明暗两套模板");
    }
}

// ============================================================
// 生成报告
// ============================================================

var report = {
    timestamp: new Date().toISOString(),
    device: device.model,
    resolution: device.width + "x" + device.height,
    spikeVersion: "1.0",

    matchAnalysis: matchAnalysis,
    ocrAnalysis: ocrAnalysis,
    perfAnalysis: perfAnalysis,
    decision: decision,

    rawData: {
        matchResults: matchResults,
        ocrResults: ocrResults,
        perfResults: perfResults
    }
};

files.write(REPORT_PATH, JSON.stringify(report, null, 2));

// ============================================================
// 打印报告
// ============================================================

log("INFO", "");
log("INFO", "====================================");
log("INFO", "       SPIKE 结果报告");
log("INFO", "====================================");
log("INFO", "");
log("INFO", "设备: " + (matchResults ? matchResults.device : "未知"));
log("INFO", "分辨率: " + (matchResults ? matchResults.resolution : "未知"));
log("INFO", "");

log("INFO", "【模板匹配精度】");
if (matchAnalysis.available) {
    log("INFO", "  测试数量: " + matchAnalysis.totalTests);
    log("INFO", "  通过: " + matchAnalysis.passed + " / " + matchAnalysis.totalTests);
    log("INFO", "  命中率: " + matchAnalysis.hitRate + "%");
    log("INFO", "  平均置信度: " + matchAnalysis.avgConfidence);
    log("INFO", "  平均耗时: " + matchAnalysis.avgElapsed + "ms");

    log("INFO", "  阈值敏感性:");
    for (var ti = 0; ti < matchAnalysis.thresholdSensitivity.length; ti++) {
        var ts = matchAnalysis.thresholdSensitivity[ti];
        log("INFO", "    threshold=" + ts.threshold + " → " +
            (ts.found ? "命中" : "未命中") +
            (ts.confidence ? " (confidence=" + ts.confidence + ")" : ""));
    }
} else {
    log("INFO", "  数据不可用 (未运行 02-test-match-accuracy.js)");
}

log("INFO", "");
log("INFO", "【OCR 对比】");
if (ocrAnalysis.available) {
    log("INFO", "  OCR 方法: " + ocrAnalysis.method);
    log("INFO", "  平均耗时: " + ocrAnalysis.avgElapsed + "ms");
    log("INFO", "  关键词命中率: " + ocrAnalysis.avgKeywordHitRate + "%");
    for (var oi = 0; oi < ocrAnalysis.details.length; oi++) {
        var od = ocrAnalysis.details[oi];
        log("INFO", "    " + od.name + ": " + od.matched + "/" + od.total +
            (od.elapsed ? " " + od.elapsed + "ms" : ""));
    }
} else {
    log("INFO", "  数据不可用 (未运行 03-test-ocr-compare.js)");
}

log("INFO", "");
log("INFO", "【性能基准】");
if (perfAnalysis.available) {
    var keys = Object.keys(perfAnalysis.summary);
    for (var pi = 0; pi < keys.length; pi++) {
        var ps = perfAnalysis.summary[keys[pi]];
        log("INFO", "  " + keys[pi] + ": " + ps.avg + "ms (min=" + ps.min + " max=" + ps.max + ")");
    }
} else {
    log("INFO", "  数据不可用 (未运行 04-test-performance.js)");
}

log("INFO", "");
log("INFO", "====================================");
log("INFO", "【决策】");
log("INFO", "  路径: " + decision.path);
log("INFO", "  原因: " + decision.reason);
log("INFO", "  建议:");
for (var di = 0; di < decision.recommendations.length; di++) {
    log("INFO", "    - " + decision.recommendations[di]);
}
log("INFO", "====================================");

log("INFO", "");
log("INFO", "报告已保存: " + REPORT_PATH);
log("INFO", "=== 完成 ===");
