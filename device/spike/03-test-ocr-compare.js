// device/spike/03-test-ocr-compare.js
// Spike Task 3: OCR 降级对比
// 目标: 对比 PaddleOCR 对同样元素的识别效果
//
// 前置条件: 运行 01-test-capture.js 采集截图
//
// 使用方法:
//   1. 确保 /sdcard/dy_auto/spike/ 下有截图
//   2. 运行此脚本

var SPIKE_DIR = "/sdcard/dy_auto/spike/";
var RESULT_PATH = SPIKE_DIR + "ocr_results.json";

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

// ============================================================
// OCR 测试函数
// ============================================================

function testOCR(screenPath, keywords) {
    var screen = images.read(screenPath);
    if (!screen) {
        return { error: "截图文件不存在: " + screenPath };
    }

    log("INFO", "截图: " + screen.getWidth() + "x" + screen.getHeight());

    // 尝试各种 OCR 方法
    var ocrResult = null;
    var method = "none";
    var startTime, elapsed;

    // 方式1: paddleOcr
    if (typeof images.paddleOcr === "function") {
        log("INFO", "尝试 paddleOcr...");
        startTime = Date.now();
        try {
            ocrResult = images.paddleOcr(screen);
            elapsed = Date.now() - startTime;
            method = "paddleOcr";
            log("INFO", "paddleOcr 成功, " + elapsed + "ms, 结果数量: " +
                (Array.isArray(ocrResult) ? ocrResult.length : "非数组"));
        } catch (e) {
            log("WARN", "paddleOcr 失败: " + e.message);
        }
    }

    // 方式2: mlKitOcr
    if (!ocrResult && typeof images.mlKitOcr === "function") {
        log("INFO", "尝试 mlKitOcr...");
        startTime = Date.now();
        try {
            ocrResult = images.mlKitOcr(screen);
            elapsed = Date.now() - startTime;
            method = "mlKitOcr";
            log("INFO", "mlKitOcr 成功, " + elapsed + "ms");
        } catch (e) {
            log("WARN", "mlKitOcr 失败: " + e.message);
        }
    }

    // 方式3: 全局 ocr
    if (!ocrResult && typeof ocr === "function") {
        log("INFO", "尝试全局 ocr()...");
        startTime = Date.now();
        try {
            ocrResult = ocr(screen);
            elapsed = Date.now() - startTime;
            method = "ocr";
            log("INFO", "ocr() 成功, " + elapsed + "ms");
        } catch (e) {
            log("WARN", "ocr() 失败: " + e.message);
        }
    }

    if (!ocrResult) {
        screen.recycle();
        return { error: "无可用的 OCR 方法" };
    }

    // 解析 OCR 结果，查找关键词
    var foundKeywords = [];
    var allText = [];

    if (Array.isArray(ocrResult)) {
        for (var i = 0; i < ocrResult.length; i++) {
            var item = ocrResult[i];
            var text = item.text || item.label || String(item);
            var bounds = item.bounds || item.box || item.rect || null;
            allText.push({
                text: text,
                bounds: bounds,
                confidence: item.confidence || item.score || null
            });

            // 检查是否匹配关键词
            for (var k = 0; k < keywords.length; k++) {
                if (text.indexOf(keywords[k]) !== -1) {
                    foundKeywords.push({
                        keyword: keywords[k],
                        text: text,
                        bounds: bounds,
                        confidence: item.confidence || item.score || null
                    });
                }
            }
        }
    } else if (typeof ocrResult === "object") {
        // 某些 OCR 返回对象而非数组
        allText.push({ text: JSON.stringify(ocrResult).substring(0, 500) });
    }

    screen.recycle();

    return {
        method: method,
        elapsed: elapsed,
        totalItems: allText.length,
        allText: allText.slice(0, 50), // 只保留前 50 条
        foundKeywords: foundKeywords
    };
}

// ============================================================
// 测试矩阵
// ============================================================

var testMatrix = [
    {
        name: "T1: 视频详情页",
        screen: "page_video_detail.png",
        keywords: ["赞", "点赞", "关注", "评论", "分享", "收藏"]
    },
    {
        name: "T2: 搜索页",
        screen: "page_search.png",
        keywords: ["搜索", "取消", "历史", "热门"]
    },
    {
        name: "T3: 搜索结果页",
        screen: "page_search_result.png",
        keywords: ["视频", "用户", "直播", "商品", "综合", "排序"]
    },
    {
        name: "T4: 排序弹窗",
        screen: "page_sort_popup.png",
        keywords: ["最新发布", "最多点赞", "综合排序", "排序"]
    },
    {
        name: "T5: 首页",
        screen: "page_home.png",
        keywords: ["首页", "朋友", "拍摄", "消息", "我"]
    }
];

// ============================================================
// 主流程
// ============================================================

log("INFO", "=== Spike Task 3: OCR 降级对比测试 ===");

var allResults = [];

for (var i = 0; i < testMatrix.length; i++) {
    var test = testMatrix[i];
    log("INFO", "--- " + test.name + " ---");

    var result = testOCR(SPIKE_DIR + test.screen, test.keywords);
    result.testName = test.name;
    result.screen = test.screen;
    result.expectedKeywords = test.keywords;

    allResults.push(result);

    if (result.error) {
        log("INFO", "结果: " + result.error);
    } else {
        log("INFO", "方法: " + result.method + ", 耗时: " + result.elapsed + "ms");
        log("INFO", "识别文字数量: " + result.totalItems);
        log("INFO", "匹配关键词: " + result.foundKeywords.length + "/" + test.keywords.length);
        for (var j = 0; j < result.foundKeywords.length; j++) {
            var kw = result.foundKeywords[j];
            log("INFO", "  \"" + kw.keyword + "\" → \"" + kw.text + "\"" +
                (kw.bounds ? " bounds=" + JSON.stringify(kw.bounds) : ""));
        }
    }
    log("INFO", "");
}

// 保存结果
var summary = {
    timestamp: new Date().toISOString(),
    device: device.model,
    resolution: device.width + "x" + device.height,
    results: allResults.map(function (r) {
        return {
            name: r.testName,
            method: r.method || "none",
            elapsed: r.elapsed || null,
            totalItems: r.totalItems || 0,
            foundKeywords: r.foundKeywords || [],
            expectedKeywords: r.expectedKeywords,
            matchedCount: (r.foundKeywords || []).length,
            totalCount: (r.expectedKeywords || []).length
        };
    })
};

files.write(RESULT_PATH, JSON.stringify(summary, null, 2));
log("INFO", "结果已保存: " + RESULT_PATH);

// 打印汇总
log("INFO", "");
log("INFO", "=== OCR vs 模板匹配对比表 ===");
log("INFO", "页面              | OCR方法    | 识别数 | 关键词命中 | 耗时");
log("INFO", "------------------|-----------|-------|----------|------");
for (var m = 0; m < allResults.length; m++) {
    var r = allResults[m];
    var method = r.method || "N/A";
    var total = r.totalItems || 0;
    var matched = (r.foundKeywords || []).length;
    var expected = (r.expectedKeywords || []).length;
    var elapsed = r.elapsed ? (r.elapsed + "ms") : "N/A";
    log("INFO", padRight(r.testName, 18) + " | " +
        padRight(method, 9) + " | " +
        padRight(String(total), 5) + " | " +
        padRight(matched + "/" + expected, 8) + " | " + elapsed);
}

log("INFO", "");
log("INFO", "=== 完成 ===");

function padRight(str, len) {
    while (str.length < len) str += " ";
    return str;
}
