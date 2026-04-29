# 以图找图元素定位方案 - 设计文档

## 概述

在现有 AutoJS6 控件选择器（text/id/desc/className/coordinate）基础上，增加图像模板匹配作为降级策略，解决抖音频繁更新导致控件属性失效、选择器维护成本高的问题。

## 核心思路

将图像匹配作为选择器策略的一种新类型 `image`，融入现有的多策略降级链：

```
现有：text → id → desc → className → coordinate
扩展后：text → id → desc → className → image → coordinate
```

优先用控件属性快速定位，找不到时降级到图像匹配，最后用坐标兜底。

## 技术选型

### 匹配引擎：AutoJS6 原生 API + JS 层多尺度

使用 AutoJS6 内置的 `images.findImage()`（底层基于 OpenCV `matchTemplate`），在 JS 层实现多尺度金字塔匹配。不引入额外 OpenCV 模块。

理由：
- 零额外依赖，AutoJS6 内置
- 灰度匹配通过 `images.grayscale()` 实现
- 多尺度在 JS 层循环缩放模板图即可，不需要 WASM
- 如果后续精度不够，可升级到 OpenCV.js WASM 模块

### 模板图片：后端管理 + 设备端缓存

模板图片存储在设备本地 `/sdcard/dy_auto/templates/` 目录，由后端统一分发和版本管理。

---

## 匹配引擎设计

### 核心匹配流程

```
findImageMatch(screenImg, templatePath, options):
  template = images.read(templatePath)

  // 1. 灰度转换（抗颜色/主题变化）
  grayScreen = images.grayscale(screenImg)
  grayTemplate = images.grayscale(template)

  // 2. 多尺度匹配（适配不同分辨率）
  for scale in [0.9, 1.0, 1.1]:
    scaledTemplate = scale === 1.0 ? grayTemplate : images.scale(grayTemplate, scale, scale)
    result = images.findImage(grayScreen, scaledTemplate, {
      threshold: options.threshold || 0.8,
      region: options.region || null
    })
    if result:
      return { x, y, confidence, scale }

  return null
```

### 性能优化

| 优化手段 | 说明 | 效果 |
|---------|------|------|
| 搜索区域限定 | 已知按钮在屏幕底部时只搜索底部区域 | 匹配速度提升 3-5x |
| 截图复用 | 同一操作流程复用同一张截图 | 避免重复截屏 |
| 灰度预处理 | 模板和截图都转灰度 | 减少计算量 |
| 分辨率映射 | 首次运行记录分辨率，后端下发对应模板 | 减少缩放开销 |

### 匹配结果对象

```javascript
{
  isImageMatch: true,
  x: centerX,           // 元素中心 X（点击坐标）
  y: centerY,           // 元素中心 Y
  confidence: 0.92,     // 匹配置信度
  scale: 1.0,           // 匹配时的缩放比例
  bounds: { left, top, right, bottom }
}
```

返回的对象兼容现有 `clickElement()` 方法，走坐标点击逻辑。

---

## UI 操作层改造

### findElement 方法扩展

```javascript
findElement: function (actionName, timeout, screenImg) {
  // screenImg 可选传入，避免重复截屏
  // 按策略优先级依次尝试
  for each strategy in strategies:
    element = this._findByStrategy(strategy, screenImg)
    if element: return element
  return null
}

_findByStrategy: function (strategy, screenImg) {
  switch (strategy.type) {
    case "text":       return text(strategy.value).findOnce()
    case "id":         return id(strategy.value).findOnce()
    case "desc":       return desc(strategy.value).findOnce()
    case "className":  return className(strategy.value).findOnce()
    case "image":      return this._findByImage(strategy, screenImg)  // 新增
    case "coordinate": return { isCoordinate, x, y }
  }
}
```

### 截图复用

Handler 层面在操作开始时截一次图，传给多个 `findElement` 调用：

```javascript
var screen = images.captureScreen();
var likeBtn = uiOperator.findElement("like_button", 3000, screen);
var commentBtn = uiOperator.findElement("comment_input", 3000, screen);
screen.recycle();
```

### clickElement 兼容

image 匹配返回的对象带 `isImageMatch` 标记，走现有坐标点击逻辑，不需要额外改动。

---

## 模板管理

### 模板存储结构

**设备端**：
```
/sdcard/dy_auto/templates/
├── v1/
│   ├── like_button.png
│   ├── follow_button.png
│   ├── comment_input.png
│   ├── search_tab.png
│   ├── sort_latest.png
│   └── ...
└── manifest.json
```

**后端**：
```
server/app/data/templates/
├── v1/
│   ├── like_button.png
│   └── ...
└── manifest.json
```

### manifest.json 格式

```json
{
  "version": 1,
  "templates": {
    "like_button": {
      "file": "like_button.png",
      "threshold": 0.8,
      "region": { "x": 0.7, "y": 0.3, "w": 0.3, "h": 0.4 },
      "note": "右侧点赞按钮"
    },
    "sort_latest": {
      "file": "sort_latest.png",
      "threshold": 0.85,
      "region": null,
      "note": "排序弹窗-最新发布"
    }
  }
}
```

- `region`：可选的搜索区域限制（屏幕百分比），用于加速匹配
- `threshold`：匹配置信度阈值，低于此值视为未找到

### 模板同步机制

复用现有选择器同步流程：

1. 设备轮询时，后端返回 `templates_version`
2. 设备检测到版本不一致时，请求 `GET /api/device/templates?version=xxx`
3. 后端返回更新的模板文件列表和 manifest
4. 设备下载模板图片到本地
5. 更新本地 manifest

### 后端新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/device/templates?version=xxx` | 获取模板清单和更新列表 |
| GET | `/api/device/templates/download/{filename}` | 下载单个模板图片 |
| CRUD | `/api/templates` | 管理端：模板 CRUD |

### 选择器配置扩展

在 `selectors.yaml` 中为 action 增加 `image` 类型策略：

```yaml
- action_name: "like_button"
  strategies:
    - { type: "text", value: "赞", priority: 1 }
    - { type: "desc", value: "点赞", priority: 2 }
    - { type: "id", value: "com.ss.android.ugc.aweme:id/like_icon", priority: 3 }
    - { type: "image", template: "like_button.png", threshold: 0.8, priority: 4 }
    - { type: "coordinate", x_percent: 0.85, y_percent: 0.45, priority: 5 }
```

---

## 模板更新与维护

### 触发更新的场景

| 场景 | 触发条件 | 处理方式 |
|------|---------|---------|
| 全部策略失败 | text/id/desc/image 全部失败 | 设备上报 UI 截图快照，后端记录告警 |
| 置信度下降 | 匹配置信度低于阈值 | 上报后端标记"置信度低"，Web 后台预警 |
| 主动更新 | 抖音大版本更新 | 运营人员手动采集新模板，上传后端 |

### 模板采集辅助脚本

```javascript
// device/tools/capture-template.js
// 导航到目标页面后运行，自动截屏并输出可交互元素信息
// 运营人员根据信息裁剪目标区域作为模板

function captureForTemplate() {
  var img = images.captureScreen();
  var path = "/sdcard/dy_auto/capture_" + Date.now() + ".png";
  images.save(img, path);

  // 输出当前页面所有可交互元素信息
  var clickables = clickable(true).find();
  var elements = [];
  for (var i = 0; i < clickables.length; i++) {
    var el = clickables[i];
    elements.push({
      text: el.text(), desc: el.desc(), id: el.id(), bounds: el.bounds()
    });
  }
  files.write(path.replace(".png", "_elements.json"), JSON.stringify(elements, null, 2));
}
```

### 模板图片要求

- 只包含目标元素，不包含周围背景
- 保留少量边距（元素周围 5-10px）
- 每个元素准备 1-2 个模板（正常状态 + 变体状态，如已点赞/未点赞）

### 版本管理

- 每次更新 manifest 版本号 +1
- 旧版本模板保留 1 个版本（方便回滚）
- 设备端只保留最新版本 + 上一个版本

---

## 改动范围

| 模块 | 改动 | 工作量 |
|------|------|--------|
| `device/core/ui-operator.js` | 新增 `_findByImage` 方法，`findElement` 支持截图传入 | 中 |
| `device/core/selector-loader.js` | 新增模板版本检测和同步逻辑 | 小 |
| 新增 `device/core/template-loader.js` | 模板图片下载、缓存、manifest 管理 | 中 |
| `server/config/selectors.yaml` | 为各 action 添加 image 策略 | 小 |
| `server/app/routers/device.py` | 新增模板同步 API | 小 |
| 新增 `server/app/routers/templates.py` | 模板管理 CRUD API | 中 |
| 配置文件 | selectors.yaml 支持 image 类型策略 | 小 |
| 模板图片采集 | 手动采集首批模板（约 10-15 个） | 手工 |
| 新增 `device/tools/capture-template.js` | 模板采集辅助脚本 | 小 |

## 实施顺序（审查后修订）

### 第一阶段：可行性验证 Spike（2 天）

**目标**：在投入模板同步基础设施前，验证模板匹配和 OCR 的实际命中率。

**实验 1：模板匹配精度测试**（1 天）
1. 在小米 10 上打开抖音 5 个不同页面（首页、搜索页、视频详情、个人主页、排序弹窗）
2. 每个页面截全屏，裁剪 5 个关键元素作为模板（点赞、关注、搜索、评论、排序选项）
3. 用 `images.findImage()` + 灰度 + 多尺度 [0.9, 1.0, 1.1] 匹配
4. 记录每个模板的命中率、置信度、匹配耗时
5. 验证 `findImage()` 返回坐标语义（左上角 vs 中心）
6. 测试暗色模式对灰度匹配的影响

**实验 2：OCR 降级对比**（0.5 天）
1. 对同样的 5 个页面，用 PaddleOCR 识别文字按钮
2. 对比 OCR 命中率 vs 模板匹配命中率
3. 确定哪些元素适合 OCR、哪些必须用模板匹配

**实验 3：性能基准**（0.5 天）
1. 在小米 10 上测试单次 `findImage()` 耗时（全屏 vs 限定区域）
2. 测试多尺度匹配的总耗时
3. 确定性能预算：图像匹配必须在 800ms 内完成

**止损标准**：
- 模板匹配命中率 < 85% → 重新评估方案，考虑 OCR 优先
- 单次匹配耗时 > 1500ms → 减少尺度数量或放弃多尺度
- 暗色模式命中率 < 70% → 需要明暗两套模板，重新评估维护成本

### 第二阶段：根据 Spike 结果决定方向

**路径 A**（命中率 > 85%）：按原方案推进
1. 集成到 UI 操作层（2-3 天）
2. 模板管理后端（2-3 天）
3. 首批模板采集（1 天）
4. 优化与稳定（持续）

**路径 B**（命中率 < 85%，OCR 效果好）：OCR 优先方案
1. 将 OCR 作为 image 之前的降级策略
2. 仅对无文字的图标元素使用模板匹配
3. 考虑 LLM-vision 作为最终降级

**路径 C**（两者都差）：重新设计
1. 调研 accessibility 树启发式方案
2. 考虑 LLM-vision 定位器

### 第三阶段：实现（无论哪个方向都必须解决的 CRITICAL 问题）

1. **截图内存安全** — 实现 `withScreen(callback)` 包装器，强制 try/finally
2. **路径遍历防护** — 模板下载端点文件名清理（禁止 `/`, `\`, `..`）
3. **完整测试计划** — 单元测试（模板匹配、内存管理）+ 集成测试（同步协议）+ 安全测试（路径遍历）

### 其他审查发现的修复

| 问题 | 修复方案 | 阶段 |
|------|---------|------|
| 模板/选择器版本分裂 | 统一为单一 `config_version` | 第二阶段 |
| findElement 签名变更 | 改用模块级 `_currentScreen` 属性 | 第二阶段 |
| 模板读取失败处理 | `_findByImage` 内 try/catch + null 检查 | 第二阶段 |
| 暗色模式 | 明暗两套模板或阈值调优 | Spike 后决定 |
| findImage 坐标语义 | Spike 中验证，实现时加 templateWidth/2 | 第二阶段 |
| 管理端认证 | 明确指定 `verify_admin_token` | 第二阶段 |
| 模板上传验证 | 500KB 限制 + PNG magic bytes + 尺寸检查 | 第二阶段 |
| 分辨率映射 | v1 只用多尺度，删除分辨率映射 | 设计简化 |
| 屏幕截图权限检查 | 启动时检测，失败则禁用 image 策略 | 第二阶段 |

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/autoplan` | Scope & strategy | 1 | issues_open | 5 findings (1 CRITICAL, 3 HIGH, 1 MEDIUM) |
| Eng Review | `/autoplan` | Architecture & tests (required) | 1 | issues_open | 17 findings (3 CRITICAL, 7 HIGH, 7 MEDIUM, 2 LOW) |
| Design Review | skipped | No UI scope | 0 | — | — |
| DX Review | skipped | No developer-facing scope | 0 | — | — |

- **UNRESOLVED:** 22 findings total, 3 CRITICAL resolved via spike-first approach
- **VERDICT:** ENG review found 3 critical issues (memory leak, no test plan, path traversal). All addressed in revised implementation plan. Spike-first approach accepted by user.
