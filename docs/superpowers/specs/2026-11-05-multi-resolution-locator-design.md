# 多分辨率元素定位优化

## Intent and authorization

用户在代码分析后要求“那请进行优化”，沿用上一轮建议的第一、第二阶段，并纳入实现它们必需的图片匹配与配置验证。此次授权实施，不再重复设计确认。以已合并的 `8dac313` 为基线，创建独立分支；完成验证后交付 PR，合并与部署另行决定。

## Goals

- 同一语义选择器能在不同分辨率、应用窗口、键盘状态中使用，优先无障碍节点与容器范围。
- 修正 images.scale 的倍率参数；对模板使用有限数量的等比缩放，保持阈值，按区域匹配。
- 统一截图、屏幕、应用区域与锚点区域的坐标换算，执行前重读几何状态、验证可见区域。
- 兼容旧 JSON：coordinate 的 x_percent/y_percent 为屏幕 0–1 比例；image 的同名字段为像素偏移；节点为尺寸百分比。新配置使用独立 position/offset 字段，不静默重写旧记录。
- OCR 文本没有坐标时不点击猜测位置；重试重新定位；有副作用的发送不以点击/回车返回值冒充成功，也不在结果未知时自动重发。
- 前端和服务端采用同一配置契约，错误单位、非有限数、反向区域、缺失锚点在保存时被拒绝。

## Constraints

- 设备生产代码保持 AutoJS6 / Rhino ES5.1：var、普通 function、CommonJS；不引入依赖或 setScreenMetrics。
- 无障碍 bounds 已为屏幕像素，禁止按分辨率再次缩放。
- 应用可用区域来自目标应用无障碍窗口/根节点，不能拿自动化应用自身的 Insets 冒充目标应用 Insets；不可获知时明确回退与边界验证。
- 使用当前分支既有 API/配置表；不修改数据库结构、不自动迁移旧策略、不改变非定位业务策略。
- 新代码必须覆盖多分辨率、偏移单位、截图映射、越界、键盘遮挡、位置变化、未知发送结果等行为测试。
- 自动测试不等于 Android 真机验证；交付明确说明尚未提供的实际机型/抖音版本与截图限制。

## Approaches

1. 仅修改固定坐标和图片倍率：改动小，但键盘、字体缩放、不同长宽比与窗口变化仍然会失效。
2. 保留配置系统，新增统一几何层，并让现有定位/点击与关键业务使用它：本次选择；兼容旧数据，解决已确认错误，并给区域/锚点配置明确入口。
3. 引入全套视觉识别、标注平台与机型模板库：需要用户实际设备数据与更大范围产品改造，本次不假设已有这些数据。

## Coordinate contract

新增可选 `position: {space, x, y}`。space 可为 `screen_normalized`、`content_normalized`、`anchor_normalized`、`screen_px`、`capture_px`；normalized 值为 0–1，边缘 1 映射到区域内最后一个像素。

新增可选 `offset: {unit, x, y}`。unit 为 `px`、`dp`、`target_fraction`。offset 优先于旧偏移字段；coordinate 的旧 x_percent/y_percent 仅为位置，绝不再次充当偏移。

新增可选 `region: {space, left, top, right, bottom}`，space 为三个 normalized 空间之一，四边 0–1 且 left < right、top < bottom。默认使用目标应用可见区域。

`anchor: {type, value, match_mode?}` 为单条语义选择器，type 为 text/id/desc/className；使用 anchor_normalized 必须提供且在设备当前窗口找到唯一可用锚点。不递归引用 action。

图片策略可带 `source_resolution: "1080x2400"`、`source_density: 3` 与 `scales: [0.9, 1, 1.1]`。scales 为最多五个有限正数，范围 0.25–4；默认围绕推导倍率最多三个等比候选；文件名/目录分辨率作为旧模板兼容来源。保持用户阈值，不自动降阈值。

## Geometry module interfaces

`device/core/screen-context.js` exports:

- `create(options)`: validated snapshot `{width,height,density,fontScale,rotation,contentBounds,blockedBounds,captureWidth,captureHeight,captureBounds,captureRotation,captureValid,signature,targetPackage,foregroundPackage,canInteract,observedAt}`.
- `read(image?, options?)`: refresh runtime display metrics, target application bounds and input-method/overlay bounds; image supplies actual capture dimensions. Does not cache geometry across actions.
- `rect(value)`, `intersect(a,b)`, `contains(rect,x,y)` use plain left/top/right/bottom rectangles and half-open physical pixel edges.
- `normalizedPoint(x,y,bounds)`, `captureToScreen(point,ctx)`, `screenToCapture(point,ctx)` return `{x,y}` or null. Explicit captureRotation supports 0/90/180/270; unknown mismatched capture aspect is invalid, never guessed.
- `regionForStrategy(strategy,ctx,anchorBounds?)`, `pointForStrategy(strategy,ctx,anchorBounds?)`, `offsetPoint(point,strategy,targetBounds,ctx,kind)` implement the contract and legacy semantics. kind is `node`, `image` or `coordinate`.
- `isUsablePoint(point,ctx,region?)` validates physical/content bounds, known blockers and target foreground state.
- `dp(value,ctx)` converts known display density.

UiObject remains the return type for raw semantic nodes to preserve callers using text/find/parent. Point results carry the screen-context signature and observed time. `clickElement` validates live geometry before actuation. `findElement(action, timeout, quiet)` remains compatible. New `clickAction(action, timeout, options?)` resolves a fresh target and returns an actuation boolean; postconditions remain explicit in callers.

## Calibration and refresh

Refresh resolution selection on runtime geometry changes; do not retain an init-only screen size. Calibration may crop an observed semantic target or a validated image target; coordinate-only guesses must not become automatically published new templates. Screenshot crop must convert screen bounds through the same mapping and clip to actual capture bounds. Keep existing API operational and describe any remaining version/physical-device limitations rather than claiming a new calibration platform exists.

Integration decisions: device selector snapshots now include row ID/version. Calibration uploads include that identity, target app version and actual capture metadata; the server validates the source revision and selects the exact action/platform/resolution target, assigns immutable content-based filenames, and appends a missing image strategy. Legacy uploads without identity are accepted only for a unique source profile. No new DB columns are needed. Image-only results without an explicit uniqueness proof are not enough to seed unattended calibration.

For unknown DM sends, retaining the existing transient claim was insufficient: active orphan claims expire after 30 minutes. New device claims therefore send `preserve_on_unknown: true` and use existing `Conversation.status = pending_confirmation`; successful reports restore active, proven pre-submit/failure outcomes may release. Legacy clients retain their prior timeout behavior. The management UI surfaces the pending status; it never implies a delivery receipt.

## Acceptance

Run deterministic geometry and actual-module runtime tests over 720×1600, 1080×2340/2400 and 1440×3200; resized/cropped capture, explicit rotation, invalid/ambiguous mapping, keyboard overlap, zero coordinates, out-of-range offsets and stale signatures. Verify handler no-coordinate OCR and unknown-send outcomes, fresh follow retries, scoped search/container gestures. Validate API create/update and UI editing without silently changing legacy semantics. Run all device, server and frontend suites and frontend build, independent code review, then publish the reviewed branch/PR. Provide a concise operational guide and a real-device acceptance matrix.
