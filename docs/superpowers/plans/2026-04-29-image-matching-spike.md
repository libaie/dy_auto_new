# 图像匹配可行性验证 Spike 计划

> **目标**：在投入模板同步基础设施前，验证模板匹配和 OCR 的实际命中率、性能和维护成本。

**设备**：小米 10 (192.168.0.11)，通过 AutoJS6 VSCode 扩展连接
**时间**：2 天
**止损标准**：命中率 < 85% 或单次匹配 > 1500ms → 重新评估方案

---

## Spike Task 1：环境准备与截图采集（2 小时）

**目标**：在小米 10 上准备好测试素材

**步骤**：

1. 确认 AutoJS6 截图权限可用
```javascript
// device/spike/01-test-capture.js
// 测试截图权限和基本截图功能
if (!images.requestScreenCapture()) {
    toast("截图权限被拒绝");
    exit();
}
sleep(1000);
var img = images.captureScreen();
toast("截图成功: " + img.getWidth() + "x" + img.getHeight());
images.save(img, "/sdcard/dy_auto/spike/test_capture.png");
img.recycle();
```

2. 截取 5 个目标页面的全屏截图

| 页面 | 操作路径 | 截图文件名 |
|------|---------|-----------|
| 首页推荐 | 打开抖音 → 首页 | `page_home.png` |
| 搜索页 | 首页 → 点击搜索 | `page_search.png` |
| 搜索结果 | 搜索"美食" → 视频 tab | `page_search_result.png` |
| 排序弹窗 | 搜索结果 → 点击排序按钮 | `page_sort_popup.png` |
| 视频详情 | 搜索结果 → 点击第一个视频 | `page_video_detail.png` |

3. 从每张截图中裁剪 5 个关键元素，保存为模板

| 元素 | 来源页面 | 模板文件名 | 预期用途 |
|------|---------|-----------|---------|
| 点赞按钮（未点赞） | 视频详情 | `like_off.png` | 验证图标匹配 |
| 关注按钮 | 视频详情 | `follow_btn.png` | 验证文字+图标匹配 |
| 搜索输入框 | 搜索页 | `search_input.png` | 验证输入框匹配 |
| "最新发布"选项 | 排序弹窗 | `sort_latest.png` | 验证弹窗元素匹配 |
| 视频 tab | 搜索结果 | `tab_video.png` | 验证 tab 匹配 |

**产出**：10 张截图 + 25 个模板 PNG 文件，存放在 `/sdcard/dy_auto/spike/templates/`

---

## Spike Task 2：模板匹配精度实验（4 小时）

**目标**：验证 `images.findImage()` + 灰度 + 多尺度的命中率

**测试脚本**：

```javascript
// device/spike/02-test-match-accuracy.js
// 对每个模板，在对应页面截图上测试匹配

function testMatch(templatePath, screenPath, options) {
    var template = images.read(templatePath);
    var screen = images.read(screenPath);
    if (!template || !screen) {
        return { error: "file not found" };
    }

    var grayScreen = images.grayscale(screen);
    var grayTemplate = images.grayscale(template);
    var threshold = options.threshold || 0.8;
    var scales = options.scales || [0.9, 1.0, 1.1];
    var region = options.region || null;

    var results = [];
    for (var i = 0; i < scales.length; i++) {
        var scaled = scales[i] === 1.0
            ? grayTemplate
            : images.scale(grayTemplate, scales[i], scales[i]);

        var startTime = Date.now();
        var result = images.findImage(grayScreen, scaled, {
            threshold: threshold,
            region: region
        });
        var elapsed = Date.now() - startTime;

        results.push({
            scale: scales[i],
            found: !!result,
            x: result ? result.x : null,
            y: result ? result.y : null,
            elapsed: elapsed
        });

        if (scaled !== grayTemplate) scaled.recycle();
    }

    template.recycle();
    screen.recycle();
    grayScreen.recycle();
    grayTemplate.recycle();

    return { results: results, templateSize: { w: template.getWidth(), h: template.getHeight() } };
}
```

**测试矩阵**：

| 测试用例 | 模板 | 截图 | 阈值 | 预期 |
|---------|------|------|------|------|
| T1 | like_off.png | page_video_detail.png | 0.8 | 命中 |
| T2 | follow_btn.png | page_video_detail.png | 0.8 | 命中 |
| T3 | search_input.png | page_search.png | 0.8 | 命中 |
| T4 | sort_latest.png | page_sort_popup.png | 0.85 | 命中 |
| T5 | tab_video.png | page_search_result.png | 0.8 | 命中 |

**额外测试**：
- 暗色模式：如果设备支持暗色模式，切换后重复 T1-T5
- 不同阈值：对 T1 测试 threshold 0.7, 0.75, 0.8, 0.85, 0.9 的命中率
- 坐标语义：验证 `result.x/y` 是左上角还是中心点

**产出**：精度测试结果表，记录每个用例的命中率、置信度、耗时

---

## Spike Task 3：OCR 降级对比（2 小时）

**目标**：对比 PaddleOCR 对同样元素的识别效果

**测试脚本**：

```javascript
// device/spike/03-test-ocr-compare.js
// 对每个页面截图，用 OCR 识别文字按钮

function testOCR(screenPath) {
    var screen = images.read(screenPath);
    if (!screen) return { error: "file not found" };

    var startTime = Date.now();
    var result;
    if (typeof images.paddleOcr === "function") {
        result = images.paddleOcr(screen);
    } else if (typeof images.mlKitOcr === "function") {
        result = images.mlKitOcr(screen);
    } else {
        return { error: "no OCR available" };
    }
    var elapsed = Date.now() - startTime;

    screen.recycle();
    return { ocrResults: result, elapsed: elapsed };
}
```

**对比维度**：

| 元素 | OCR 能否识别 | 模板匹配能否识别 | 推荐方案 |
|------|------------|----------------|---------|
| "点赞"文字 | ? | ? | |
| "关注"文字 | ? | ? | |
| 搜索输入框（无文字） | ? | ? | |
| "最新发布" | ? | ? | |
| "视频" tab | ? | ? | |

**产出**：OCR vs 模板匹配对比表，确定哪些元素用哪种方案

---

## Spike Task 4：性能基准（2 小时）

**目标**：建立性能预算，确定是否需要优化

**测试项**：

| 测试 | 方法 | 目标 |
|------|------|------|
| 单次 findImage（全屏） | 1080x2400 截图 + 小模板 | < 500ms |
| 单次 findImage（限定区域） | 只搜索底部 30% | < 200ms |
| 多尺度 3 级 | [0.9, 1.0, 1.1] 全屏 | < 1200ms |
| 多尺度 2 级 | [0.95, 1.0] 全屏 | < 800ms |
| 灰度转换 | 1080x2400 截图 | < 50ms |
| images.read() 模板 | 小 PNG 文件 | < 30ms |
| PaddleOCR 全屏 | 1080x2400 截图 | < 2000ms |

**产出**：性能基准表，确定最终的尺度策略和区域限定策略

---

## Spike Task 5：结果汇总与决策（2 小时）

**目标**：根据实验数据决定后续方向

**决策矩阵**：

| 条件 | 决策 |
|------|------|
| 模板匹配命中率 > 85% 且单次 < 800ms | 路径 A：按原方案推进模板匹配 |
| 模板匹配命中率 > 85% 但单次 > 1500ms | 路径 A-：减少尺度数量，限定区域 |
| 模板匹配命中率 < 85% 且 OCR 命中率 > 80% | 路径 B：OCR 优先 + 模板匹配兜底 |
| 两者都差 | 路径 C：重新设计（LLM-vision / accessibility 树） |
| 暗色模式命中率 < 70% | 需要明暗两套模板，重新评估维护成本 |

**产出**：
1. Spike 结果报告（写入 `docs/superpowers/specs/2026-04-29-spike-results.md`）
2. 根据决策矩阵选择路径，更新设计文档
3. 如果选择路径 A，编写完整实施计划

---

## 文件结构

```
device/spike/
├── 01-test-capture.js          # 截图权限测试 + 页面截图采集
├── 02-test-match-accuracy.js   # 模板匹配精度测试
├── 03-test-ocr-compare.js      # OCR 对比测试
├── 04-test-performance.js      # 性能基准测试
├── 05-summarize.js             # 结果汇总脚本
└── templates/                  # 裁剪的模板图片
    ├── like_off.png
    ├── follow_btn.png
    ├── search_input.png
    ├── sort_latest.png
    └── tab_video.png
```

## 执行顺序

```
Task 1 (环境准备) → Task 2 (精度实验) + Task 3 (OCR 对比) → Task 4 (性能基准) → Task 5 (汇总决策)
```

Task 2 和 Task 3 可以并行执行（同一套截图素材）。

## 成功标准

Spike 成功的定义：
- 完成 5 个元素 x 5 个页面的匹配精度测试
- 完成 OCR vs 模板匹配的对比
- 建立性能基准数据
- 根据数据做出明确的路径选择决策

Spike 失败的定义：
- 模板匹配命中率 < 70%（即使调优也无法接受）
- 设备上 `images.findImage()` 不可用或行为异常
- 无法获取截图权限
